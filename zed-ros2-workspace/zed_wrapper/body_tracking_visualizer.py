#!/usr/bin/env python3
"""
Body tracking visualization utilities for ZED client.

This module provides functions to visualize body tracking data
from zed_client.py on images.
"""

import cv2
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

# Color palette for different body IDs
ID_COLORS = [
    (232, 176, 59),
    (175, 208, 25),
    (102, 205, 105),
    (185, 0, 255),
    (99, 107, 252)
]

# BODY_18 skeleton connections (bone pairs)
# Each tuple contains (start_keypoint_index, end_keypoint_index)
BODY_18_BONES = [
    (0, 1),   # Nose - Neck
    (1, 2),   # Neck - Right Shoulder
    (1, 5),   # Neck - Left Shoulder
    (2, 3),   # Right Shoulder - Right Elbow
    (3, 4),   # Right Elbow - Right Wrist
    (5, 6),   # Left Shoulder - Left Elbow
    (6, 7),   # Left Elbow - Left Wrist
    (1, 8),   # Neck - Right Hip
    (1, 11),  # Neck - Left Hip
    (8, 9),   # Right Hip - Right Knee
    (9, 10),  # Right Knee - Right Ankle
    (11, 12), # Left Hip - Left Knee
    (12, 13), # Left Knee - Left Ankle
    (0, 14),  # Nose - Right Eye
    (0, 15),  # Nose - Left Eye
    (14, 16), # Right Eye - Right Ear
    (15, 17), # Left Eye - Left Ear
]

# BODY_34 skeleton connections (if needed in future)
BODY_34_BONES = []  # TODO: Add if BODY_34 format is needed

# BODY_38 skeleton connections (if needed in future)
BODY_38_BONES = []  # TODO: Add if BODY_38 format is needed


def generate_color_id(idx: int) -> Tuple[int, int, int]:
    """
    Generate a color for a body ID.
    
    Args:
        idx: Body ID
        
    Returns:
        BGR color tuple
    """
    if idx < 0:
        return (36, 184, 236)  # Default color (BGR format)
    else:
        color_idx = idx % len(ID_COLORS)
        # Convert RGB to BGR for OpenCV
        return (ID_COLORS[color_idx][2], ID_COLORS[color_idx][1], ID_COLORS[color_idx][0])


def cvt(pt: List[float], img_scale: List[float]) -> List[float]:
    """
    Scale point coordinates.
    
    Args:
        pt: Point coordinates [x, y]
        img_scale: Scale factors [scale_x, scale_y]
        
    Returns:
        Scaled point coordinates
    """
    return [pt[0] * img_scale[0], pt[1] * img_scale[1]]


def render_skeleton(
    image: np.ndarray,
    img_scale: List[float],
    body: Dict[str, Any],
    color: Tuple[int, int, int],
    bones: List[Tuple[int, int]]
) -> None:
    """
    Render skeleton bones and joints on an image.
    
    Args:
        image: Image array to draw on (will be modified)
        img_scale: Scale factors [scale_x, scale_y]
        body: Body dictionary from client
        color: BGR color tuple for drawing
        bones: List of bone connections (keypoint index pairs)
    """
    keypoints_2d = body.get('keypoints_2d', [])
    if len(keypoints_2d) == 0:
        return
    
    h, w = image.shape[:2]
    
    # Draw skeleton bones
    for bone_start_idx, bone_end_idx in bones:
        if bone_start_idx < len(keypoints_2d) and bone_end_idx < len(keypoints_2d):
            kp_a_raw = keypoints_2d[bone_start_idx]
            kp_b_raw = keypoints_2d[bone_end_idx]
            
            # Skip if keypoints are invalid (zero or negative)
            if len(kp_a_raw) >= 2 and len(kp_b_raw) >= 2:
                if kp_a_raw[0] > 0 and kp_a_raw[1] > 0 and kp_b_raw[0] > 0 and kp_b_raw[1] > 0:
                    kp_a = cvt(kp_a_raw, img_scale)
                    kp_b = cvt(kp_b_raw, img_scale)
                    
                    # Check that keypoints are inside the image
                    if (0 < kp_a[0] < w and 0 < kp_a[1] < h and
                        0 < kp_b[0] < w and 0 < kp_b[1] < h):
                        cv2.line(
                            image,
                            (int(kp_a[0]), int(kp_a[1])),
                            (int(kp_b[0]), int(kp_b[1])),
                            color,
                            2,
                            cv2.LINE_AA
                        )
    
    # Draw skeleton joints
    for kp in keypoints_2d:
        if len(kp) >= 2 and kp[0] > 0 and kp[1] > 0:
            cv_kp = cvt(kp, img_scale)
            if 0 < cv_kp[0] < w and 0 < cv_kp[1] < h:
                cv2.circle(
                    image,
                    (int(cv_kp[0]), int(cv_kp[1])),
                    4,
                    color,
                    -1
                )


