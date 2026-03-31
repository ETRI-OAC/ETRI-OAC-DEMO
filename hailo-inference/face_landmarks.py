"""
Utility functions for converting YOLO COCO-17 keypoints to ArcFace 5-point landmarks.
No heavy dependencies (only numpy, cv2).
"""

import cv2
import numpy as np
from typing import Optional

# ArcFace canonical reference landmarks for 112x112 aligned face
ARCFACE_REF_LANDMARKS = np.array([
    [38.2946, 51.6963],   # LEFT_EYE
    [73.5318, 51.5014],   # RIGHT_EYE
    [56.0252, 71.7366],   # NOSE
    [41.5493, 92.3655],   # LEFT_MOUTH
    [70.7299, 92.2041],   # RIGHT_MOUTH
], dtype=np.float32)


def coco17_to_arcface_landmarks(keypoints_2d: list, bbox: list) -> Optional[np.ndarray]:
    """Convert YOLO COCO-17 keypoints to 5-point ArcFace landmarks in crop coordinates.

    Args:
        keypoints_2d: COCO-17 keypoints [[x,y], ...] in full image coordinates.
                      Index 0=nose, 1=left_eye, 2=right_eye, 3=left_ear, 4=right_ear
        bbox: Face crop bounding box [x1, y1, x2, y2] in full image coordinates.

    Returns:
        5x2 numpy array of [left_eye, right_eye, nose, left_mouth, right_mouth]
        in crop-local coordinates, or None if keypoints are invalid.
    """
    if len(keypoints_2d) < 3:
        return None

    nose = np.array(keypoints_2d[0], dtype=np.float32)
    l_eye = np.array(keypoints_2d[1], dtype=np.float32)
    r_eye = np.array(keypoints_2d[2], dtype=np.float32)

    # Validate: all keypoints must be positive
    if any(p[0] <= 0 or p[1] <= 0 for p in [nose, l_eye, r_eye]):
        return None

    # Synthesize mouth corners from eye/nose geometry
    eye_center_y = (l_eye[1] + r_eye[1]) / 2
    nose_to_eye = nose[1] - eye_center_y
    if nose_to_eye <= 0:
        return None
    mouth_y = nose[1] + nose_to_eye * 0.6

    eye_span = abs(r_eye[0] - l_eye[0])
    if eye_span < 5:  # eyes too close — bad detection
        return None
    eye_center_x = (l_eye[0] + r_eye[0]) / 2
    l_mouth = np.array([eye_center_x - eye_span * 0.35, mouth_y], dtype=np.float32)
    r_mouth = np.array([eye_center_x + eye_span * 0.35, mouth_y], dtype=np.float32)

    # Convert to crop-local coordinates
    x1, y1 = float(bbox[0]), float(bbox[1])
    landmarks = np.array([
        l_eye - [x1, y1],
        r_eye - [x1, y1],
        nose - [x1, y1],
        l_mouth - [x1, y1],
        r_mouth - [x1, y1],
    ], dtype=np.float32)

    return landmarks


def align_face(image: np.ndarray, landmarks_5: np.ndarray) -> np.ndarray:
    """Warp face image to 112x112 canonical pose using 5-point landmarks.

    Args:
        image: Face crop (BGR)
        landmarks_5: 5x2 array [left_eye, right_eye, nose, left_mouth, right_mouth]
                     in image-local coordinates.

    Returns:
        112x112 aligned face image (BGR)
    """
    src = landmarks_5.astype(np.float32)
    dst = ARCFACE_REF_LANDMARKS.astype(np.float32)
    M, _ = cv2.estimateAffinePartial2D(src, dst)
    if M is None:
        return cv2.resize(image, (112, 112))
    return cv2.warpAffine(image, M, (112, 112), borderMode=cv2.BORDER_REPLICATE)
