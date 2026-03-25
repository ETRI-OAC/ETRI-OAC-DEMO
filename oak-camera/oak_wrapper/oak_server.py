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
import sys
import time
import os
from typing import Tuple, Optional, List

import multiprocessing.shared_memory as shm
import numpy as np
import cv2

try:
    import depthai as dai
except ImportError:
    raise ImportError("depthai not installed. Run: pip install depthai (가상환경 활성화 또는 Docker 내부에서 실행)")

from person_tracker import PersonTracker
from head_pose_estimator import estimate_head_orientation, estimate_head_bounding_box
from hailo_utils import detect_hailo_device, is_hailo_available
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
# Hailo-10 pose estimator  (HailoRT 5.x InferModel API)
# ---------------------------------------------------------------------------
class HailoPoseEstimator:
    """YOLOv8m-pose inference via hailo_inference_server (TCP client) or direct VDevice.

    Output tensors (9 total, no built-in NMS):
      stride 8  (80×80): conv59 bbox[64], conv60 cls[1], conv61 kpt[51]
      stride 16 (40×40): conv75 bbox[64], conv76 cls[1], conv77 kpt[51]
      stride 32 (20×20): conv90 bbox[64], conv91 cls[1], conv92 kpt[51]
    """

    _REG_MAX = 16      # DFL bins
    _NUM_KPT = 17      # COCO keypoints

    # (bbox_name, cls_name, kpt_name) per stride
    _SCALE_OUTPUTS = {
        8:  ("yolov8m_pose/conv59", "yolov8m_pose/conv60", "yolov8m_pose/conv61"),
        16: ("yolov8m_pose/conv75", "yolov8m_pose/conv76", "yolov8m_pose/conv77"),
        32: ("yolov8m_pose/conv90", "yolov8m_pose/conv91", "yolov8m_pose/conv92"),
    }

    def __init__(self, hef_path: str, input_size: int = 640,
                 score_threshold: float = 0.3, nms_iou: float = 0.45,
                 device_id: Optional[str] = None,
                 use_server: bool = False, server_host: str = "localhost",
                 server_port: int = 8003):
        self.input_size = input_size
        self.score_threshold = score_threshold
        self.nms_iou = nms_iou
        self._client = None
        self._vdevice = None
        self._infer_model = None
        self._ctx = None
        self._configured = None

        if use_server:
            # Use centralized inference server (shares Hailo with other services)
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hailo-inference"))
            from hailo_inference_client import HailoInferenceClient
            self._client = HailoInferenceClient(host=server_host, port=server_port)
            print(f"[HAILO] Using inference server at {server_host}:{server_port}")
        else:
            # Direct VDevice access (exclusive Hailo ownership)
            try:
                from hailo_platform import VDevice, FormatType
            except ImportError:
                raise ImportError(
                    "hailo_platform not installed. Install HailoRT: "
                    "https://hailo.ai/developer-zone/"
                )

            if not os.path.exists(hef_path):
                raise FileNotFoundError(f"Hailo HEF model not found: {hef_path}")

            if device_id:
                params = VDevice.create_params()
                params.device_ids = [device_id]
                self._vdevice = VDevice(params)
                print(f"[HAILO] Using device: {device_id}")
            else:
                self._vdevice = VDevice()

            self._infer_model = self._vdevice.create_infer_model(hef_path)
            self._infer_model.set_batch_size(1)

            for out in self._infer_model.outputs:
                self._infer_model.output(out.name).set_format_type(FormatType.FLOAT32)

            self._ctx = self._infer_model.configure()
            self._configured = self._ctx.__enter__()
            print(f"[HAILO] Loaded model: {hef_path}")

    def __del__(self):
        if self._ctx is not None:
            try:
                self._ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._client is not None:
            self._client.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def infer(self, bgr_frame: np.ndarray) -> List[dict]:
        """Run pose estimation. Returns list of {bbox, score, keypoints_2d}."""
        orig_h, orig_w = bgr_frame.shape[:2]
        tensor, scale, pad_x, pad_y = self._preprocess(bgr_frame)

        if self._client is not None:
            # Remote inference via TCP server
            outputs = self._client.infer("yolov8m_pose", tensor)
        else:
            # Direct local inference
            bindings = self._configured.create_bindings()
            input_name = self._infer_model.inputs[0].name
            bindings.input(input_name).set_buffer(tensor)

            out_bufs: dict = {}
            for out in self._infer_model.outputs:
                buf = np.empty(tuple(out.shape), dtype=np.float32)
                bindings.output(out.name).set_buffer(buf)
                out_bufs[out.name] = buf

            self._configured.run([bindings], 5000)
            outputs = {name: bindings.output(name).get_buffer() for name in out_bufs}

        all_dets: List[dict] = []
        for stride, (bn, cn, kn) in self._SCALE_OUTPUTS.items():
            all_dets.extend(
                self._decode_scale(outputs[bn], outputs[cn], outputs[kn],
                                   stride, orig_w, orig_h, scale, pad_x, pad_y)
            )
        return self._nms(all_dets)

    # ------------------------------------------------------------------
    # Pre / post processing
    # ------------------------------------------------------------------
    def _preprocess(self, bgr_frame: np.ndarray):
        h, w = bgr_frame.shape[:2]
        scale = min(self.input_size / w, self.input_size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        pad_x = (self.input_size - new_w) // 2
        pad_y = (self.input_size - new_h) // 2

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
        # NHWC uint8 — HailoRT quantizes internally
        return canvas, scale, pad_x, pad_y

    def _dfl(self, pred: np.ndarray) -> np.ndarray:
        """Distribution Focal Loss decode: [N, 64] → [N, 4] distances."""
        n = pred.shape[0]
        p = pred.reshape(n, 4, self._REG_MAX).astype(np.float32)
        p -= p.max(axis=2, keepdims=True)
        exp = np.exp(p)
        soft = exp / (exp.sum(axis=2, keepdims=True) + 1e-9)
        w = np.arange(self._REG_MAX, dtype=np.float32)
        return (soft * w).sum(axis=2)  # [N, 4]

    def _decode_scale(self, bbox_raw, cls_raw, kpt_raw, stride,
                      orig_w, orig_h, scale, pad_x, pad_y) -> List[dict]:
        h, w = bbox_raw.shape[:2]
        n = h * w

        # Hailo HEF already applies sigmoid to cls outputs (FormatType.FLOAT32
        # dequantizes to probabilities, NOT raw logits). Using sigmoid again would
        # convert near-zero values to ~0.5 and flood detections.
        scores = cls_raw.reshape(n).astype(np.float32)
        mask = scores > self.score_threshold
        if not mask.any():
            return []

        # Anchor grid centers in feature-map coords
        ys = np.arange(h, dtype=np.float32) + 0.5
        xs = np.arange(w, dtype=np.float32) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        anchors = np.stack([gx.ravel(), gy.ravel()], axis=1)  # [H*W, 2]

        scores  = scores[mask]
        bbox_f  = bbox_raw.reshape(n, 64)[mask].astype(np.float32)
        kpt_f   = kpt_raw.reshape(n, 51)[mask].astype(np.float32)
        anc     = anchors[mask]

        # DFL → [N, 4]: (left, top, right, bottom) in feature-map units → pixel
        dist = self._dfl(bbox_f)
        x1 = (anc[:, 0] - dist[:, 0]) * stride
        y1 = (anc[:, 1] - dist[:, 1]) * stride
        x2 = (anc[:, 0] + dist[:, 2]) * stride
        y2 = (anc[:, 1] + dist[:, 3]) * stride

        # Keypoints: (kx*2 + anchor - 0.5) * stride  (YOLOv8 pose convention)
        kpts = kpt_f.reshape(-1, self._NUM_KPT, 3)
        kx = (kpts[:, :, 0] * 2.0 + anc[:, 0:1] - 0.5) * stride
        ky = (kpts[:, :, 1] * 2.0 + anc[:, 1:2] - 0.5) * stride
        kv = kpts[:, :, 2]  # already probability (sigmoid applied in HEF)

        # Reverse letterbox → original image coords
        x1 = (x1 - pad_x) / scale;  x2 = (x2 - pad_x) / scale
        y1 = (y1 - pad_y) / scale;  y2 = (y2 - pad_y) / scale
        kx = (kx - pad_x) / scale;  ky = (ky - pad_y) / scale

        detections: List[dict] = []
        for i in range(len(scores)):
            kpts_2d = [
                [float(kx[i, j]), float(ky[i, j])] if kv[i, j] > 0.3 else [0.0, 0.0]
                for j in range(self._NUM_KPT)
            ]
            detections.append({
                "bbox": [
                    max(0.0, float(x1[i])), max(0.0, float(y1[i])),
                    min(float(orig_w), float(x2[i])), min(float(orig_h), float(y2[i])),
                ],
                "score": float(scores[i]),
                "keypoints_2d": kpts_2d,
            })
        return detections

    def _nms(self, dets: List[dict]) -> List[dict]:
        if not dets:
            return []
        boxes  = np.array([d["bbox"] for d in dets], dtype=np.float32)
        scores = np.array([d["score"] for d in dets], dtype=np.float32)
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas  = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        order  = scores.argsort()[::-1]
        keep   = []
        while order.size > 0:
            i = order[0]; keep.append(i)
            ix1 = np.maximum(x1[i], x1[order[1:]])
            iy1 = np.maximum(y1[i], y1[order[1:]])
            ix2 = np.minimum(x2[i], x2[order[1:]])
            iy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)
            iou   = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            order = order[np.where(iou <= self.nms_iou)[0] + 1]
        return [dets[i] for i in keep]


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
        use_hailo_server: bool = False,
        hailo_server_host: str = "localhost",
        hailo_server_port: int = 8003,
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

        # Hailo-10 pose estimator
        self.pose_estimator: Optional[HailoPoseEstimator] = None
        if use_hailo_server:
            # Use centralized inference server (shares Hailo with face_recognition, etc.)
            self.pose_estimator = HailoPoseEstimator(
                hef_path="",  # not needed in server mode
                use_server=True,
                server_host=hailo_server_host,
                server_port=hailo_server_port,
            )
        else:
            # Direct VDevice access (exclusive)
            if hef_path is None:
                hef_path = get_hef_path("yolov8m_pose")
            if hef_path:
                if is_hailo_available():
                    if hailo_device_id is None:
                        hailo_device_id = detect_hailo_device(device_index=hailo_device_index)
                    self.pose_estimator = HailoPoseEstimator(hef_path, device_id=hailo_device_id)
                else:
                    print("[OAK] No Hailo device — pose estimation disabled")

        # FPS tracking
        self._last_fps_time: Optional[float] = None
        self._frame_count_for_fps = 0

    # ------------------------------------------------------------------
    # OAK-D pipeline (DepthAI v3 API — no XLinkOut)
    # ------------------------------------------------------------------
    def _build_pipeline(self):
        """Build pipeline. Returns (pipeline, rgb_queue, depth_queue)."""
        pipeline = dai.Pipeline()

        # --- RGB camera (CAM_A) ---
        cam_rgb = pipeline.create(dai.node.Camera, dai.CameraBoardSocket.CAM_A)
        cam_rgb.build()
        rgb_out = cam_rgb.requestOutput((1920, 1080), dai.ImgFrame.Type.BGR888p)

        # --- Stereo depth with auto-created mono cameras (CAM_B + CAM_C) ---
        # Using autoCreateCameras=True avoids "board socket already used" errors
        # that occur when we create Camera nodes for CAM_B/CAM_C AND stereo also
        # tries to register those sockets internally.
        # NOTE: Do NOT call setDepthAlign(CAM_A) — the OAK-D Pro W RGB ISP native
        # width is 2024 (not a multiple of 16 relative to depth), which causes a
        # pipeline crash. Depth is used only to sample a small patch near keypoints,
        # so mono-resolution unaligned depth is sufficient.
        stereo = pipeline.create(dai.node.StereoDepth)
        stereo.build(autoCreateCameras=True, presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL)

        # --- Output queues (must be created before pipeline.start()) ---
        rgb_q   = rgb_out.createOutputQueue()
        depth_q = stereo.depth.createOutputQueue()

        return pipeline, rgb_q, depth_q

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

        # head_bounding_box_2d — USED (unsigned int, clamp negatives to 0)
        head_bbox = body.get("head_bounding_box_2d", [(0, 0)] * 4)
        bbox_values = []
        for corner in head_bbox[:4]:
            bbox_values.extend([max(0, int(corner[0])), max(0, int(corner[1]))])
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
            # Depth frame is in mono resolution (640×400); RGB is 1920×1080.
            # Scale nose coords from RGB space to depth space for lookup.
            nose = coco_kps[COCO_NOSE]
            head_position = [0.0, 0.0, 0.0]
            if depth_frame is not None and nose[0] > 0 and nose[1] > 0:
                rgb_h, rgb_w = self.frame_shape[:2]
                d_h, d_w = depth_frame.shape[:2]
                raw_nx = int(nose[0] * d_w / rgb_w)
                raw_ny = int(nose[1] * d_h / rgb_h)
                nx = min(max(raw_nx, 0), d_w - 1)
                ny = min(max(raw_ny, 0), d_h - 1)
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
        pipeline, q_rgb, q_depth = self._build_pipeline()
        pipeline.start()

        device = pipeline.getDefaultDevice()

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
            pipeline.stop()
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
    parser.add_argument("--use-hailo-server", action="store_true",
                        help="Use centralized hailo_inference_server instead of direct VDevice")
    parser.add_argument("--hailo-server-host", type=str, default="localhost",
                        help="Hailo inference server host (default: localhost)")
    parser.add_argument("--hailo-server-port", type=int, default=8003,
                        help="Hailo inference server port (default: 8003)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable FPS debug output")
    args = parser.parse_args()

    server = OakImageServer(
        hef_path=args.hef,
        hailo_device_id=args.hailo_device,
        hailo_device_index=args.hailo_index,
        use_hailo_server=args.use_hailo_server,
        hailo_server_host=args.hailo_server_host,
        hailo_server_port=args.hailo_server_port,
        debug=args.debug,
    )
    server.run()


if __name__ == "__main__":
    main()
