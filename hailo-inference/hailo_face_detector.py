#!/usr/bin/env python3
"""
Face detection using SCRFD on Hailo-10 with full landmark extraction.

Supports:
  - server: hailo_inference_server (TCP) — shares Hailo device
  - direct: HailoRT 5.x InferModel API — exclusive VDevice access

Outputs bounding boxes + 5-point facial landmarks (eyes, nose, mouth corners).
"""

import os
import sys
from typing import List, Optional, Tuple

import cv2
import numpy as np


# SCRFD 10g output tensor mapping (3 scales × 3 types)
# Each scale has 2 anchors
SCRFD_OUTPUTS = {
    # (score_name, bbox_name, landmark_name, stride, grid_size)
    "stride8":  {"score": "scrfd_10g/conv41", "bbox": "scrfd_10g/conv42", "lmk": "scrfd_10g/conv43", "stride": 8,  "grid": 80},
    "stride16": {"score": "scrfd_10g/conv49", "bbox": "scrfd_10g/conv50", "lmk": "scrfd_10g/conv51", "stride": 16, "grid": 40},
    "stride32": {"score": "scrfd_10g/conv56", "bbox": "scrfd_10g/conv57", "lmk": "scrfd_10g/conv58", "stride": 32, "grid": 20},
}

NUM_ANCHORS = 2  # SCRFD 10g uses 2 anchors per location


def _generate_anchors(grid_size: int, stride: int) -> np.ndarray:
    """Generate anchor centers for a given grid size and stride."""
    shifts_x = np.arange(grid_size) * stride
    shifts_y = np.arange(grid_size) * stride
    shift_x, shift_y = np.meshgrid(shifts_x, shifts_y)
    centers = np.stack([shift_x.ravel(), shift_y.ravel()], axis=1)  # (grid*grid, 2)
    # Repeat for each anchor
    centers = np.tile(centers, (1, NUM_ANCHORS)).reshape(-1, 2)  # (grid*grid*num_anchors, 2)
    return centers.astype(np.float32)


def _decode_scrfd(outputs: dict, input_size: int, score_threshold: float,
                   scale: float, pad_x: int, pad_y: int,
                   orig_w: int, orig_h: int) -> List[dict]:
    """Decode SCRFD multi-scale outputs into detections with landmarks.

    Returns:
        List of dicts with 'bbox' [x1,y1,x2,y2], 'score', 'landmarks' 5×2 array.
    """
    all_scores = []
    all_bboxes = []
    all_landmarks = []

    for key, cfg in SCRFD_OUTPUTS.items():
        stride = cfg["stride"]
        grid = cfg["grid"]

        score_raw = outputs.get(cfg["score"])
        bbox_raw = outputs.get(cfg["bbox"])
        lmk_raw = outputs.get(cfg["lmk"])

        if score_raw is None or bbox_raw is None:
            continue

        # Reshape: (grid, grid, num_anchors) → (grid*grid*num_anchors,)
        scores = score_raw.reshape(-1)

        # Reshape bbox: (grid, grid, num_anchors*4) → (grid*grid*num_anchors, 4)
        bboxes = bbox_raw.reshape(-1, 4)

        # Reshape landmarks: (grid, grid, num_anchors*10) → (grid*grid*num_anchors, 10)
        if lmk_raw is not None:
            landmarks = lmk_raw.reshape(-1, 10)
        else:
            landmarks = np.zeros((len(scores), 10), dtype=np.float32)

        # Filter by score threshold
        mask = scores > score_threshold
        if not mask.any():
            continue

        scores = scores[mask]
        bboxes = bboxes[mask]
        landmarks = landmarks[mask]

        # Generate anchor centers for this scale
        anchors = _generate_anchors(grid, stride)
        anchors = anchors[mask]

        # Decode bbox: distance from anchor center → absolute coords
        # SCRFD bbox format: [left, top, right, bottom] distances from anchor
        x1 = anchors[:, 0] - bboxes[:, 0] * stride
        y1 = anchors[:, 1] - bboxes[:, 1] * stride
        x2 = anchors[:, 0] + bboxes[:, 2] * stride
        y2 = anchors[:, 1] + bboxes[:, 3] * stride
        decoded_bboxes = np.stack([x1, y1, x2, y2], axis=1)

        # Decode landmarks: offset from anchor center
        decoded_lmks = np.zeros_like(landmarks)
        for i in range(5):
            decoded_lmks[:, i * 2] = anchors[:, 0] + landmarks[:, i * 2] * stride
            decoded_lmks[:, i * 2 + 1] = anchors[:, 1] + landmarks[:, i * 2 + 1] * stride

        all_scores.append(scores)
        all_bboxes.append(decoded_bboxes)
        all_landmarks.append(decoded_lmks)

    if not all_scores:
        return []

    scores = np.concatenate(all_scores)
    bboxes = np.concatenate(all_bboxes)
    landmarks = np.concatenate(all_landmarks)

    # NMS
    keep = _nms(bboxes, scores, iou_threshold=0.4)
    scores = scores[keep]
    bboxes = bboxes[keep]
    landmarks = landmarks[keep]

    # Convert from letterbox coords to original image coords
    detections = []
    for i in range(len(scores)):
        x1 = (bboxes[i, 0] - pad_x) / scale
        y1 = (bboxes[i, 1] - pad_y) / scale
        x2 = (bboxes[i, 2] - pad_x) / scale
        y2 = (bboxes[i, 3] - pad_y) / scale

        lmk = landmarks[i].reshape(5, 2)
        lmk[:, 0] = (lmk[:, 0] - pad_x) / scale
        lmk[:, 1] = (lmk[:, 1] - pad_y) / scale

        detections.append({
            "bbox": [
                max(0, int(x1)), max(0, int(y1)),
                min(orig_w, int(x2)), min(orig_h, int(y2)),
            ],
            "score": float(scores[i]),
            "landmarks": lmk.astype(np.float32),  # 5×2: [l_eye, r_eye, nose, l_mouth, r_mouth]
        })

    return detections


