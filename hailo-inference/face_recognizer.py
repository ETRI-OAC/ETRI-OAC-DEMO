"""
Face Recognition Module using ArcFace (InsightFace)
ETRI Patrol Robot Project - Face Recognition Stage

Face detection backends:
  - landmarks: Pre-computed YOLO COCO-17 keypoints (preferred, no re-detection)
  - cpu:       InsightFace built-in SCRFD on CPU (fallback when no landmarks)

In all cases, ArcFace embedding runs on CPU via onnxruntime.
"""

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from typing import List, Tuple, Optional, Dict
import os
import pickle

from face_landmarks import coco17_to_arcface_landmarks, align_face


class FaceRecognizer:
    """ArcFace based face recognizer using InsightFace"""

    def __init__(self, model_name: str = "buffalo_l",
                 similarity_threshold: float = 0.5,
                 ctx_id: int = 0,
                 **kwargs):
        """
        Initialize the face recognizer.

        Args:
            model_name: InsightFace model name (buffalo_l, buffalo_s, etc.)
            similarity_threshold: Cosine similarity threshold for recognition
            ctx_id: Context ID (-1 for CPU)
            **kwargs: Legacy args (hailo_hef_path, use_hailo_server, etc.) — ignored.
        """
        self.threshold = similarity_threshold

        # Initialize InsightFace (needed for CPU fallback detection + ArcFace model)
        self.app = FaceAnalysis(
            name=model_name,
            providers=['CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        # Extract the ArcFace recognition model for direct use with pre-aligned images
        self.rec_model = None
        for model in self.app.models:
            if hasattr(model, 'input_size') and tuple(model.input_size) == (112, 112):
                self.rec_model = model
                break
        if self.rec_model is None:
            print("[FaceRecognizer] WARNING: Could not extract ArcFace model, "
                  "landmark-based recognition will fall back to SCRFD")

        print(f"[FaceRecognizer] Initialized: model={model_name}, "
              f"landmark_align={'yes' if self.rec_model else 'no (fallback)'}, "
              f"embedding=CPU")
        print(f"[FaceRecognizer] Similarity threshold: {similarity_threshold}")

        # Database of known faces: {name: embedding}
        self.known_faces: Dict[str, np.ndarray] = {}

    def get_embedding_from_landmarks(self, face_image: np.ndarray,
                                      landmarks_5: np.ndarray) -> Optional[np.ndarray]:
        """Get ArcFace embedding using pre-computed landmarks (no SCRFD needed).

        Args:
            face_image: Cropped face image (BGR)
            landmarks_5: 5x2 array in crop-local coordinates

        Returns:
            512-dim embedding or None
        """
        if self.rec_model is None:
            return None

        aligned = align_face(face_image, landmarks_5)

        # ArcFace preprocessing: BGR→RGB, HWC→CHW, float32, normalize
        img = cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)
        img = np.transpose(img, (2, 0, 1)).astype(np.float32)
        img = (img - 127.5) / 127.5
        img = np.expand_dims(img, axis=0)

        # Run ArcFace ONNX model directly
        embedding = self.rec_model.session.run(
            self.rec_model.output_names,
            {self.rec_model.input_names[0]: img}
        )[0][0]

        # Normalize embedding
        embedding = embedding / np.linalg.norm(embedding)
        return embedding

    def get_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """Get face embedding using CPU InsightFace detection (SCRFD fallback).

        Used when no landmarks are available (e.g., warmup, registration).
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

    def register_face(self, name: str, face_image: np.ndarray) -> bool:
        """Register a face to the known faces database."""
        # Try full image detection first, then padded fallback
        faces = self.app.get(face_image)
        if faces:
            embedding = faces[0].embedding
        else:
            embedding = self.get_embedding(face_image)

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
        """Match embedding against known faces database."""
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
                         If provided, skips SCRFD and aligns directly.

        Returns:
            Tuple of (name, similarity)
        """
        embedding = None

        # Preferred: use pre-computed landmarks (no SCRFD)
        if landmarks_5 is not None and self.rec_model is not None:
            embedding = self.get_embedding_from_landmarks(face_image, landmarks_5)

        # Fallback: CPU InsightFace SCRFD detection
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
