#!/usr/bin/env python3
"""
Face detection using SCRFD on Hailo-10.

Supports two backends:
  - server: hailo_inference_server (TCP) — shares Hailo device with other services
  - direct: HailoRT 5.x InferModel API — exclusive VDevice access

HEF model: scrfd_10g from Hailo Model Zoo (auto-downloaded)
"""

import os
import sys
from typing import List, Optional

import cv2
import numpy as np


class HailoFaceDetector:
    """SCRFD face detection on Hailo-10 (via server or direct)."""

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
            # Use centralized inference server
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hailo-inference"))
            from hailo_inference_client import HailoInferenceClient
            self._client = HailoInferenceClient(host=server_host, port=server_port)
            print(f"[HAILO-FACE] Using inference server at {server_host}:{server_port}")
        else:
            # Direct VDevice access (HailoRT 5.x InferModel API)
            try:
                from hailo_platform import VDevice, FormatType
            except ImportError:
                raise ImportError(
                    "hailo_platform not installed. Install HailoRT: "
                    "https://hailo.ai/developer-zone/"
                )

            if not os.path.exists(hef_path):
                raise FileNotFoundError(f"Face detection HEF not found: {hef_path}")

            from hailo_utils import detect_hailo_device
            if device_id is None:
                device_id = detect_hailo_device()

            if device_id:
                params = VDevice.create_params()
                params.device_ids = [device_id]
                self._vdevice = VDevice(params)
                print(f"[HAILO-FACE] Using device: {device_id}")
            else:
                self._vdevice = VDevice()
                print("[HAILO-FACE] Using default device")

            self._infer_model = self._vdevice.create_infer_model(hef_path)
            self._infer_model.set_batch_size(1)
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
        """Detect faces in a BGR image.

        Returns:
            List of dicts with 'bbox' [x1, y1, x2, y2] and 'score'.
        """
        orig_h, orig_w = bgr_frame.shape[:2]
        tensor, scale, pad_x, pad_y = self._preprocess(bgr_frame)

        if self._client is not None:
            # Remote inference via TCP server
            outputs = self._client.infer("scrfd_10g", tensor)
        else:
            # Direct local inference
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

        return self._postprocess(outputs, orig_w, orig_h, scale, pad_x, pad_y)

    def _preprocess(self, bgr_frame: np.ndarray):
        h, w = bgr_frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_x = (self.input_size - new_w) // 2
        pad_y = (self.input_size - new_h) // 2

        resized = cv2.resize(bgr_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # HailoRT InferModel expects NHWC uint8 (quantizes internally).
        # No batch dimension, no normalization needed.
        return canvas, scale, pad_x, pad_y

    def _postprocess(self, outputs: dict, orig_w: int, orig_h: int,
                     scale: float, pad_x: int, pad_y: int) -> List[dict]:
        """Decode SCRFD output into face bounding boxes."""
        # Get the first (or only) output tensor
        out_name = list(outputs.keys())[0]
        raw = outputs[out_name]
        if isinstance(raw, list):
            raw = raw[0]
        raw = np.squeeze(raw)

        # SCRFD output: [N, 5] or [N, 15] (bbox + score + optional landmarks)
        if raw.ndim == 1:
            num_det = len(raw) // 5
            if num_det == 0:
                return []
            raw = raw[:num_det * 5].reshape(num_det, 5)
        elif raw.ndim == 2:
            if raw.shape[1] < 5:
                return []
        else:
            return []

        detections = []
        for det in raw:
            score = det[4] if len(det) >= 5 else det[-1]
            if score < self.score_threshold:
                continue

            x1_lb, y1_lb, x2_lb, y2_lb = det[0], det[1], det[2], det[3]
            x1 = (x1_lb - pad_x) / scale
            y1 = (y1_lb - pad_y) / scale
            x2 = (x2_lb - pad_x) / scale
            y2 = (y2_lb - pad_y) / scale

            detections.append({
                "bbox": [
                    max(0, int(x1)), max(0, int(y1)),
                    min(orig_w, int(x2)), min(orig_h, int(y2)),
                ],
                "score": float(score),
            })

        return detections