def render_bounding_box_2d(
    image: np.ndarray,
    img_scale: List[float],
    body: Dict[str, Any],
    color: Tuple[int, int, int]
) -> None:
    """
    Render 2D bounding box on an image.
    
    Args:
        image: Image array to draw on (will be modified)
        img_scale: Scale factors [scale_x, scale_y]
        body: Body dictionary from client
        color: BGR color tuple for drawing
    """
    bbox_2d = body.get('bounding_box_2d', [])
    if len(bbox_2d) != 4:
        return
    
    h, w = image.shape[:2]
    points = []
    
    for corner in bbox_2d:
        scaled_pt = cvt([corner[0], corner[1]], img_scale)
        if 0 < scaled_pt[0] < w and 0 < scaled_pt[1] < h:
            points.append((int(scaled_pt[0]), int(scaled_pt[1])))
    
    if len(points) == 4:
        # Draw bounding box
        for i in range(4):
            pt1 = points[i]
            pt2 = points[(i + 1) % 4]
            cv2.line(image, pt1, pt2, color, 2, cv2.LINE_AA)


def render_body_info(
    image: np.ndarray,
    body: Dict[str, Any],
    position: Tuple[int, int],
    color: Tuple[int, int, int]
) -> None:
    """
    Render body information text (ID, confidence) on image.
    
    Args:
        image: Image array to draw on (will be modified)
        body: Body dictionary from client
        position: (x, y) position to draw text
        color: BGR color tuple for text
    """
    body_id = body.get('id', -1)
    confidence = body.get('confidence', 0.0)
    
    text = f"ID: {body_id} ({confidence:.1f}%)"
    cv2.putText(
        image,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
        cv2.LINE_AA
    )


def visualize_bodies_2d(
    image: np.ndarray,
    bodies: List[Dict[str, Any]],
    body_format: int = 18,
    img_scale: Optional[List[float]] = None,
    draw_skeleton: bool = True,
    draw_bbox: bool = True,
    draw_info: bool = True
) -> np.ndarray:
    """
    Visualize body tracking data on a 2D image.
    
    Args:
        image: Image array (H, W, 3) uint8 BGR format
        bodies: List of body dictionaries from zed_client
        body_format: Body format (18, 34, or 38 keypoints)
        img_scale: Scale factors [scale_x, scale_y]. If None, uses [1.0, 1.0]
        draw_skeleton: Whether to draw skeleton
        draw_bbox: Whether to draw bounding box
        draw_info: Whether to draw body ID and confidence
        
    Returns:
        Image with visualizations drawn (same array, modified in place)
    """
    if image is None or len(bodies) == 0:
        return image
    
    if img_scale is None:
        img_scale = [1.0, 1.0]
    
    # Select bones based on body format
    if body_format == 18:
        bones = BODY_18_BONES
    elif body_format == 34:
        bones = BODY_34_BONES
    elif body_format == 38:
        bones = BODY_38_BONES
    else:
        bones = BODY_18_BONES  # Default
    
    # Create overlay for transparency effect
    overlay = image.copy()
    
    # Render each body
    for body in bodies:
        try:
            body_id = body.get('id', -1)
            color = generate_color_id(body_id)
            
            # Draw skeleton
            if draw_skeleton:
                render_skeleton(image, img_scale, body, color, bones)
            
            # Draw bounding box
            if draw_bbox:
                render_bounding_box_2d(image, img_scale, body, color)
            
            # Draw body info
            if draw_info:
                bbox_2d = body.get('bounding_box_2d', [])
                if len(bbox_2d) >= 1:
                    # Draw info at top-left corner of bounding box
                    top_left = cvt([bbox_2d[0][0], bbox_2d[0][1]], img_scale)
                    render_body_info(image, body, (int(top_left[0]), int(top_left[1]) - 10), color)
        except Exception as e:
            print(f"[VISUALIZER] Error rendering body {body.get('id', 'unknown')}: {e}")
            continue
    
    # Apply transparency overlay
    cv2.addWeighted(image, 0.9, overlay, 0.1, 0.0, image)
    
    return image


def visualize_bodies_simple(
    image: np.ndarray,
    bodies: List[Dict[str, Any]],
    body_format: int = 18
) -> np.ndarray:
    """
    Simple visualization wrapper - just draws skeletons and bounding boxes.
    
    Args:
        image: Image array (H, W, 3) uint8 BGR format
        bodies: List of body dictionaries from zed_client
        body_format: Body format (18, 34, or 38 keypoints)
        
    Returns:
        Image with visualizations drawn
    """
    return visualize_bodies_2d(
        image,
        bodies,
        body_format=body_format,
        draw_skeleton=True,
        draw_bbox=True,
        draw_info=True
    )
