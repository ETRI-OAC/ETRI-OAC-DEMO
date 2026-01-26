#!/usr/bin/env python3
"""
ZED image server using shared memory.

Run this inside the ZED container. It:
  - Opens the ZED camera
  - Grabs LEFT_BGR images
  - Publishes each frame into a fixed-size shared memory segment

Client processes (on host or other containers) can attach to the same
shared memory name to read the latest frame without copying over sockets.
"""

import struct
import time
from typing import Tuple
import os

import multiprocessing.shared_memory as shm
import numpy as np
import pyzed.sl as sl

SHM_IMAGE_NAME = "zed_image_shm"
SHM_BODY_NAME = "zed_body_shm"

# Image header layout (all little-endian):
# [0] lock_byte (0=unlocked, 1=locked/writing) - uint8, followed by 3 bytes padding (uint32)
# [1] magic = 0x5A494D47  ("ZIMG" for sanity check) - uint32
# [2] width - uint32
# [3] height - uint32
# [4] channels - uint32
# [5] dtype_code (0=uint8, 1=float32, etc. currently only 0 used) - uint32
# [6] frame_counter - uint32
IMAGE_HEADER_BYTES = 7 * 4  # 7 uint32s (lock + 6 data fields)
IMAGE_MAGIC = 0x5A494D47  # 'ZIMG'
IMAGE_LOCK_UNLOCKED = 0
IMAGE_LOCK_LOCKED = 1

# Body tracking header layout (all little-endian):
# [0] lock_byte (0=unlocked, 1=locked/writing) - uint8, followed by 3 bytes padding (uint32)
# [1] magic = 0x5A424F44  ("ZBOD" for sanity check) - uint32
# [2] frame_counter (uint32)
# [3] num_bodies (uint32)
# [4] body_format (uint32) - keypoints per body (18, 34, or 38)
# Body data follows: each body is serialized with fixed + variable size fields
BODY_HEADER_BYTES = 5 * 4  # 5 uint32s (lock + 4 data fields)
BODY_MAGIC = 0x5A424F44  # 'ZBOD'
BODY_LOCK_UNLOCKED = 0
BODY_LOCK_LOCKED = 1


def allocate_size(width: int, height: int, channels: int, bytes_per_channel: int = 1) -> int:
    """Return total shared memory size in bytes for given image shape."""
    return IMAGE_HEADER_BYTES + width * height * channels * bytes_per_channel


