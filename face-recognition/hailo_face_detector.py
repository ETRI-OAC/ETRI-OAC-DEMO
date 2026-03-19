#!/usr/bin/env python3
"""
Face detection using SCRFD on Hailo-10.

Replaces InsightFace's built-in SCRFD face detector with Hailo-accelerated
inference. The detected face bounding boxes are then used by InsightFace's
ArcFace embedding model (CPU) for recognition.

HEF model: scrfd_2.5g or scrfd_10g from Hailo Model Zoo
  hailo model-zoo download --model scrfd_2.5g --hw-arch hailo10h
"""

import os
from typing import List, Tuple, Optional

import cv2
import numpy as np

from hailo_utils import detect_hailo_device


class HailoFaceDetector:
    """SCRFD face detection on Hailo-10."""

    def __init__(self, hef_path: str, input_size: int = 640,
                 score_threshold: float = 0.5, device_id: Optional[str] = None):
        self.input_size = input_size
        self.score_threshold = score_threshold

        try:
            from hailo_platform import (
                HEF, VDevice, HailoStreamInterface,
                ConfigureParams, InputVStreamParams, OutputVStreamParams,
                FormatType,
            )
        except ImportError:
            raise ImportError(
                "hailo_platform not installed. Install HailoRT: "
                "https://hailo.ai/developer-zone/"
            )

        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"Face detection HEF not found: {hef_path}")

        self.hef = HEF(hef_path)

        # Auto-detect device if not specified
        if device_id is None:
            device_id = detect_hailo_device()

        if device_id:
            params = VDevice.create_params()
            params.device_ids = [device_id]
            self.target = VDevice(params)
            print(f"[HAILO-FACE] Using device: {device_id}")
        else:
            self.target = VDevice()
            print("[HAILO-FACE] Using default device")

        configure_params = ConfigureParams.create_from_hef(
            self.hef, interface=HailoStreamInterface.PCIe
        )
        self.network_group = self.target.configure(self.hef, configure_params)[0]

        self.input_vstream_info = self.hef.get_input_vstream_infos()
        self.output_vstream_info = self.hef.get_output_vstream_infos()

        self.input_params = InputVStreamParams.make_from_network_group(
            self.network_group, quantized=False, format_type=FormatType.FLOAT32
        )
        self.output_params = OutputVStreamParams.make_from_network_group(
            self.network_group, quantized=False, format_type=FormatType.FLOAT32
        )

        print(f"[HAILO-FACE] Loaded: {hef_path}")

    def detect(self, bgr_frame: np.ndarray) -> List[dict]:
        """Detect faces in a BGR image.

        Args:
            bgr_frame: (H, W, 3) uint8 BGR image.

        Returns:
            List of dicts with 'bbox' [x1, y1, x2, y2] and 'score'.
        """
        from hailo_platform import InferVStreams

        orig_h, orig_w = bgr_frame.shape[:2]

        # Preprocess: letterbox resize
        tensor, scale, pad_x, pad_y = self._preprocess(bgr_frame)

        # Infer
        input_name = self.input_vstream_info[0].name
        with InferVStreams(
            self.network_group, self.input_params, self.output_params
        ) as pipeline:
            output = pipeline.infer({input_name: tensor})

        # Postprocess
        return self._postprocess(output, orig_w, orig_h, scale, pad_x, pad_y)

    def _preprocess(self, bgr_frame: np.ndarray):
        h, w = bgr_frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_x = (self.input_size - new_w) // 2
        pad_y = (self.input_size - new_h) // 2

        resized = cv2.resize(bgr_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        tensor = canvas.astype(np.float32) / 255.0
        tensor = np.expand_dims(tensor, axis=0)
        return tensor, scale, pad_x, pad_y

    def _postprocess(self, output: dict, orig_w: int, orig_h: int,
                     scale: float, pad_x: int, pad_y: int) -> List[dict]:
        """Decode SCRFD output into face bounding boxes."""
        out_name = self.output_vstream_info[0].name
        raw = output[out_name]
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
