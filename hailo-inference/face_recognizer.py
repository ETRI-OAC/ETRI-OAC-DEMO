"""
Face Recognition Module — Full Hailo Pipeline
ETRI Patrol Robot Project

Pipeline (all on Hailo-10H except lightweight CPU ops):
  1. Hailo SCRFD: face detection + 5-point landmarks (~5ms)
  2. CPU norm_crop: affine warp to 112×112 aligned face (<1ms)
  3. Hailo ArcFace: 512-dim embedding (~5ms)
  4. CPU cosine similarity matching (<1ms)

Fallback: InsightFace CPU if Hailo unavailable.
"""

import cv2
import numpy as np
from typing import Tuple, Optional, Dict
import os
import pickle

from insightface.utils.face_align import norm_crop


class FaceRecognizer:
    """Face recognizer: Hailo SCRFD + ArcFace, InsightFace CPU fallback."""

    def __init__(self, model_name: str = "buffalo_l",
                 similarity_threshold: float = 0.5,
                 ctx_id: int = 0,
                 use_hailo_server: bool = False,
                 hailo_server_host: str = "localhost",
                 hailo_server_port: int = 8003,
                 **kwargs):
        self.threshold = similarity_threshold
        self.hailo_detector = None
        self.hailo_client = None
        self.insightface_app = None

        # Try Hailo SCRFD + ArcFace
        if use_hailo_server:
            try:
                from hailo_face_detector import HailoFaceDetector
                self.hailo_detector = HailoFaceDetector(
                    use_server=True,
                    server_host=hailo_server_host,
                    server_port=hailo_server_port,
                )

                from hailo_inference_client import HailoInferenceClient
                self.hailo_client = HailoInferenceClient(
                    host=hailo_server_host, port=hailo_server_port
                )
                # Test ArcFace connection
                dummy = np.zeros((1, 112, 112, 3), dtype=np.uint8)
                self.hailo_client.infer("arcface_r50", dummy)

                print(f"[FaceRecognizer] Detection: Hailo SCRFD (via server)")
                print(f"[FaceRecognizer] Embedding: Hailo ArcFace (via server)")
            except Exception as e:
                print(f"[FaceRecognizer] Hailo init failed ({e}), using CPU InsightFace")
                self.hailo_detector = None
                self.hailo_client = None

        # CPU fallback: InsightFace
        if self.hailo_detector is None or self.hailo_client is None:
            from insightface.app import FaceAnalysis
            self.insightface_app = FaceAnalysis(
                name=model_name,
                providers=['CPUExecutionProvider']
            )
            self.insightface_app.prepare(ctx_id=ctx_id, det_size=(640, 640))
            if self.hailo_detector is None:
                print(f"[FaceRecognizer] Detection: CPU InsightFace SCRFD")
            if self.hailo_client is None:
                print(f"[FaceRecognizer] Embedding: CPU InsightFace ArcFace")

        print(f"[FaceRecognizer] Similarity threshold: {similarity_threshold}")
        self.known_faces: Dict[str, np.ndarray] = {}

    def _detect_and_align(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Detect face and return aligned 112×112 image.

        Uses Hailo SCRFD if available, else InsightFace CPU.
        """
        if self.hailo_detector is not None:
            dets = self.hailo_detector.detect(image)
            if dets:
                # landmarks: 5×2 [l_eye, r_eye, nose, l_mouth, r_mouth]
                lmk = dets[0]["landmarks"]
                return norm_crop(image, lmk)

        # Fallback or retry with InsightFace
        if self.insightface_app is not None:
            faces = self.insightface_app.get(image)
            if not faces:
                # Retry with padding
                h, w = image.shape[:2]
                pad = int(max(h, w) * 0.3)
                padded = cv2.copyMakeBorder(
                    image, pad, pad, pad, pad,
                    cv2.BORDER_CONSTANT, value=(0, 0, 0)
                )
                faces = self.insightface_app.get(padded)
            if faces and hasattr(faces[0], 'kps') and faces[0].kps is not None:
                return norm_crop(image if not faces else image, faces[0].kps)

        return None

    def _get_embedding(self, aligned_112: np.ndarray) -> Optional[np.ndarray]:
        """Get 512-dim embedding from aligned 112×112 face."""
        if self.hailo_client is not None:
            try:
                rgb = cv2.cvtColor(aligned_112, cv2.COLOR_BGR2RGB)
                tensor = np.expand_dims(rgb, axis=0).astype(np.uint8)
                outputs = self.hailo_client.infer("arcface_r50", tensor)
                emb = list(outputs.values())[0].flatten().astype(np.float32)
                return emb / np.linalg.norm(emb)
            except Exception as e:
                print(f"[FaceRecognizer] Hailo ArcFace failed: {e}")

        # CPU fallback
        if self.insightface_app is not None:
            faces = self.insightface_app.get(aligned_112)
            if not faces:
                pad = 30
                padded = cv2.copyMakeBorder(
                    aligned_112, pad, pad, pad, pad,
                    cv2.BORDER_CONSTANT, value=(0, 0, 0)
                )
                faces = self.insightface_app.get(padded)
            if faces:
                return faces[0].embedding

        return None

    def register_face(self, name: str, face_image: np.ndarray) -> bool:
        """Register a face to the known faces database."""
        aligned = self._detect_and_align(face_image)
        if aligned is None:
            print(f"[FaceRecognizer] Failed to register: {name} (no face detected)")
            return False

        embedding = self._get_embedding(aligned)
        if embedding is not None:
            self.known_faces[name] = embedding
            print(f"[FaceRecognizer] Registered: {name}")
            return True
        else:
            print(f"[FaceRecognizer] Failed to register: {name} (embedding failed)")
            return False

    def register_from_file(self, name: str, image_path: str) -> bool:
        """Register a face from an image file."""
        if not os.path.exists(image_path):
            print(f"[FaceRecognizer] File not found: {image_path}")
            return False
        image = cv2.imread(image_path)
        if image is None:
            print(f"[FaceRecognizer] Failed to read image: {image_path}")
            return False
        return self.register_face(name, image)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _match_embedding(self, embedding: np.ndarray) -> Tuple[str, float]:
        if len(self.known_faces) == 0:
            return "Unknown", 0.0
        best_match = "Unknown"
        best_similarity = 0.0
        for name, known_emb in self.known_faces.items():
            sim = self.cosine_similarity(embedding, known_emb)
            if sim > best_similarity:
                best_similarity = sim
                if sim >= self.threshold:
                    best_match = name
        return best_match, best_similarity

    def recognize(self, face_image: np.ndarray, **kwargs) -> Tuple[str, float]:
        """Recognize a face: detect → align → embed → match."""
        aligned = self._detect_and_align(face_image)
        if aligned is None:
            return "Unknown", 0.0

        embedding = self._get_embedding(aligned)
        if embedding is None:
            return "Unknown", 0.0

        return self._match_embedding(embedding)

    def save_database(self, path: str = "database/known_faces.pkl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self.known_faces, f)
        print(f"[FaceRecognizer] Database saved to {path}")

    def load_database(self, path: str = "database/known_faces.pkl") -> bool:
        if not os.path.exists(path):
            print(f"[FaceRecognizer] Database file not found: {path}")
            return False
        with open(path, 'rb') as f:
            self.known_faces = pickle.load(f)
        print(f"[FaceRecognizer] Loaded {len(self.known_faces)} faces from database")
        return True
