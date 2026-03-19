#!/usr/bin/env python3
"""
OAK-D Pro W (camera) + Hailo-10 (pose estimation) server using shared memory.

Drop-in replacement for zed_server.py:
  - OAK-D Pro W: RGB frames + stereo depth via DepthAI (no on-device NN)
  - Hailo-10:  YOLOv8n-pose inference via HailoRT for body tracking
  - Output:    Same shared memory binary format as zed_server.py

zed_client.py and all demo scripts work without modification.
"""

import struct
import time
import os
from typing import Tuple, Optional, List

import multiprocessing.shared_memory as shm
import numpy as np
import cv2

try:
    import depthai as dai
except ImportError:
    raise ImportError("depthai not installed. Run: pip install depthai")

from person_tracker import PersonTracker
from head_pose_estimator import estimate_head_orientation, estimate_head_bounding_box
from hailo_utils import detect_hailo_device
from hailo_model_downloader import get_hef_path

# ---------------------------------------------------------------------------
# Shared memory constants (must match zed_client.py exactly)
# ---------------------------------------------------------------------------
SHM_IMAGE_NAME = "zed_image_shm"
SHM_BODY_NAME = "zed_body_shm"

# Image header: 7 × uint32 = 28 bytes
IMAGE_HEADER_BYTES = 7 * 4
IMAGE_MAGIC = 0x5A494D47  # 'ZIMG'
IMAGE_LOCK_UNLOCKED = 0
IMAGE_LOCK_LOCKED = 1

# Body header: 5 × uint32 = 20 bytes
BODY_HEADER_BYTES = 5 * 4
BODY_MAGIC = 0x5A424F44  # 'ZBOD'
BODY_LOCK_UNLOCKED = 0
BODY_LOCK_LOCKED = 1

# BODY_34 format code (must match zed_client expectation)
BODY_FORMAT_34 = 34

# COCO-17 keypoint indices
COCO_NOSE = 0
COCO_LEFT_EYE = 1
COCO_RIGHT_EYE = 2
COCO_LEFT_EAR = 3
COCO_RIGHT_EAR = 4

MAX_KEYPOINTS = 34  # SHM slot count (BODY_34 compat)
MAX_BODIES = 10

# Per-body serialized size (must match zed_client._calculate_body_field_offsets)
BODY_FIXED_SIZE = 360
KEYPOINT_2D_SIZE = MAX_KEYPOINTS * 2 * 4
KEYPOINT_3D_SIZE = MAX_KEYPOINTS * 3 * 4
BODY_SIZE = BODY_FIXED_SIZE + KEYPOINT_2D_SIZE + KEYPOINT_3D_SIZE


def allocate_size(width: int, height: int, channels: int, bytes_per_channel: int = 1) -> int:
    return IMAGE_HEADER_BYTES + width * height * channels * bytes_per_channel


