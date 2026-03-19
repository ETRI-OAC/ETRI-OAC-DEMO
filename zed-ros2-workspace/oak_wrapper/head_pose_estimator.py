#!/usr/bin/env python3
"""
Head pose and bounding box estimation from COCO-17 keypoints.

Provides geometric estimation of head orientation (quaternion) and
head bounding box from face keypoints (nose, eyes, ears).
These are used by demo scripts for:
  - is_person_looking_at_cam(): checks |yaw| > 160 degrees
  - crop_face(): crops head region for face recognition
"""

from typing import List, Tuple
import numpy as np

# COCO-17 keypoint indices
NOSE = 0
LEFT_EYE = 1
RIGHT_EYE = 2
LEFT_EAR = 3
RIGHT_EAR = 4


def estimate_head_orientation(coco_keypoints: List[List[float]]) -> List[float]:
    """
    Estimate head orientation as a quaternion [x, y, z, w] from COCO face keypoints.

    The demo scripts extract yaw via:
        sin_yaw = 2*(qw*qz + qx*qy)
        cos_yaw = 1 - 2*(qy² + qz²)
        yaw = atan2(sin_yaw, cos_yaw)

    In the ZED coordinate convention (RIGHT_HANDED_Z_UP_X_FWD), a person
    facing the camera has |yaw| close to pi (180 degrees).

    The demo considers |yaw| > deg2rad(160) as "looking at camera".

    Strategy: Use eye positions relative to nose to estimate yaw.
    - If both eyes are visible and roughly symmetric about the nose → facing camera
    - If eyes are asymmetric or one is missing → turned sideways

    Returns:
        Quaternion [x, y, z, w] encoding estimated head yaw.
    """
    if len(coco_keypoints) < 5:
        return [0.0, 0.0, 0.0, 1.0]

    nose = coco_keypoints[NOSE]
    l_eye = coco_keypoints[LEFT_EYE]
    r_eye = coco_keypoints[RIGHT_EYE]
    l_ear = coco_keypoints[LEFT_EAR]
    r_ear = coco_keypoints[RIGHT_EAR]

    # Need at least nose and one eye
    if nose[0] <= 0 or nose[1] <= 0:
        return [0.0, 0.0, 0.0, 1.0]

    have_l_eye = l_eye[0] > 0 and l_eye[1] > 0
    have_r_eye = r_eye[0] > 0 and r_eye[1] > 0
    have_l_ear = l_ear[0] > 0 and l_ear[1] > 0
    have_r_ear = r_ear[0] > 0 and r_ear[1] > 0

    yaw = 0.0

    if have_l_eye and have_r_eye:
        # Both eyes visible — estimate yaw from asymmetry
        eye_center_x = (l_eye[0] + r_eye[0]) / 2.0
        eye_span = abs(r_eye[0] - l_eye[0])
        if eye_span > 1.0:
            # How much the nose is offset from eye center (normalized)
            nose_offset = (nose[0] - eye_center_x) / eye_span
            # Small offset → facing camera (yaw ≈ π)
            # Large offset → turned (yaw ≈ π/2)
            yaw = np.pi - np.arctan2(abs(nose_offset) * 3.0, 1.0)
            if nose_offset > 0:
                yaw = -yaw
        else:
            # Eyes very close together → probably facing camera
            yaw = np.pi
    elif have_l_eye or have_r_eye:
        # Only one eye visible — person is turned significantly
        # If only left eye visible → turned right (positive yaw ~90°)
        # If only right eye visible → turned left (negative yaw ~-90°)
        yaw = np.pi / 2.0 if have_l_eye else -np.pi / 2.0
    elif have_l_ear and have_r_ear:
        # Both ears but no eyes? Probably facing away
        yaw = 0.0
    else:
        # Not enough info
        return [0.0, 0.0, 0.0, 1.0]

    # Enhance with ear visibility:
    # If facing camera, both ears may or may not be visible
    # If turned, typically only one ear is visible
    if have_l_eye and have_r_eye:
        if have_l_ear != have_r_ear:
            # One ear missing → slightly more turned
            # Reduce yaw magnitude slightly toward pi/2
            yaw = yaw * 0.85
        elif have_l_ear and have_r_ear:
            # Both ears visible → very likely facing camera
            # Push yaw closer to pi
            if abs(yaw) > np.pi / 2:
                yaw = np.sign(yaw) * min(abs(yaw) * 1.1, np.pi)

    # Convert yaw to quaternion [x, y, z, w]
    # Rotation around Z-axis (yaw) in ZED coordinate convention
    qx = 0.0
    qy = 0.0
    qz = np.sin(yaw / 2.0)
    qw = np.cos(yaw / 2.0)

    return [float(qx), float(qy), float(qz), float(qw)]


def estimate_head_bounding_box(
    coco_keypoints: List[List[float]],
    margin_ratio: float = 0.6,
) -> List[Tuple[int, int]]:
    """
    Estimate head bounding box from COCO face keypoints.

    The demo uses head_bounding_box_2d to crop face images for recognition:
        face_bbox_2d = np.array(body['head_bounding_box_2d'])
        x1 = face_bbox_2d[0][0]  # Top-left X
        x2 = face_bbox_2d[1][0]  # Top-right X
        y1 = face_bbox_2d[1][1] - 50  # Top Y
        y2 = face_bbox_2d[2][1]  # Bottom Y

    Format: 4 corners [(x1,y1), (x2,y1), (x2,y2), (x1,y2)]

    Args:
        coco_keypoints: COCO-17 keypoints list.
        margin_ratio: Extra margin as ratio of estimated head width.

    Returns:
        List of 4 (x, y) integer tuples forming the bounding box corners.
    """
    if len(coco_keypoints) < 5:
        return [(0, 0), (0, 0), (0, 0), (0, 0)]

    # Collect valid face keypoints
    face_indices = [NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR]
    valid_points = []
    for idx in face_indices:
        kp = coco_keypoints[idx]
        if kp[0] > 0 and kp[1] > 0:
            valid_points.append(kp)

    if len(valid_points) < 2:
        # Not enough points — return zero bbox
        return [(0, 0), (0, 0), (0, 0), (0, 0)]

    xs = [p[0] for p in valid_points]
    ys = [p[1] for p in valid_points]

    cx = np.mean(xs)
    cy = np.mean(ys)

    # Estimate head size from the spread of face keypoints
    width = max(xs) - min(xs)
    if width < 10:
        # Points are very close — use a default head size estimate
        width = 60.0

    height = width * 1.4  # Head is taller than wide
    margin = width * margin_ratio

    x1 = int(cx - width / 2 - margin)
    x2 = int(cx + width / 2 + margin)
    y1 = int(cy - height / 2 - margin)
    y2 = int(cy + height / 2 + margin)

    # 4 corners: top-left, top-right, bottom-right, bottom-left
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
