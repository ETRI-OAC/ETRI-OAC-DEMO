"""
Face Recognition Module using ArcFace
ETRI Patrol Robot Project - Face Recognition Stage

ArcFace embedding:
  - hailo: arcface_mobilefacenet on Hailo-10 via inference server (preferred)
  - cpu:   InsightFace w600k_r50 on CPU (fallback / registration)

Face detection for registration: InsightFace CPU SCRFD (detects + provides landmarks).
Face detection for recognition: YOLO COCO-17 keypoints (provided by caller).
"""

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from typing import List, Tuple, Optional, Dict
import os
import pickle

from face_landmarks import coco17_to_arcface_landmarks, align_face


class FaceRecognizer:
    """ArcFace based face recognizer with optional Hailo acceleration"""

    def __init__(self, model_name: str = "buffalo_l",
                 similarity_threshold: float = 0.5,
                 ctx_id: int = 0,
                 use_hailo_server: bool = False,
                 hailo_server_host: str = "localhost",
                 hailo_server_port: int = 8003,
                 **kwargs):
        """
        Initialize the face recognizer.

        Args:
            model_name: InsightFace model name (for CPU fallback + registration)
            similarity_threshold: Cosine similarity threshold for recognition
            ctx_id: Context ID (-1 for CPU)
            use_hailo_server: Use Hailo inference server for ArcFace embedding
            hailo_server_host: Hailo inference server host
            hailo_server_port: Hailo inference server port
        """
        self.threshold = similarity_threshold
        self.hailo_client = None

        # Initialize InsightFace (for CPU fallback detection + registration landmarks)
        self.app = FaceAnalysis(
            name=model_name,
            providers=['CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        # Extract the CPU ArcFace recognition model for fallback
        self.rec_model = None
        for model in self.app.models:
            if hasattr(model, 'input_size') and tuple(model.input_size) == (112, 112):
                self.rec_model = model
                break

        # Try connecting to Hailo inference server for ArcFace
        if use_hailo_server:
            try:
                from hailo_inference_client import HailoInferenceClient
                self.hailo_client = HailoInferenceClient(
                    host=hailo_server_host, port=hailo_server_port
                )
                print(f"[FaceRecognizer] ArcFace: Hailo-10 (via inference server at "
                      f"{hailo_server_host}:{hailo_server_port})")
            except Exception as e:
                print(f"[FaceRecognizer] Hailo client init failed ({e}), using CPU ArcFace")
                self.hailo_client = None

        if self.hailo_client is None:
            print(f"[FaceRecognizer] ArcFace: CPU (InsightFace {model_name})")

        print(f"[FaceRecognizer] Similarity threshold: {similarity_threshold}")

        # Database of known faces: {name: embedding}
        self.known_faces: Dict[str, np.ndarray] = {}

    def _get_embedding_hailo(self, aligned_112: np.ndarray) -> Optional[np.ndarray]:
        """Get ArcFace embedding via Hailo inference server.

        Args:
            aligned_112: 112x112 BGR aligned face image

        Returns:
            512-dim normalized embedding or None
        """
        if self.hailo_client is None:
            return None
        try:
            # HEF expects RGB uint8 (112, 112, 3)
            rgb = cv2.cvtColor(aligned_112, cv2.COLOR_BGR2RGB)
            tensor = np.expand_dims(rgb, axis=0).astype(np.uint8)  # (1, 112, 112, 3)

            outputs = self.hailo_client.infer("arcface_mobilefacenet", tensor)

            # Get the first (and only) output — 512-dim embedding
            embedding = list(outputs.values())[0].flatten().astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            return embedding
        except Exception as e:
            print(f"[FaceRecognizer] Hailo ArcFace failed ({e}), falling back to CPU")
            return None

    def _get_embedding_cpu(self, aligned_112: np.ndarray) -> Optional[np.ndarray]:
        """Get ArcFace embedding via CPU InsightFace model.

        Args:
            aligned_112: 112x112 BGR aligned face image

        Returns:
            512-dim normalized embedding or None
        """
        if self.rec_model is None:
            return None

        img = cv2.cvtColor(aligned_112, cv2.COLOR_BGR2RGB)
        img = np.transpose(img, (2, 0, 1)).astype(np.float32)
        img = (img - 127.5) / 127.5
        img = np.expand_dims(img, axis=0)

        embedding = self.rec_model.session.run(
            self.rec_model.output_names,
            {self.rec_model.input_names[0]: img}
        )[0][0]

        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def get_embedding_from_landmarks(self, face_image: np.ndarray,
                                      landmarks_5: np.ndarray) -> Optional[np.ndarray]:
        """Get ArcFace embedding using pre-computed landmarks.

        Args:
            face_image: Cropped face image (BGR)
            landmarks_5: 5x2 array in crop-local coordinates

        Returns:
            512-dim embedding or None
        """
        aligned = align_face(face_image, landmarks_5)

        # Prefer Hailo, fall back to CPU
        embedding = self._get_embedding_hailo(aligned)
        if embedding is None:
            embedding = self._get_embedding_cpu(aligned)
        return embedding

    def get_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """Get face embedding using CPU InsightFace detection (fallback).

        Used when no landmarks are available (e.g., warmup).
        """
        h, w = face_image.shape[:2]
        pad = int(max(h, w) * 0.3)
        padded = cv2.copyMakeBorder(
            face_image, pad, pad, pad, pad,
            cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )
        faces = self.app.get(padded)
        if len(faces) > 0:
            return faces[0].embedding
        return None

    def register_face(self, name: str, face_image: np.ndarray,
                      landmarks_5: Optional[np.ndarray] = None) -> bool:
        """Register a face to the known faces database."""
        embedding = None

        if landmarks_5 is not None:
            embedding = self.get_embedding_from_landmarks(face_image, landmarks_5)

        if embedding is None:
            faces = self.app.get(face_image)
            if not faces:
                embedding = self.get_embedding(face_image)
            else:
                embedding = faces[0].embedding

        if embedding is not None:
            self.known_faces[name] = embedding
            print(f"[FaceRecognizer] Registered: {name}")
            return True
        else:
            print(f"[FaceRecognizer] Failed to register: {name} (no face detected)")
            return False

    def register_from_file(self, name: str, image_path: str) -> bool:
        """Register a face from an image file.

        Uses InsightFace to detect the face, extracts 5-point landmarks,
        then computes embedding via the same align_face + ArcFace pipeline
        used in recognize(), ensuring consistent embeddings.
        """
        if not os.path.exists(image_path):
            print(f"[FaceRecognizer] File not found: {image_path}")
            return False
        image = cv2.imread(image_path)
        if image is None:
            print(f"[FaceRecognizer] Failed to read image: {image_path}")
            return False

        # Detect face with InsightFace to get landmarks
        faces = self.app.get(image)
        if not faces:
            h, w = image.shape[:2]
            pad = int(max(h, w) * 0.3)
            padded = cv2.copyMakeBorder(
                image, pad, pad, pad, pad,
                cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
            faces = self.app.get(padded)

        if not faces:
            print(f"[FaceRecognizer] Failed to register: {name} (no face detected)")
            return False

        face = faces[0]

        # Use align_face + ArcFace (same pipeline as recognize)
        if hasattr(face, 'kps') and face.kps is not None:
            landmarks_5 = face.kps.astype(np.float32)
            embedding = self.get_embedding_from_landmarks(image, landmarks_5)
            if embedding is not None:
                self.known_faces[name] = embedding
                print(f"[FaceRecognizer] Registered: {name} (landmark-aligned)")
                return True

        # Fallback
        return self.register_face(name, image)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _match_embedding(self, embedding: np.ndarray) -> Tuple[str, float]:
        if len(self.known_faces) == 0:
            return "Unknown", 0.0

        best_match = "Unknown"
        best_similarity = 0.0
        for name, known_embedding in self.known_faces.items():
            similarity = self.cosine_similarity(embedding, known_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                if similarity >= self.threshold:
                    best_match = name
        return best_match, best_similarity

    def recognize(self, face_image: np.ndarray,
                  landmarks_5: Optional[np.ndarray] = None) -> Tuple[str, float]:
        """Recognize a face against the known faces database.

        Args:
            face_image: Cropped face image (BGR)
            landmarks_5: Optional 5x2 landmarks in crop-local coordinates.

        Returns:
            Tuple of (name, similarity)
        """
        embedding = None

        if landmarks_5 is not None:
            embedding = self.get_embedding_from_landmarks(face_image, landmarks_5)

        if embedding is None:
            embedding = self.get_embedding(face_image)

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
