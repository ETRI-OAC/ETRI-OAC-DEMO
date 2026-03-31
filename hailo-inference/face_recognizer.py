"""
Face Recognition Module using ArcFace
ETRI Patrol Robot Project - Face Recognition Stage

Pipeline:
  1. InsightFace CPU SCRFD detects face + computes aligned 112x112 crop
  2. Hailo-10 arcface_r50 computes 512-dim embedding (fast, ~5ms)
  3. Cosine similarity matching against known faces DB

Fallback: if Hailo unavailable, InsightFace CPU ArcFace for embedding.
"""

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from typing import Tuple, Optional, Dict
import os
import pickle


class FaceRecognizer:
    """Face recognizer: InsightFace alignment + Hailo ArcFace embedding"""

    def __init__(self, model_name: str = "buffalo_l",
                 similarity_threshold: float = 0.5,
                 ctx_id: int = 0,
                 use_hailo_server: bool = False,
                 hailo_server_host: str = "localhost",
                 hailo_server_port: int = 8003,
                 **kwargs):
        self.threshold = similarity_threshold
        self.hailo_client = None

        # InsightFace: detection + alignment + CPU ArcFace fallback
        self.app = FaceAnalysis(
            name=model_name,
            providers=['CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        # Hailo ArcFace for fast embedding
        if use_hailo_server:
            try:
                from hailo_inference_client import HailoInferenceClient
                self.hailo_client = HailoInferenceClient(
                    host=hailo_server_host, port=hailo_server_port
                )
                # Test connection
                dummy = np.zeros((1, 112, 112, 3), dtype=np.uint8)
                self.hailo_client.infer("arcface_r50", dummy)
                print(f"[FaceRecognizer] Embedding: Hailo-10 arcface_r50 "
                      f"(via {hailo_server_host}:{hailo_server_port})")
            except Exception as e:
                print(f"[FaceRecognizer] Hailo ArcFace unavailable ({e}), using CPU")
                self.hailo_client = None

        if self.hailo_client is None:
            print(f"[FaceRecognizer] Embedding: CPU InsightFace {model_name}")

        print(f"[FaceRecognizer] Similarity threshold: {similarity_threshold}")

        self.known_faces: Dict[str, np.ndarray] = {}

    def _get_aligned_face(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Detect face and return InsightFace-aligned 112x112 BGR image.

        InsightFace internally: SCRFD detect → 5-point landmarks → warp to 112x112.
        This alignment is high quality and handles pose/angle well.
        """
        faces = self.app.get(image)
        if not faces:
            # Retry with padding (for tight crops)
            h, w = image.shape[:2]
            pad = int(max(h, w) * 0.3)
            padded = cv2.copyMakeBorder(
                image, pad, pad, pad, pad,
                cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
            faces = self.app.get(padded)

        if not faces:
            return None

        # InsightFace Face object has .normed_embedding (from its own ArcFace)
        # but also stores the aligned crop internally. We need to get the
        # aligned image. InsightFace does: detect → align → embed.
        # The aligned image isn't directly exposed, so we reconstruct it
        # from the face's landmarks using InsightFace's own alignment.
        face = faces[0]
        if hasattr(face, 'kps') and face.kps is not None:
            from insightface.utils.face_align import norm_crop
            aligned = norm_crop(image, face.kps)
            return aligned

        return None

    def _hailo_embedding(self, aligned_112: np.ndarray) -> Optional[np.ndarray]:
        """Get embedding from Hailo arcface_r50."""
        if self.hailo_client is None:
            return None
        try:
            rgb = cv2.cvtColor(aligned_112, cv2.COLOR_BGR2RGB)
            tensor = np.expand_dims(rgb, axis=0).astype(np.uint8)
            outputs = self.hailo_client.infer("arcface_r50", tensor)
            emb = list(outputs.values())[0].flatten().astype(np.float32)
            return emb / np.linalg.norm(emb)
        except Exception as e:
            print(f"[FaceRecognizer] Hailo embed failed: {e}")
            return None

    def _get_embedding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Full pipeline: InsightFace align → Hailo/CPU embed."""
        aligned = self._get_aligned_face(image)
        if aligned is None:
            return None

        # Prefer Hailo
        emb = self._hailo_embedding(aligned)
        if emb is not None:
            return emb

        # CPU fallback: use InsightFace's own embedding
        faces = self.app.get(image)
        if not faces:
            h, w = image.shape[:2]
            pad = int(max(h, w) * 0.3)
            padded = cv2.copyMakeBorder(
                image, pad, pad, pad, pad,
                cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
            faces = self.app.get(padded)
        if faces:
            return faces[0].embedding
        return None

    def register_face(self, name: str, face_image: np.ndarray) -> bool:
        """Register a face to the known faces database."""
        embedding = self._get_embedding(face_image)
        if embedding is not None:
            self.known_faces[name] = embedding
            print(f"[FaceRecognizer] Registered: {name}")
            return True
        else:
            print(f"[FaceRecognizer] Failed to register: {name} (no face detected)")
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
        """Recognize a face: InsightFace align → Hailo embed → DB match.

        Args:
            face_image: Cropped face image (BGR)
            **kwargs: Ignored (backward compat for landmarks_5 etc.)
        """
        embedding = self._get_embedding(face_image)
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
