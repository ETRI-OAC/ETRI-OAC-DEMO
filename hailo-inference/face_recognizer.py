"""
Face Recognition Module using ArcFace (InsightFace)
ETRI Patrol Robot Project - Face Recognition Stage

Supports two face detection backends:
  - hailo: SCRFD on Hailo-10 (shares device with OAK-ROS2 pose estimation)
  - cpu:   InsightFace built-in SCRFD on CPU (default)

In both cases, ArcFace embedding runs on CPU via onnxruntime.
"""

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from insightface.model_zoo import get_model
from typing import List, Tuple, Optional, Dict
import os
import pickle


class FaceRecognizer:
    """ArcFace based face recognizer using InsightFace"""

    def __init__(self, model_name: str = "buffalo_l",
                 similarity_threshold: float = 0.5,
                 ctx_id: int = 0,
                 hailo_hef_path: Optional[str] = None,
                 hailo_device_id: Optional[str] = None,
                 hailo_device_index: int = 0,
                 use_hailo_server: bool = False,
                 hailo_server_host: str = "localhost",
                 hailo_server_port: int = 8003):
        """
        Initialize the face recognizer

        Args:
            model_name: InsightFace model name (buffalo_l, buffalo_s, etc.)
            similarity_threshold: Cosine similarity threshold for recognition
            ctx_id: Context ID (-1 for CPU)
            hailo_hef_path: Path to SCRFD .hef for Hailo-10 face detection.
                           If None, uses InsightFace CPU detection.
            hailo_device_id: Hailo device ID (e.g. '0000:02:00.0').
                            If None, auto-detects.
            hailo_device_index: Which Hailo device to use when multiple
                               present (0=first, 1=second). Ignored if
                               hailo_device_id is specified.
            use_hailo_server: Use centralized hailo_inference_server instead
                             of direct VDevice access.
            hailo_server_host: Inference server host (default: localhost).
            hailo_server_port: Inference server port (default: 8003).
        """
        self.threshold = similarity_threshold
        self.hailo_detector = None

        # Initialize InsightFace (always needed for ArcFace embedding)
        self.app = FaceAnalysis(
            name=model_name,
            providers=['CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))

        # Use Hailo-10 for face detection if available
        if hailo_hef_path == "__skip__":
            # Explicitly skip Hailo — CPU-only mode
            self.hailo_detector = None
            hailo_hef_path = None
        elif use_hailo_server:
            # Use centralized inference server (shares Hailo device)
            try:
                from hailo_face_detector import HailoFaceDetector
                self.hailo_detector = HailoFaceDetector(
                    use_server=True,
                    server_host=hailo_server_host,
                    server_port=hailo_server_port,
                )
                print("[FaceRecognizer] Face detection: Hailo-10 (via inference server)")
            except Exception as e:
                print(f"[FaceRecognizer] Hailo server init failed ({e}), falling back to CPU")
                self.hailo_detector = None
        else:
            # Direct VDevice access
            if hailo_hef_path is None:
                try:
                    from hailo_utils import is_hailo_available
                    if is_hailo_available():
                        from hailo_model_downloader import get_hef_path
                        hailo_hef_path = get_hef_path("scrfd_10g")
                except ImportError:
                    pass

            if hailo_hef_path:
                try:
                    from hailo_face_detector import HailoFaceDetector
                    from hailo_utils import detect_hailo_device
                    if hailo_device_id is None:
                        hailo_device_id = detect_hailo_device(device_index=hailo_device_index)
                    self.hailo_detector = HailoFaceDetector(
                        hef_path=hailo_hef_path,
                        device_id=hailo_device_id,
                    )
                    print("[FaceRecognizer] Face detection: Hailo-10 (direct)")
                except Exception as e:
                    print(f"[FaceRecognizer] Hailo init failed ({e}), falling back to CPU")
                    self.hailo_detector = None

        det_backend = "Hailo-10" if self.hailo_detector else "CPU"
        print(f"[FaceRecognizer] Initialized: model={model_name}, "
              f"detection={det_backend}, embedding=CPU")
        print(f"[FaceRecognizer] Similarity threshold: {similarity_threshold}")

        # Database of known faces: {name: embedding}
        self.known_faces: Dict[str, np.ndarray] = {}

    def _detect_faces(self, image: np.ndarray):
        """Detect faces using Hailo or CPU backend.

        Returns:
            List of dicts with 'bbox' and 'embedding' (or InsightFace Face objects).
        """
        # Always use CPU InsightFace for detection + embedding
        # Hailo SCRFD works well on full frames but fails on small face crops,
        # and the crop→re-detect→embed pipeline adds complexity without benefit.
        # CPU InsightFace SCRFD is fast enough for per-request face detection.
        return self.app.get(image)

    def get_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Get face embedding from a cropped face image

        Args:
            face_image: Cropped face image (BGR format)

        Returns:
            512-dimensional embedding vector or None if no face detected
        """
        # InsightFace expects the full image and detects face internally
        # For better results with cropped faces, we pad the image
        h, w = face_image.shape[:2]

        # Add padding around the face
        pad = int(max(h, w) * 0.3)
        padded = cv2.copyMakeBorder(
            face_image, pad, pad, pad, pad,
            cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )

        faces = self._detect_faces(padded)

        if len(faces) > 0:
            return faces[0].embedding
        return None

    def register_face(self, name: str, face_image: np.ndarray) -> bool:
        """
        Register a face to the known faces database

        Args:
            name: Name/ID of the person
            face_image: Cropped face image or full image with one face

        Returns:
            True if registration successful
        """
        # Try detecting on the full image first (works best for full photos)
        faces = self._detect_faces(face_image)
        if faces:
            embedding = faces[0].embedding
        else:
            # Fallback: pad and retry (for tightly cropped face images)
            embedding = self.get_embedding(face_image)

        if embedding is not None:
            self.known_faces[name] = embedding
            print(f"[FaceRecognizer] Registered: {name}")
            return True
        else:
            print(f"[FaceRecognizer] Failed to register: {name} (no face detected)")
            return False

    def register_from_file(self, name: str, image_path: str) -> bool:
        """
        Register a face from an image file

        Args:
            name: Name/ID of the person
            image_path: Path to the image file

        Returns:
            True if registration successful
        """
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
        """
        Calculate cosine similarity between two vectors

        Args:
            a, b: Embedding vectors

        Returns:
            Cosine similarity score (0-1)
        """
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def recognize(self, face_image: np.ndarray) -> Tuple[str, float]:
        """
        Recognize a face against the known faces database

        Args:
            face_image: Cropped face image

        Returns:
            Tuple of (name, similarity) - name is "Unknown" if below threshold
        """
        embedding = self.get_embedding(face_image)

        if embedding is None:
            return "Unknown", 0.0

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

    def save_database(self, path: str = "database/known_faces.pkl"):
        """Save known faces database to file"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self.known_faces, f)
        print(f"[FaceRecognizer] Database saved to {path}")

    def load_database(self, path: str = "database/known_faces.pkl") -> bool:
        """Load known faces database from file"""
        if not os.path.exists(path):
            print(f"[FaceRecognizer] Database file not found: {path}")
            return False

        with open(path, 'rb') as f:
            self.known_faces = pickle.load(f)
        print(f"[FaceRecognizer] Loaded {len(self.known_faces)} faces from database")
        return True


if __name__ == "__main__":
    # Test face recognizer
    recognizer = FaceRecognizer(similarity_threshold=0.5)

    # Register a face from file (example)
    # recognizer.register_from_file("Junha", "database/base_image.jpg")

    # Test with webcam
    cap = cv2.VideoCapture(0)

    print("Press 'r' to register current face as 'TestUser'")
    print("Press 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Get faces from InsightFace directly
        faces = recognizer.app.get(frame)

        for face in faces:
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox

            # Get recognition result
            face_crop = frame[y1:y2, x1:x2]
            name, similarity = recognizer.recognize(face_crop)

            # Draw result
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{name} ({similarity:.2f})"
            cv2.putText(frame, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Face Recognition", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r') and len(faces) > 0:
            # Register first detected face
            recognizer.register_face("TestUser", frame)

    cap.release()
    cv2.destroyAllWindows()