class ZedImageServer:
    def __init__(self, shm_image_name: str = SHM_IMAGE_NAME, shm_body_name: str = SHM_BODY_NAME, debug: bool = False):
        self.shm_image_name = shm_image_name
        self.shm_body_name = shm_body_name
        self.debug = debug
        self.camera = sl.Camera()
        self.image_left = sl.Mat()
        self.bodies = sl.Bodies()
        self.frame_counter = 0
        self.shm_image_block: shm.SharedMemory | None = None
        self.shm_body_block: shm.SharedMemory | None = None
        self.frame_shape: Tuple[int, int, int] | None = None  # (h, w, c)
        self.body_format = sl.BODY_FORMAT.BODY_18  # TODO: get from parameters, only BODY_18 is supported for now
        self.runtime_params = sl.RuntimeParameters()
        self.body_runtime_param = sl.BodyTrackingRuntimeParameters()
        self.body_runtime_param.detection_confidence_threshold = 80
        
        # FPS tracking for debug mode
        self._last_fps_time = None
        self._frame_count_for_fps = 0

        self._open_camera()
        self._init_image_shared_memory()
        self._init_body_shared_memory()

    def _open_camera(self) -> None:
        init_params = sl.InitParameters()
        init_params.camera_resolution = sl.RESOLUTION.HD1200
        init_params.camera_fps = 30
        init_params.depth_mode = sl.DEPTH_MODE.NEURAL_LIGHT

        err = self.camera.open(init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"Failed to open ZED camera: {err}")

        print("[ZED] Camera initialized.")

        # Enable positional tracking (required for body tracking)
        positional_tracking_parameters = sl.PositionalTrackingParameters()
        self.camera.enable_positional_tracking(positional_tracking_parameters)
        print("[ZED] Positional tracking enabled.")

        # Enable body tracking
        body_param = sl.BodyTrackingParameters()
        body_param.enable_tracking = True
        body_param.enable_body_fitting = True
        body_param.detection_model = sl.BODY_TRACKING_MODEL.HUMAN_BODY_FAST
        body_param.body_format = self.body_format

        err = self.camera.enable_body_tracking(body_param)
        if err != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"Failed to enable body tracking: {err}")
        print("[ZED] Body tracking enabled.")

        # Grab one frame to determine dimensions
        runtime_params = sl.RuntimeParameters()
        if self.camera.grab(runtime_params) != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError("Failed to grab initial frame from ZED.")

        self.camera.retrieve_image(self.image_left, sl.VIEW.LEFT_BGR)
        h = self.image_left.get_height()
        w = self.image_left.get_width()
        c = 3  # BGR
        self.frame_shape = (h, w, c)
        print(f"[ZED] Image size: {w}x{h}x{c}")

    def _init_image_shared_memory(self) -> None:
        assert self.frame_shape is not None
        h, w, c = self.frame_shape
        total_size = allocate_size(w, h, c, bytes_per_channel=1)

        # Try to create; if exists, attach and reuse size (must be >= needed)
        try:
            self.shm_image_block = shm.SharedMemory(name=self.shm_image_name, create=True, size=total_size)
            print(f"[SHM] Created shared memory '{self.shm_image_name}' ({total_size} bytes)")
        except FileExistsError:
            # Attach to existing block
            existing = shm.SharedMemory(name=self.shm_image_name, create=False)
            if existing.size < total_size:
                existing.close()
                raise RuntimeError(
                    f"Existing shared memory '{self.shm_image_name}' is too small "
                    f"({existing.size} < {total_size} bytes)"
                )
            self.shm_image_block = existing
            print(
                f"[SHM] Attached to existing shared memory '{self.shm_image_name}' "
                f"({existing.size} bytes, need {total_size})"
            )

        # Relax permissions so non-root host user can read it
        try:
            shm_path = f"/dev/shm/{self.shm_image_name}"
            os.chmod(shm_path, 0o666)
            print(f"[SHM] Set permissions 666 on {shm_path}")
        except FileNotFoundError:
            print("[SHM] Warning: backing file not found to chmod; "
                  "ensure host/container share /dev/shm")
        except PermissionError as e:
            print(f"[SHM] Warning: chmod failed: {e}")

        # Initialize header with static fields
        buf = self.shm_image_block.buf
        width, height, channels = self.frame_shape[1], self.frame_shape[0], self.frame_shape[2]
        dtype_code = 0  # uint8
        frame_counter = 0
        # Initialize lock byte to unlocked (first 4 bytes)
        buf[0:4] = struct.pack("<I", IMAGE_LOCK_UNLOCKED)
        # Pack rest of header (magic, width, height, channels, dtype_code, frame_counter)
        header = struct.pack(
            "<6I", IMAGE_MAGIC, width, height, channels, dtype_code, frame_counter
        )
        buf[4:IMAGE_HEADER_BYTES] = header
        print(f"[SHM] Header initialized for {width}x{height}x{channels} uint8")

    def _init_body_shared_memory(self) -> None:
        """Initialize shared memory for body tracking data."""
        # Estimate max size: header + max bodies * body_size
        # Each body: id(4) + confidence(4) + position(12) + covariance(24) + velocity(12)
        #           + tracking_state(1) + action_state(1) + padding(2)
        #           + bbox_2d(16) + bbox_3d(96) + dimensions(12) + head_bbox_2d(16) + head_bbox_3d(96) + head_pos(12)
        #           + num_keypoints(4) + keypoints_2d(variable) + keypoints_3d(variable)
        # For BODY_18: 2*18*4 + 3*18*4 = 360 bytes per body for keypoints
        # Fixed per body: ~300 bytes
        # Total per body: ~660 bytes, allow for 10 bodies max = 6600 bytes
        # Plus header: 16 bytes
        MAX_BODIES = 10
        KEYPOINTS_PER_BODY = 18  # BODY_18 format
        BODY_FIXED_SIZE = 300  # Fixed fields per body
        KEYPOINT_2D_SIZE = KEYPOINTS_PER_BODY * 2 * 4  # 2 floats per keypoint
        KEYPOINT_3D_SIZE = KEYPOINTS_PER_BODY * 3 * 4  # 3 floats per keypoint
        BODY_SIZE = BODY_FIXED_SIZE + KEYPOINT_2D_SIZE + KEYPOINT_3D_SIZE
        total_size = BODY_HEADER_BYTES + MAX_BODIES * BODY_SIZE

        try:
            self.shm_body_block = shm.SharedMemory(
                name=self.shm_body_name, create=True, size=total_size
            )
            print(f"[SHM] Created body tracking shared memory '{self.shm_body_name}' ({total_size} bytes)")
        except FileExistsError:
            existing = shm.SharedMemory(name=self.shm_body_name, create=False)
            if existing.size < total_size:
                existing.close()
                raise RuntimeError(
                    f"Existing body shared memory '{self.shm_body_name}' is too small "
                    f"({existing.size} < {total_size} bytes)"
                )
            self.shm_body_block = existing
            print(
                f"[SHM] Attached to existing body shared memory '{self.shm_body_name}' "
                f"({existing.size} bytes, need {total_size})"
            )

        # Relax permissions
        try:
            shm_path = f"/dev/shm/{self.shm_body_name}"
            os.chmod(shm_path, 0o666)
            print(f"[SHM] Set permissions 666 on {shm_path}")
        except FileNotFoundError:
            print("[SHM] Warning: backing file not found to chmod")
        except PermissionError as e:
            print(f"[SHM] Warning: chmod failed: {e}")

        # Initialize header
        buf = self.shm_body_block.buf
        # Initialize lock byte to unlocked (first 4 bytes)
        buf[0:4] = struct.pack("<I", BODY_LOCK_UNLOCKED)
        # Pack rest of header (magic, frame_counter, num_bodies, body_format)
        header = struct.pack(
            "<IIII", BODY_MAGIC, 0, 0, self.body_format.value
        )
        buf[4:BODY_HEADER_BYTES] = header
        print(f"[SHM] Body tracking header initialized")

    def _serialize_body_data(self, bodies: sl.Bodies) -> bytes:
        """Serialize body_list data into bytes for shared memory."""
        body_list = bodies.body_list
        num_bodies = len(body_list)
        
        # Start with header fields
        data_parts = []
        
        # Serialize each body
        for body in body_list:
            # Fixed fields
            body_data = struct.pack(
                "<I", body.id  # uint32
            )
            body_data += struct.pack("<f", body.confidence)  # float32
            
            # Position (3 floats)
            try:
                if hasattr(body, 'position') and len(body.position) >= 3:
                    body_data += struct.pack("<fff", float(body.position[0]), float(body.position[1]), float(body.position[2]))
                else:
                    body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            
            # Position covariance (6 floats - upper triangular matrix)
            try:
                if hasattr(body, 'position_covariance') and len(body.position_covariance) >= 6:
                    body_data += struct.pack("<ffffff", *[float(x) for x in body.position_covariance[:6]])
                else:
                    body_data += struct.pack("<ffffff", *([0.0] * 6))
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<ffffff", *([0.0] * 6))
            
            # Velocity (3 floats)
            try:
                if hasattr(body, 'velocity') and len(body.velocity) >= 3:
                    body_data += struct.pack("<fff", float(body.velocity[0]), float(body.velocity[1]), float(body.velocity[2]))
                else:
                    body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            
            # Tracking and action states (int8 each)
            tracking_state = int(body.tracking_state.value) if hasattr(body, 'tracking_state') else 0
            action_state = int(body.action_state.value) if hasattr(body, 'action_state') else 0
            body_data += struct.pack("<bb", tracking_state, action_state)
            body_data += struct.pack("<H", 0)  # Padding to align to 4 bytes
            
            # Bounding box 2D (4 corners, each 2 uint32 = 8 uint32s = 32 bytes)
            try:
                if hasattr(body, 'bounding_box_2d') and len(body.bounding_box_2d) >= 4:
                    bbox_2d = body.bounding_box_2d[:4]
                    # Handle different access patterns (list, tuple, or object with x,y attributes)
                    bbox_values = []
                    for corner in bbox_2d:
                        if hasattr(corner, 'x') and hasattr(corner, 'y'):
                            bbox_values.extend([int(corner.x), int(corner.y)])
                        elif isinstance(corner, (list, tuple)) and len(corner) >= 2:
                            bbox_values.extend([int(corner[0]), int(corner[1])])
                        else:
                            bbox_values.extend([0, 0])
                    body_data += struct.pack("<8I", *bbox_values[:8])
                else:
                    body_data += struct.pack("<8I", *([0] * 8))
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<8I", *([0] * 8))
            
            # Bounding box 3D (8 corners, each 3 floats = 24 floats = 96 bytes)
            try:
                if hasattr(body, 'bounding_box') and len(body.bounding_box) >= 8:
                    bbox_3d = body.bounding_box[:8]
                    # Handle different access patterns
                    bbox_values = []
                    for corner in bbox_3d:
                        if hasattr(corner, 'x') and hasattr(corner, 'y') and hasattr(corner, 'z'):
                            bbox_values.extend([float(corner.x), float(corner.y), float(corner.z)])
                        elif isinstance(corner, (list, tuple)) and len(corner) >= 3:
                            bbox_values.extend([float(corner[0]), float(corner[1]), float(corner[2])])
                        else:
                            bbox_values.extend([0.0, 0.0, 0.0])
                    body_data += struct.pack("<24f", *bbox_values[:24])
                else:
                    body_data += struct.pack("<24f", *([0.0] * 24))
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<24f", *([0.0] * 24))
            
            # Dimensions (3 floats)
            try:
                if hasattr(body, 'dimensions') and len(body.dimensions) >= 3:
                    body_data += struct.pack("<fff", float(body.dimensions[0]), float(body.dimensions[1]), float(body.dimensions[2]))
                else:
                    body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            
            # Head bounding box 2D
            try:
                if hasattr(body, 'head_bounding_box_2d') and len(body.head_bounding_box_2d) >= 4:
                    head_bbox_2d = body.head_bounding_box_2d[:4]
                    head_bbox_values = []
                    for corner in head_bbox_2d:
                        head_bbox_values.extend([int(corner[0]), int(corner[1])])
                    body_data += struct.pack("<8I", *head_bbox_values[:8])
                else:
                    body_data += struct.pack("<8I", *([0] * 8))
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<8I", *([0] * 8))
            
            # Head bounding box 3D
            try:
                if hasattr(body, 'head_bounding_box') and len(body.head_bounding_box) >= 8:
                    head_bbox_3d = body.head_bounding_box[:8]
                    head_bbox_values = []
                    for corner in head_bbox_3d:
                        if hasattr(corner, 'x') and hasattr(corner, 'y') and hasattr(corner, 'z'):
                            head_bbox_values.extend([float(corner.x), float(corner.y), float(corner.z)])
                        elif isinstance(corner, (list, tuple)) and len(corner) >= 3:
                            head_bbox_values.extend([float(corner[0]), float(corner[1]), float(corner[2])])
                        else:
                            head_bbox_values.extend([0.0, 0.0, 0.0])
                    body_data += struct.pack("<24f", *head_bbox_values[:24])
                else:
                    body_data += struct.pack("<24f", *([0.0] * 24))
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<24f", *([0.0] * 24))
            
            # Head position (3 floats)
            try:
                if hasattr(body, 'head_position') and len(body.head_position) >= 3:
                    body_data += struct.pack("<fff", float(body.head_position[0]), float(body.head_position[1]), float(body.head_position[2]))
                else:
                    body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            except (AttributeError, IndexError, TypeError):
                body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            
            # Keypoints
            num_kp = 0
            keypoints_2d_list = []
            
            try:
                # Try to access keypoint_2d - it might be a vector or list
                if hasattr(body, 'keypoint_2d'):
                    kp_2d = body.keypoint_2d
                    
                    # Try to get length
                    if hasattr(kp_2d, '__len__'):
                        num_kp = len(kp_2d)
                        
                        # Try to iterate and extract keypoints
                        for i in range(min(num_kp, 18)):
                            try:
                                kp = kp_2d[i]
                                
                                # Try different access patterns
                                x, y = 0.0, 0.0
                                
                                # Pattern 1: Object with x, y attributes
                                if hasattr(kp, 'x') and hasattr(kp, 'y'):
                                    x, y = float(kp.x), float(kp.y)
                                # Pattern 2: Indexable (list, tuple, array)
                                elif hasattr(kp, '__getitem__'):
                                    try:
                                        x, y = float(kp[0]), float(kp[1])
                                    except (IndexError, TypeError):
                                        x, y = 0.0, 0.0
                                # Pattern 3: Direct tuple/list
                                elif isinstance(kp, (list, tuple)) and len(kp) >= 2:
                                    x, y = float(kp[0]), float(kp[1])
                                
                                keypoints_2d_list.append((x, y))
                                    
                            except (AttributeError, IndexError, TypeError) as e:
                                if self.debug:
                                    print(f"[DEBUG] Error accessing keypoint {i}: {e}, type: {type(kp_2d[i])}")
                                keypoints_2d_list.append((0.0, 0.0))
                    else:
                        if self.debug:
                            print(f"[DEBUG] keypoint_2d is not iterable")
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Exception accessing keypoint_2d: {e}")
                    import traceback
                    traceback.print_exc()
                num_kp = 0
            
            body_data += struct.pack("<I", num_kp)  # Number of keypoints
            
            # Keypoints 2D (2 floats per keypoint)
            max_kp = 18  # BODY_18
            # Write actual keypoints
            for kp in keypoints_2d_list:
                body_data += struct.pack("<ff", kp[0], kp[1])
            # Pad to max keypoints if needed
            for _ in range(len(keypoints_2d_list), max_kp):
                body_data += struct.pack("<ff", 0.0, 0.0)
            
            # Keypoints 3D (3 floats per keypoint)
            keypoints_3d_list = []
            try:
                if hasattr(body, 'keypoint'):
                    kp_3d = body.keypoint
                    # Check if it's a list/vector
                    if hasattr(kp_3d, '__len__'):
                        kp_len = len(kp_3d)
                        # Try to extract keypoints
                        for i in range(min(kp_len, 18)):
                            try:
                                kp = kp_3d[i]
                                # Try different access patterns
                                if hasattr(kp, 'x') and hasattr(kp, 'y') and hasattr(kp, 'z'):
                                    keypoints_3d_list.append((float(kp.x), float(kp.y), float(kp.z)))
                                elif hasattr(kp, '__getitem__'):
                                    keypoints_3d_list.append((float(kp[0]), float(kp[1]), float(kp[2])))
                                elif isinstance(kp, (list, tuple)) and len(kp) >= 3:
                                    keypoints_3d_list.append((float(kp[0]), float(kp[1]), float(kp[2])))
                                else:
                                    keypoints_3d_list.append((0.0, 0.0, 0.0))
                            except (AttributeError, IndexError, TypeError) as e:
                                if self.debug:
                                    print(f"[DEBUG] Error accessing 3D keypoint {i}: {e}")
                                keypoints_3d_list.append((0.0, 0.0, 0.0))
            except Exception as e:
                if self.debug:
                    print(f"[DEBUG] Error accessing keypoint: {e}")
            
            # Write actual keypoints
            for kp in keypoints_3d_list:
                body_data += struct.pack("<fff", kp[0], kp[1], kp[2])
            # Pad to max keypoints if needed
            for _ in range(len(keypoints_3d_list), max_kp):
                body_data += struct.pack("<fff", 0.0, 0.0, 0.0)
            
            data_parts.append(body_data)
        
        return b''.join(data_parts)

    def _write_image_data(self, image_array: np.ndarray) -> None:
        """Write image data to shared memory with locking."""
        if self.shm_image_block is None:
            return
        
        buf = self.shm_image_block.buf
        h, w, c = self.frame_shape
        
        # Ensure shape is (h, w, 3) uint8 BGR
        array = np.asarray(image_array, dtype=np.uint8)
        if array.shape[-1] == 4:
            array = array[..., :3]
        if array.shape != (h, w, c):
            array = array.reshape((h, w, c))
        
        # Lock: set lock byte to LOCKED before writing (first 4 bytes)
        buf[0:4] = struct.pack("<I", IMAGE_LOCK_LOCKED)
        
        try:
            # Write pixel data after header
            pixel_bytes = array.tobytes(order="C")
            data_offset = IMAGE_HEADER_BYTES
            buf[data_offset : data_offset + len(pixel_bytes)] = pixel_bytes
            
            # Update frame counter in header (offset 6*4, which is the 7th uint32)
            self.frame_counter += 1
            buf[6*4 : 7*4] = struct.pack("<I", self.frame_counter)
        finally:
            # Unlock: set lock byte to UNLOCKED after writing
            buf[0:4] = struct.pack("<I", IMAGE_LOCK_UNLOCKED)

    def _write_body_data(self, bodies: sl.Bodies) -> None:
        """Write body tracking data to shared memory with locking."""
        if self.shm_body_block is None:
            return
        
        buf = self.shm_body_block.buf
        body_list = bodies.body_list
        num_bodies = len(body_list)
        
        # Serialize body data first (outside of lock)
        body_bytes = self._serialize_body_data(bodies)
        
        # Calculate required size
        required_size = BODY_HEADER_BYTES + len(body_bytes)
        
        if required_size > len(buf):
            print(f"[SHM] Warning: Body data too large ({required_size} > {len(buf)}), truncating")
            body_bytes = body_bytes[:len(buf) - BODY_HEADER_BYTES]
            num_bodies = min(num_bodies, 10)  # Limit to max
        
        # Lock: set lock byte to LOCKED (first 4 bytes)
        buf[0:4] = struct.pack("<I", BODY_LOCK_LOCKED)
        
        try:
            # Write header (without lock byte, starting at offset 4)
            header = struct.pack(
                "<IIII", BODY_MAGIC, self.frame_counter, num_bodies, self.body_format.value
            )
            buf[4:BODY_HEADER_BYTES] = header
            
            # Write body data
            if len(body_bytes) > 0:
                buf[BODY_HEADER_BYTES:BODY_HEADER_BYTES + len(body_bytes)] = body_bytes
        finally:
            # Unlock: set lock byte to UNLOCKED
            buf[0:4] = struct.pack("<I", BODY_LOCK_UNLOCKED)

    def run(self) -> None:
        try:
            print(f"[SERVER] Publishing frames into shared memory '{self.shm_image_name}'.")
            print(f"[SERVER] Publishing body tracking into shared memory '{self.shm_body_name}'.")
            print("[SERVER] Ctrl+C to stop.")
            while True:
                if self.camera.grab(self.runtime_params) != sl.ERROR_CODE.SUCCESS:
                    print("[ZED] Grab failed, retrying...")
                    time.sleep(0.01)
                    continue

                # # Retrieve and write image data
                self.camera.retrieve_image(self.image_left, sl.VIEW.LEFT_BGR)
                image_np = self.image_left.get_data()  # (h, w, 4) or (h, w, 3) depending on SDK
                self._write_image_data(image_np)

                # Retrieve and write body tracking data
                if self.camera.retrieve_bodies(self.bodies, self.body_runtime_param) == sl.ERROR_CODE.SUCCESS:
                    self._write_body_data(self.bodies)

                # FPS measurement (only when debug is on)
                if self.debug:
                    if self._last_fps_time is None:
                        self._last_fps_time = time.time()
                        self._frame_count_for_fps = 0
                    
                    self._frame_count_for_fps += 1
                    now = time.time()
                    elapsed = now - self._last_fps_time
                    if elapsed >= 1.0:
                        fps = self._frame_count_for_fps / elapsed
                        print(f"[DEBUG] {len(self.bodies.body_list)} person(s) detected,ZED Server processing FPS: {fps:.2f}")
                        self._last_fps_time = now
                        self._frame_count_for_fps = 0

        except KeyboardInterrupt:
            print("\n[SERVER] Stopping...")
        finally:
            self.close()

    def close(self) -> None:
        if self.camera is not None:
            self.camera.close()
            print("[ZED] Camera closed.")
        if self.shm_image_block is not None:
            try:
                self.shm_image_block.close()
                # Do NOT unlink here by default so clients can attach after server exit.
                # If you want auto-clean, uncomment the next line:
                # self.shm_image_block.unlink()
                print(f"[SHM] Detached from image shared memory '{self.shm_image_name}'")
            except FileNotFoundError:
                pass
        if self.shm_body_block is not None:
            try:
                self.shm_body_block.close()
                # Do NOT unlink here by default so clients can attach after server exit.
                # self.shm_body_block.unlink()
                print(f"[SHM] Detached from body shared memory '{self.shm_body_name}'")
            except FileNotFoundError:
                pass


def main() -> None:
    server = ZedImageServer(debug=True)
    server.run()


if __name__ == "__main__":
    main()