def _nms(bboxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
    """Non-Maximum Suppression."""
    x1, y1, x2, y2 = bboxes[:, 0], bboxes[:, 1], bboxes[:, 2], bboxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

        remaining = np.where(iou <= iou_threshold)[0]
        order = order[remaining + 1]

    return keep


class HailoFaceDetector:
    """SCRFD face detection on Hailo-10 with landmark extraction."""

    def __init__(self, hef_path: str = "", input_size: int = 640,
                 score_threshold: float = 0.5, device_id: Optional[str] = None,
                 use_server: bool = False, server_host: str = "localhost",
                 server_port: int = 8003):
        self.input_size = input_size
        self.score_threshold = score_threshold
        self._client = None
        self._infer_model = None
        self._configured = None
        self._ctx = None

        if use_server:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hailo-inference"))
            from hailo_inference_client import HailoInferenceClient
            self._client = HailoInferenceClient(host=server_host, port=server_port)
            print(f"[HAILO-FACE] Using inference server at {server_host}:{server_port}")
        else:
            try:
                from hailo_platform import VDevice, FormatType
            except ImportError:
                raise ImportError("hailo_platform not installed")

            if not os.path.exists(hef_path):
                raise FileNotFoundError(f"HEF not found: {hef_path}")

            from hailo_utils import detect_hailo_device
            if device_id is None:
                device_id = detect_hailo_device()

            if device_id:
                params = VDevice.create_params()
                params.device_ids = [device_id]
                self._vdevice = VDevice(params)
            else:
                self._vdevice = VDevice()

            self._infer_model = self._vdevice.create_infer_model(hef_path)
            self._infer_model.set_batch_size(1)
            for inp in self._infer_model.inputs:
                self._infer_model.input(inp.name).set_format_type(FormatType.FLOAT32)
            for out in self._infer_model.outputs:
                self._infer_model.output(out.name).set_format_type(FormatType.FLOAT32)
            self._ctx = self._infer_model.configure()
            self._configured = self._ctx.__enter__()
            print(f"[HAILO-FACE] Loaded: {hef_path}")

    def __del__(self):
        if self._ctx is not None:
            try:
                self._ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._client is not None:
            self._client.close()

    def detect(self, bgr_frame: np.ndarray) -> List[dict]:
        """Detect faces. Returns list of {bbox, score, landmarks(5×2)}."""
        orig_h, orig_w = bgr_frame.shape[:2]
        tensor, scale, pad_x, pad_y = self._preprocess(bgr_frame)

        if self._client is not None:
            outputs = self._client.infer("scrfd_10g", tensor)
        else:
            bindings = self._configured.create_bindings()
            input_name = self._infer_model.inputs[0].name
            bindings.input(input_name).set_buffer(tensor)
            out_bufs = {}
            for out in self._infer_model.outputs:
                buf = np.empty(tuple(out.shape), dtype=np.float32)
                bindings.output(out.name).set_buffer(buf)
                out_bufs[out.name] = buf
            self._configured.run([bindings], 5000)
            outputs = {name: bindings.output(name).get_buffer() for name in out_bufs}

        return _decode_scrfd(outputs, self.input_size, self.score_threshold,
                              scale, pad_x, pad_y, orig_w, orig_h)

    def _preprocess(self, bgr_frame: np.ndarray):
        h, w = bgr_frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_x = (self.input_size - new_w) // 2
        pad_y = (self.input_size - new_h) // 2

        resized = cv2.resize(bgr_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
        return canvas, scale, pad_x, pad_y