# ---------------------------------------------------------------------------
# Hailo-10 pose estimator
# ---------------------------------------------------------------------------
class HailoPoseEstimator:
    """YOLOv8s-pose inference on Hailo-10 via HailoRT."""

    def __init__(self, hef_path: str, input_size: int = 640, score_threshold: float = 0.3,
                 device_id: Optional[str] = None):
        self.input_size = input_size
        self.score_threshold = score_threshold

        try:
            from hailo_platform import (
                HEF, VDevice, HailoStreamInterface,
                InferVStreams, ConfigureParams, InputVStreamParams, OutputVStreamParams,
                FormatType,
            )
        except ImportError:
            raise ImportError(
                "hailo_platform not installed. Install HailoRT: "
                "https://hailo.ai/developer-zone/"
            )

        self._hailo = __import__("hailo_platform")

        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"Hailo HEF model not found: {hef_path}")

        self.hef = HEF(hef_path)

        # Select specific Hailo device by ID (e.g. "0000:01:00.0")
        # When None, uses first available device
        if device_id:
            params = VDevice.create_params()
            params.device_ids = [device_id]
            self.target = VDevice(params)
            print(f"[HAILO] Using device: {device_id}")
        else:
            self.target = VDevice()

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

        print(f"[HAILO] Loaded model: {hef_path}")
        print(f"[HAILO] Input: {self.input_vstream_info[0].shape}, "
              f"Output: {[o.shape for o in self.output_vstream_info]}")

    def infer(self, bgr_frame: np.ndarray) -> List[dict]:
        """Run pose estimation on a BGR frame.

        Args:
            bgr_frame: (H, W, 3) uint8 BGR image.

        Returns:
            List of detection dicts with 'keypoints_2d', 'bbox', 'score'.
        """
        from hailo_platform import InferVStreams

        orig_h, orig_w = bgr_frame.shape[:2]

        # Preprocess: resize + pad (letterbox) to input_size × input_size
        input_tensor, scale, pad_x, pad_y = self._preprocess(bgr_frame)

        # Run inference
        with InferVStreams(
            self.network_group, self.input_params, self.output_params
        ) as pipeline:
            input_dict = {self.input_vstream_info[0].name: input_tensor}
            output = pipeline.infer(input_dict)

        # Post-process: decode YOLOv8-pose output
        detections = self._postprocess(output, orig_w, orig_h, scale, pad_x, pad_y)
        return detections

    def _preprocess(self, bgr_frame: np.ndarray):
        """Letterbox resize to input_size × input_size, return (tensor, scale, pad_x, pad_y)."""
        h, w = bgr_frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_x = (self.input_size - new_w) // 2
        pad_y = (self.input_size - new_h) // 2

        resized = cv2.resize(bgr_frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # Normalize to [0, 1] float32, NHWC
        tensor = canvas.astype(np.float32) / 255.0
        tensor = np.expand_dims(tensor, axis=0)  # (1, H, W, 3)
        return tensor, scale, pad_x, pad_y

    def _postprocess(
        self, output: dict, orig_w: int, orig_h: int,
        scale: float, pad_x: int, pad_y: int,
    ) -> List[dict]:
        """Decode YOLOv8-pose output tensors into detection dicts.

        YOLOv8-pose output format (after NMS):
        Each detection: [x_center, y_center, w, h, confidence,
                         kp0_x, kp0_y, kp0_conf, kp1_x, kp1_y, kp1_conf, ...]
        17 keypoints × 3 = 51 values + 5 bbox values = 56 per detection.
        """
        # Get the output tensor (exact shape depends on HEF compilation)
        out_name = self.output_vstream_info[0].name
        raw = output[out_name]
        if isinstance(raw, list):
            raw = raw[0]
        raw = np.squeeze(raw)  # Remove batch dim if present

        # Handle different output layouts
        if raw.ndim == 1:
            # Flat output — reshape assuming 56 values per detection
            num_det = len(raw) // 56
            if num_det == 0:
                return []
            raw = raw[:num_det * 56].reshape(num_det, 56)
        elif raw.ndim == 2:
            if raw.shape[1] == 56:
                pass  # Already (N, 56)
            elif raw.shape[0] == 56:
                raw = raw.T  # Transpose (56, N) → (N, 56)
            else:
                return []
        else:
            return []

        detections = []
        for det in raw:
            conf = det[4]
            if conf < self.score_threshold:
                continue

            # Bbox in letterbox coordinates
            cx, cy, bw, bh = det[0], det[1], det[2], det[3]
            x1_lb = cx - bw / 2
            y1_lb = cy - bh / 2
            x2_lb = cx + bw / 2
            y2_lb = cy + bh / 2

            # Reverse letterbox → original coordinates
            x1 = (x1_lb - pad_x) / scale
            y1 = (y1_lb - pad_y) / scale
            x2 = (x2_lb - pad_x) / scale
            y2 = (y2_lb - pad_y) / scale

            # Keypoints (17 × 3: x, y, conf in letterbox coords)
            keypoints_2d = []
            for kp_idx in range(17):
                kx_lb = det[5 + kp_idx * 3 + 0]
                ky_lb = det[5 + kp_idx * 3 + 1]
                ks = det[5 + kp_idx * 3 + 2]
                if ks > 0.3:
                    kx = (kx_lb - pad_x) / scale
                    ky = (ky_lb - pad_y) / scale
                    keypoints_2d.append([kx, ky])
                else:
                    keypoints_2d.append([0.0, 0.0])

            detections.append({
                "keypoints_2d": keypoints_2d,
                "bbox": [
                    max(0, x1), max(0, y1),
                    min(orig_w, x2), min(orig_h, y2),
                ],
                "score": float(conf),
            })

        return detections


# ---------------------------------------------------------------------------
# Main server
# ---------------------------------------------------------------------------
class OakImageServer:
    def __init__(
        self,
        shm_image_name: str = SHM_IMAGE_NAME,
        shm_body_name: str = SHM_BODY_NAME,
        hef_path: Optional[str] = None,
        hailo_device_id: Optional[str] = None,
        hailo_device_index: int = 0,
        debug: bool = False,
    ):
        self.shm_image_name = shm_image_name
        self.shm_body_name = shm_body_name
        self.debug = debug

        self.frame_counter = 0
        self.shm_image_block: Optional[shm.SharedMemory] = None
        self.shm_body_block: Optional[shm.SharedMemory] = None
        self.frame_shape: Optional[Tuple[int, int, int]] = None

        # Camera intrinsics (populated after device opens)
        self.fx: float = 0.0
        self.fy: float = 0.0
        self.cx: float = 0.0
        self.cy: float = 0.0

        # Person tracker for persistent IDs
        self.tracker = PersonTracker()

        # Hailo-10 pose estimator (auto-detect device + auto-download model)
        self.pose_estimator: Optional[HailoPoseEstimator] = None
        if hef_path is None:
            # Auto-download YOLOv8s-pose HEF
            hef_path = get_hef_path("yolov8s_pose")
        if hef_path:
            if hailo_device_id is None:
                hailo_device_id = detect_hailo_device(device_index=hailo_device_index)
            if hailo_device_id is not None or hailo_device_index == 0:
                self.pose_estimator = HailoPoseEstimator(hef_path, device_id=hailo_device_id)

        # FPS tracking
        self._last_fps_time: Optional[float] = None
        self._frame_count_for_fps = 0

    # ------------------------------------------------------------------
    # OAK-D pipeline (camera only — no NN)
    # ------------------------------------------------------------------
    def _build_pipeline(self) -> dai.Pipeline:
        pipeline = dai.Pipeline()

        # --- Color camera ---
        cam_rgb = pipeline.create(dai.node.ColorCamera)
        cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam_rgb.setFps(30)
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        cam_rgb.setIspScale(1, 1)

        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.isp.link(xout_rgb.input)

        # --- Stereo depth (aligned to RGB) ---
        mono_left = pipeline.create(dai.node.MonoCamera)
        mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_left.setFps(30)
        mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)

        mono_right = pipeline.create(dai.node.MonoCamera)
        mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_right.setFps(30)
        mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)

        stereo = pipeline.create(dai.node.StereoDepth)
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
        stereo.setOutputSize(cam_rgb.getIspWidth(), cam_rgb.getIspHeight())
        stereo.setSubpixel(True)

        mono_left.out.link(stereo.left)
        mono_right.out.link(stereo.right)

        xout_depth = pipeline.create(dai.node.XLinkOut)
        xout_depth.setStreamName("depth")
        stereo.depth.link(xout_depth.input)

        return pipeline

    def _populate_intrinsics(self, device: dai.Device, width: int, height: int) -> None:
        if self.fx > 0:
            return
        try:
            calib = device.readCalibration()
            m = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, width, height)
            self.fx, self.fy = m[0][0], m[1][1]
            self.cx, self.cy = m[0][2], m[1][2]
            print(f"[OAK] Intrinsics: fx={self.fx:.1f} fy={self.fy:.1f} "
                  f"cx={self.cx:.1f} cy={self.cy:.1f}")
        except Exception as e:
            self.fx = width * 0.7
            self.fy = width * 0.7
            self.cx = width / 2.0
            self.cy = height / 2.0
            print(f"[OAK] Warning: Could not read intrinsics ({e}), using approximation")

    # ------------------------------------------------------------------
    # Shared memory (same protocol as zed_server.py)
    # ------------------------------------------------------------------
    def _init_image_shared_memory(self, width: int, height: int, channels: int = 3) -> None:
        self.frame_shape = (height, width, channels)
        total_size = allocate_size(width, height, channels)

        try:
            self.shm_image_block = shm.SharedMemory(
                name=self.shm_image_name, create=True, size=total_size
            )
            print(f"[SHM] Created shared memory '{self.shm_image_name}' ({total_size} bytes)")
        except FileExistsError:
            existing = shm.SharedMemory(name=self.shm_image_name, create=False)
            if existing.size < total_size:
                existing.close()
                raise RuntimeError(
                    f"Existing shared memory '{self.shm_image_name}' too small "
                    f"({existing.size} < {total_size})"
                )
            self.shm_image_block = existing
            print(f"[SHM] Attached to existing '{self.shm_image_name}' ({existing.size} bytes)")

        try:
            os.chmod(f"/dev/shm/{self.shm_image_name}", 0o666)
        except (FileNotFoundError, PermissionError):
            pass

        buf = self.shm_image_block.buf
        buf[0:4] = struct.pack("<I", IMAGE_LOCK_UNLOCKED)
        header = struct.pack("<6I", IMAGE_MAGIC, width, height, channels, 0, 0)
        buf[4:IMAGE_HEADER_BYTES] = header
        print(f"[SHM] Header initialized for {width}x{height}x{channels} uint8")

    def _init_body_shared_memory(self) -> None:
        total_size = BODY_HEADER_BYTES + MAX_BODIES * BODY_SIZE

        try:
            self.shm_body_block = shm.SharedMemory(
                name=self.shm_body_name, create=True, size=total_size
            )
            print(f"[SHM] Created body tracking shared memory '{self.shm_body_name}' "
                  f"({total_size} bytes)")
        except FileExistsError:
            existing = shm.SharedMemory(name=self.shm_body_name, create=False)
            if existing.size < total_size:
                existing.close()
                raise RuntimeError(
                    f"Existing body shared memory too small ({existing.size} < {total_size})"
                )
            self.shm_body_block = existing
            print(f"[SHM] Attached to existing '{self.shm_body_name}' ({existing.size} bytes)")

        try:
            os.chmod(f"/dev/shm/{self.shm_body_name}", 0o666)
        except (FileNotFoundError, PermissionError):
            pass

        buf = self.shm_body_block.buf
        buf[0:4] = struct.pack("<I", BODY_LOCK_UNLOCKED)
        header = struct.pack("<IIII", BODY_MAGIC, 0, 0, BODY_FORMAT_34)
        buf[4:BODY_HEADER_BYTES] = header
        print("[SHM] Body tracking header initialized")

    def _write_image_data(self, image_array: np.ndarray) -> None:
        if self.shm_image_block is None:
            return
        buf = self.shm_image_block.buf
        h, w, c = self.frame_shape

        array = np.asarray(image_array, dtype=np.uint8)
        if array.shape[-1] == 4:
            array = array[..., :3]
        if array.shape != (h, w, c):
            array = array.reshape((h, w, c))

        buf[0:4] = struct.pack("<I", IMAGE_LOCK_LOCKED)
        try:
            pixel_bytes = array.tobytes(order="C")
            data_offset = IMAGE_HEADER_BYTES
            buf[data_offset:data_offset + len(pixel_bytes)] = pixel_bytes
            self.frame_counter += 1
            buf[6 * 4:7 * 4] = struct.pack("<I", self.frame_counter)
        finally:
            buf[0:4] = struct.pack("<I", IMAGE_LOCK_UNLOCKED)

    # ------------------------------------------------------------------
    # Body tracking serialization (binary-compatible with zed_client.py)
    # ------------------------------------------------------------------
    def _serialize_body(self, body: dict) -> bytes:
        data = b""

        data += struct.pack("<I", body.get("id", 0))
        data += struct.pack("<f", body.get("confidence", 0.0))
        pos = body.get("position", [0.0, 0.0, 0.0])
        data += struct.pack("<fff", *pos[:3])
        data += struct.pack("<ffffff", *([0.0] * 6))  # covariance
        data += struct.pack("<fff", 0.0, 0.0, 0.0)    # velocity
        data += struct.pack("<bbH", 1, 0, 0)           # tracking/action state

        data += struct.pack("<8I", *([0] * 8))         # bbox_2d
        data += struct.pack("<24f", *([0.0] * 24))     # bbox_3d
        data += struct.pack("<fff", 0.0, 0.0, 0.0)     # dimensions

        # head_bounding_box_2d — USED
        head_bbox = body.get("head_bounding_box_2d", [(0, 0)] * 4)
        bbox_values = []
        for corner in head_bbox[:4]:
            bbox_values.extend([int(corner[0]), int(corner[1])])
        data += struct.pack("<8I", *bbox_values[:8])

        data += struct.pack("<24f", *([0.0] * 24))     # head_bbox_3d

        # head_position — USED
        head_pos = body.get("head_position", [0.0, 0.0, 0.0])
        data += struct.pack("<fff", *head_pos[:3])

        # head_orientation — USED
        head_orient = body.get("head_orientation", [0.0, 0.0, 0.0, 1.0])
        data += struct.pack("<ffff", *head_orient[:4])

        # keypoints
        kp_2d = body.get("keypoints_2d", [])
        num_kp = min(len(kp_2d), MAX_KEYPOINTS)
        data += struct.pack("<I", num_kp)

        for i in range(MAX_KEYPOINTS):
            if i < len(kp_2d):
                data += struct.pack("<ff", float(kp_2d[i][0]), float(kp_2d[i][1]))
            else:
                data += struct.pack("<ff", 0.0, 0.0)

        kp_3d = body.get("keypoints_3d", [])
        for i in range(MAX_KEYPOINTS):
            if i < len(kp_3d):
                data += struct.pack("<fff", float(kp_3d[i][0]), float(kp_3d[i][1]), float(kp_3d[i][2]))
            else:
                data += struct.pack("<fff", 0.0, 0.0, 0.0)

        return data

    def _write_body_data(self, bodies: List[dict]) -> None:
        if self.shm_body_block is None:
            return
        buf = self.shm_body_block.buf
        num_bodies = min(len(bodies), MAX_BODIES)

        body_bytes = b"".join(self._serialize_body(b) for b in bodies[:num_bodies])

        buf[0:4] = struct.pack("<I", BODY_LOCK_LOCKED)
        try:
            header = struct.pack("<IIII", BODY_MAGIC, self.frame_counter,
                                 num_bodies, BODY_FORMAT_34)
            buf[4:BODY_HEADER_BYTES] = header
            if len(body_bytes) > 0:
                buf[BODY_HEADER_BYTES:BODY_HEADER_BYTES + len(body_bytes)] = body_bytes
        finally:
            buf[0:4] = struct.pack("<I", BODY_LOCK_UNLOCKED)

    # ------------------------------------------------------------------
    # Detection → body dict conversion
    # ------------------------------------------------------------------
    def _process_detections(
        self, raw_detections: List[dict], depth_frame: Optional[np.ndarray]
    ) -> List[dict]:
        bboxes = [d["bbox"] for d in raw_detections]
        tracked_ids = self.tracker.update(bboxes)

        bodies = []
        for det, track_id in zip(raw_detections, tracked_ids):
            coco_kps = det["keypoints_2d"]

            # Pad COCO-17 to 34 slots (index 0 = NOSE, already correct)
            kp_2d_34 = list(coco_kps) + [[0.0, 0.0]] * (MAX_KEYPOINTS - len(coco_kps))

            # head_position from nose + depth
            nose = coco_kps[COCO_NOSE]
            head_position = [0.0, 0.0, 0.0]
            if depth_frame is not None and nose[0] > 0 and nose[1] > 0:
                nx = min(max(int(nose[0]), 0), depth_frame.shape[1] - 1)
                ny = min(max(int(nose[1]), 0), depth_frame.shape[0] - 1)
                y_lo, y_hi = max(0, ny - 2), min(depth_frame.shape[0], ny + 3)
                x_lo, x_hi = max(0, nx - 2), min(depth_frame.shape[1], nx + 3)
                patch = depth_frame[y_lo:y_hi, x_lo:x_hi]
                valid = patch[patch > 0]
                if len(valid) > 0:
                    Z = float(np.median(valid)) / 1000.0
                    X = (nose[0] - self.cx) * Z / self.fx
                    Y = (nose[1] - self.cy) * Z / self.fy
                    head_position = [Z, -X, -Y]  # OAK → ZED coord transform

            bodies.append({
                "id": track_id,
                "confidence": det["score"] * 100.0,
                "position": [0.0, 0.0, 0.0],
                "head_position": head_position,
                "head_orientation": estimate_head_orientation(coco_kps),
                "head_bounding_box_2d": estimate_head_bounding_box(coco_kps),
                "keypoints_2d": kp_2d_34,
                "keypoints_3d": [[0.0, 0.0, 0.0]] * MAX_KEYPOINTS,
            })

        return bodies

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        pipeline = self._build_pipeline()

        with dai.Device(pipeline) as device:
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_depth = device.getOutputQueue(name="depth", maxSize=4, blocking=False)

            # Wait for first frame
            print("[OAK] Waiting for first frame...")
            first_rgb = q_rgb.get()
            frame = first_rgb.getCvFrame()
            h, w = frame.shape[:2]
            print(f"[OAK] Image size: {w}x{h}x3")

            self._populate_intrinsics(device, w, h)
            self._init_image_shared_memory(w, h, 3)
            self._init_body_shared_memory()
            self._write_image_data(frame)

            if self.pose_estimator:
                print("[SERVER] Pose estimation: Hailo-10")
            else:
                print("[SERVER] Pose estimation: disabled (camera only mode)")

            print(f"[SERVER] Publishing to '{self.shm_image_name}' + '{self.shm_body_name}'")
            print("[SERVER] Ctrl+C to stop.")

            try:
                while True:
                    in_rgb = q_rgb.tryGet()
                    if in_rgb is None:
                        time.sleep(0.001)
                        continue

                    frame = in_rgb.getCvFrame()
                    self._write_image_data(frame)

                    # Depth
                    depth_frame = None
                    in_depth = q_depth.tryGet()
                    if in_depth is not None:
                        depth_frame = in_depth.getFrame()

                    # Pose estimation on Hailo-10
                    bodies = []
                    if self.pose_estimator is not None:
                        raw_dets = self.pose_estimator.infer(frame)
                        bodies = self._process_detections(raw_dets, depth_frame)

                    self._write_body_data(bodies)

                    # FPS
                    if self.debug:
                        if self._last_fps_time is None:
                            self._last_fps_time = time.time()
                            self._frame_count_for_fps = 0
                        self._frame_count_for_fps += 1
                        now = time.time()
                        elapsed = now - self._last_fps_time
                        if elapsed >= 1.0:
                            fps = self._frame_count_for_fps / elapsed
                            print(f"[DEBUG] {len(bodies)} person(s), FPS: {fps:.2f}")
                            self._last_fps_time = now
                            self._frame_count_for_fps = 0

            except KeyboardInterrupt:
                print("\n[SERVER] Stopping...")
            finally:
                self.close()

    def close(self) -> None:
        print("[OAK] Closing camera.")
        for block in (self.shm_image_block, self.shm_body_block):
            if block is not None:
                try:
                    block.close()
                except FileNotFoundError:
                    pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OAK-D Pro W + Hailo-10 camera server")
    parser.add_argument("--hef", type=str, default=None,
                        help="Path to YOLOv8s-pose .hef model for Hailo-10")
    parser.add_argument("--hailo-device", type=str, default=None,
                        help="Hailo device ID (e.g. '0000:02:00.0'). Default: auto-detect")
    parser.add_argument("--hailo-index", type=int, default=0,
                        help="Hailo device index when multiple present (default: 0)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable FPS debug output")
    args = parser.parse_args()

    server = OakImageServer(hef_path=args.hef, hailo_device_id=args.hailo_device,
                            hailo_device_index=args.hailo_index, debug=args.debug)
    server.run()


if __name__ == "__main__":
    main()
