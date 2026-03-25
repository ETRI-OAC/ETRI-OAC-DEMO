#!/usr/bin/env python3
"""
ZED image and body tracking client using shared memory.

This client can read image and body tracking data from shared memory
created by zed_server.py. It provides a class-based interface to grab
data on demand.
"""

import struct
import time
from typing import Tuple, Optional, List, Dict, Any

import multiprocessing.shared_memory as shm
import numpy as np


SHM_IMAGE_NAME = "zed_image_shm"
SHM_BODY_NAME = "zed_body_shm"
UNLOCKED = 0
LOCKED = 1

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


# Body tracking header layout (all little-endian):
# [0] lock_byte (0=unlocked, 1=locked/writing) - uint8, followed by 3 bytes padding (uint32)
# [1] magic = 0x5A424F44  ("ZBOD" for sanity check) - uint32
# [2] frame_counter (uint32)
# [3] num_bodies (uint32)
# [4] body_format (uint32) - keypoints per body (18, 34, or 38)
# Body data follows: each body is serialized with fixed + variable size fields
BODY_HEADER_BYTES = 5 * 4  # 5 uint32s (lock + 4 data fields)
BODY_MAGIC = 0x5A424F44  # 'ZBOD'

class ZedClient:
    """Client for reading ZED image and body tracking data from shared memory."""
    
    def __init__(self, shm_image_name: str = SHM_IMAGE_NAME, shm_body_name: str = SHM_BODY_NAME):
        """
        Initialize the ZED client and structure shared memory layout.
        
        Args:
            shm_image_name: Name of the image shared memory segment
            shm_body_name: Name of the body tracking shared memory segment
        """
        self.shm_image_name = shm_image_name
        self.shm_body_name = shm_body_name
        self.last_image_frame_counter = 0
        self.last_body_frame_counter = 0
        
        # Connect to shared memory and store buffers
        self.shm_image_block: Optional[shm.SharedMemory] = None
        self.shm_body_block: Optional[shm.SharedMemory] = None
        self.image_buf: Optional[memoryview] = None
        self.body_buf: Optional[memoryview] = None
        
        # Structured memory layout (parsed once during init)
        self.image_shape: Optional[Tuple[int, int, int]] = None  # (h, w, c)
        self.image_data_offset: int = IMAGE_HEADER_BYTES
        self.image_data_size: int = 0
        self.image_frame_counter_offset: int = 6 * 4  # Offset to frame_counter in header
        self.image_numpy_dtype = np.uint8  # Pre-configured dtype
        self.image_array: Optional[np.ndarray] = None  # Pre-allocated numpy array for copying
        
        self.body_header_offset: int = 4  # Offset to header data (after lock)
        self.body_data_offset: int = BODY_HEADER_BYTES
        self.body_frame_counter_offset: int = 4 + 4  # lock(4) + magic(4) = frame_counter offset
        self.body_num_bodies_offset: int = 4 + 8  # lock(4) + magic(4) + frame_counter(4) = num_bodies offset
        self.body_format_offset: int = 4 + 12  # lock(4) + magic(4) + frame_counter(4) + num_bodies(4) = body_format offset
        
        # Pre-calculated body field offsets (relative to body_data_offset)
        self._body_field_offsets = self._calculate_body_field_offsets()
        
        self._connect_and_structure_buffers()
    
    def _calculate_body_field_offsets(self) -> Dict[str, int]:
        """Calculate offsets for each body field relative to body data start."""
        offsets = {}
        offset = 0
        
        offsets['id'] = offset
        offset += 4  # uint32
        
        offsets['confidence'] = offset
        offset += 4  # float32
        
        offsets['position'] = offset
        offset += 12  # 3 floats
        
        offsets['position_covariance'] = offset
        offset += 24  # 6 floats
        
        offsets['velocity'] = offset
        offset += 12  # 3 floats
        
        offsets['tracking_state'] = offset
        offset += 1  # int8
        offsets['action_state'] = offset
        offset += 1  # int8
        offset += 2  # padding
        
        offsets['bounding_box_2d'] = offset
        offset += 32  # 8 uint32s
        
        offsets['bounding_box_3d'] = offset
        offset += 96  # 24 floats
        
        offsets['dimensions'] = offset
        offset += 12  # 3 floats
        
        offsets['head_bounding_box_2d'] = offset
        offset += 32  # 8 uint32s
        
        offsets['head_bounding_box_3d'] = offset
        offset += 96  # 24 floats
        
        offsets['head_position'] = offset
        offset += 12  # 3 floats
        
        offsets['num_keypoints'] = offset
        offset += 4  # uint32
        
        offsets['keypoints_2d'] = offset
        offset += 18 * 8  # 18 keypoints * 2 floats * 4 bytes
        
        offsets['keypoints_3d'] = offset
        offset += 18 * 12  # 18 keypoints * 3 floats * 4 bytes
        
        offsets['body_size'] = offset  # Total size per body
        
        return offsets
    
    def _connect_and_structure_buffers(self) -> None:
        """Connect to shared memory segments and structure the layout."""
        # Connect to image shared memory
        try:
            self.shm_image_block = shm.SharedMemory(name=self.shm_image_name, create=False)
            self.image_buf = self.shm_image_block.buf
            print(f"[CLIENT] Connected to image shared memory '{self.shm_image_name}'")
            
            # Structure image memory layout (wait for unlock first)
            if self._check_and_wait_for_unlock(self.image_buf, timeout=1.0):
                header_raw = bytes(self.image_buf[4:IMAGE_HEADER_BYTES])
                magic, width, height, channels, dtype_code, frame_counter = struct.unpack("<6I", header_raw)
                
                if magic == IMAGE_MAGIC and channels == 3 and dtype_code == 0:
                    self.image_shape = (height, width, channels)
                    self.image_data_size = width * height * channels
                    self.last_image_frame_counter = frame_counter
                    # Pre-allocate numpy array for copying
                    self.image_array = np.empty(self.image_shape, dtype=self.image_numpy_dtype)
                    print(f"[CLIENT] Image format: {width}x{height}x{channels} uint8 BGR")
                else:
                    print(f"[CLIENT] Warning: Invalid image format in shared memory")
            else:
                print(f"[CLIENT] Warning: Could not read image header (lock timeout)")
                
        except FileNotFoundError:
            print(f"[CLIENT] Warning: Image shared memory '{self.shm_image_name}' not found")
            self.shm_image_block = None
            self.image_buf = None
        
        # Connect to body shared memory
        try:
            self.shm_body_block = shm.SharedMemory(name=self.shm_body_name, create=False)
            self.body_buf = self.shm_body_block.buf
            print(f"[CLIENT] Connected to body tracking shared memory '{self.shm_body_name}'")
        except FileNotFoundError:
            print(f"[CLIENT] Warning: Body shared memory '{self.shm_body_name}' not found")
            self.shm_body_block = None
            self.body_buf = None
    
    def _check_and_wait_for_unlock(self, buf: memoryview, timeout: float = 1.0) -> bool:
        """
        Check if shared memory is unlocked, wait if locked.
        
        Args:
            buf: Memory buffer to check
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if unlocked, False if timeout
        """

        # Quick check first
        lock_value = struct.unpack("<I", buf[0:4])[0]
        if lock_value == UNLOCKED:
            return True
        
        # Wait for unlock
        start_time = time.time()
        while time.time() - start_time < timeout:
            lock_value = struct.unpack("<I", buf[0:4])[0]
            if lock_value == UNLOCKED:
                return True
            time.sleep(0.001)  # Small sleep to avoid busy-waiting
        return False
    
    def grab_image(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Grab the latest image from shared memory.
        Checks lock and copies data from structured memory addresses.
        
        Args:
            wait_for_new: If True, wait for a new frame (frame counter changed)
            timeout: Maximum time to wait in seconds
        
        Returns:
            Image array as numpy array (H, W, 3) uint8 BGR, or None if unavailable
        """
        if self.image_buf is None or self.image_shape is None:
            return None
        
        buf = self.image_buf
        height, width, channels = self.image_shape
        
        # Wait for lock to be unlocked
        if not self._check_and_wait_for_unlock(buf, timeout):
            return None
        
        # Read frame counter from known offset
        frame_counter = struct.unpack("<I", buf[self.image_frame_counter_offset:self.image_frame_counter_offset+4])[0]
        
        # Check if new frame is available
        if wait_for_new:
            if frame_counter == 0 or frame_counter == self.last_image_frame_counter:
                # Wait for new frame
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if not self._check_and_wait_for_unlock(buf, timeout=0.1):
                        time.sleep(0.01)
                        continue
                    new_frame_counter = struct.unpack("<I", buf[self.image_frame_counter_offset:self.image_frame_counter_offset+4])[0]
                    if new_frame_counter != frame_counter and new_frame_counter != 0:
                        frame_counter = new_frame_counter
                        break
                    time.sleep(0.01)
                else:
                    return None  # Timeout waiting for new frame
        
        if frame_counter == 0:
            return None
        
        self.last_image_frame_counter = frame_counter
        
        # Copy pixel data directly into pre-allocated array (read while unlocked)
        # Create a view of the buffer and copy into pre-allocated array
        buffer_view = np.frombuffer(
            buf[self.image_data_offset : self.image_data_offset + self.image_data_size],
            dtype=self.image_numpy_dtype
        ).reshape(self.image_shape)
        np.copyto(self.image_array, buffer_view)
        
        return self.image_array.copy()  # Return a copy to avoid issues if memory is modified
    
    def grab_bodies(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[List[Dict[str, Any]]]:
        """
        Grab the latest body tracking data from shared memory.
        Checks lock and copies data from structured memory addresses.
        
        Args:
            wait_for_new: If True, wait for a new frame (frame counter changed)
            timeout: Maximum time to wait in seconds
        
        Returns:
            List of body dictionaries, or None if unavailable.
            Each body dict contains: id, confidence, position, velocity, keypoints, etc.
        """
        if self.body_buf is None:
            return None
        
        buf = self.body_buf
        
        # Wait for lock to be unlocked
        if not self._check_and_wait_for_unlock(buf, timeout):
            return None
        
        # Read header fields from known offsets
        magic = struct.unpack("<I", buf[self.body_header_offset:self.body_header_offset+4])[0]
        if magic != BODY_MAGIC:
            return None
        
        frame_counter = struct.unpack("<I", buf[self.body_frame_counter_offset:self.body_frame_counter_offset+4])[0]
        num_bodies = struct.unpack("<I", buf[self.body_num_bodies_offset:self.body_num_bodies_offset+4])[0]
        body_format = struct.unpack("<I", buf[self.body_num_bodies_offset+4:self.body_num_bodies_offset+8])[0]
        
        # Check if new frame is available
        if wait_for_new:
            if frame_counter == 0 or frame_counter == self.last_body_frame_counter:
                # Wait for new frame
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if not self._check_and_wait_for_unlock(buf, timeout=0.1):
                        time.sleep(0.01)
                        continue
                    new_frame_counter = struct.unpack("<I", buf[self.body_frame_counter_offset:self.body_frame_counter_offset+4])[0]
                    if new_frame_counter != frame_counter and new_frame_counter != 0:
                        frame_counter = new_frame_counter
                        num_bodies = struct.unpack("<I", buf[self.body_num_bodies_offset:self.body_num_bodies_offset+4])[0]
                        break
                    time.sleep(0.01)
                else:
                    return None  # Timeout waiting for new frame
        
        if frame_counter == 0 or num_bodies == 0:
            self.last_body_frame_counter = frame_counter
            return []
        
        self.last_body_frame_counter = frame_counter
        
        # Deserialize body data from known addresses (read while unlocked)
        bodies = self._deserialize_body_data(buf, num_bodies)
        
        return bodies
    
    def _deserialize_body_data(self, buf: memoryview, num_bodies: int) -> List[Dict[str, Any]]:
        """
        Fast deserialization using pre-calculated offsets.
        Just reads and copies data into pre-structured format.
        """
        bodies = []
        body_size = self._body_field_offsets['body_size']
        base_offset = self.body_data_offset
        
        for i in range(num_bodies):
            body_offset = base_offset + i * body_size
            body = {}
            
            # Read all fields using pre-calculated offsets - just copy data
            body['id'] = struct.unpack("<I", buf[body_offset + self._body_field_offsets['id']:body_offset + self._body_field_offsets['id'] + 4])[0]
            body['confidence'] = struct.unpack("<f", buf[body_offset + self._body_field_offsets['confidence']:body_offset + self._body_field_offsets['confidence'] + 4])[0]
            
            # Position (3 floats) - direct unpack
            body['position'] = list(struct.unpack("<fff", buf[body_offset + self._body_field_offsets['position']:body_offset + self._body_field_offsets['position'] + 12]))
            
            # Position covariance (6 floats) - direct unpack
            body['position_covariance'] = list(struct.unpack("<ffffff", buf[body_offset + self._body_field_offsets['position_covariance']:body_offset + self._body_field_offsets['position_covariance'] + 24]))
            
            # Velocity (3 floats) - direct unpack
            body['velocity'] = list(struct.unpack("<fff", buf[body_offset + self._body_field_offsets['velocity']:body_offset + self._body_field_offsets['velocity'] + 12]))
            
            # Tracking and action states - direct unpack
            tracking_state, action_state = struct.unpack("<bb", buf[body_offset + self._body_field_offsets['tracking_state']:body_offset + self._body_field_offsets['tracking_state'] + 2])
            body['tracking_state'] = tracking_state
            body['action_state'] = action_state
            
            # Bounding box 2D (8 uint32s) - direct unpack and reshape
            bbox_2d_raw = struct.unpack("<8I", buf[body_offset + self._body_field_offsets['bounding_box_2d']:body_offset + self._body_field_offsets['bounding_box_2d'] + 32])
            body['bounding_box_2d'] = [(bbox_2d_raw[i*2], bbox_2d_raw[i*2+1]) for i in range(4)]
            
            # Bounding box 3D (24 floats) - direct unpack and reshape
            bbox_3d_raw = struct.unpack("<24f", buf[body_offset + self._body_field_offsets['bounding_box_3d']:body_offset + self._body_field_offsets['bounding_box_3d'] + 96])
            body['bounding_box_3d'] = [(bbox_3d_raw[i*3], bbox_3d_raw[i*3+1], bbox_3d_raw[i*3+2]) for i in range(8)]
            
            # Dimensions (3 floats) - direct unpack
            body['dimensions'] = list(struct.unpack("<fff", buf[body_offset + self._body_field_offsets['dimensions']:body_offset + self._body_field_offsets['dimensions'] + 12]))
            
            # Head bounding box 2D - direct unpack
            head_bbox_2d_raw = struct.unpack("<8I", buf[body_offset + self._body_field_offsets['head_bounding_box_2d']:body_offset + self._body_field_offsets['head_bounding_box_2d'] + 32])
            body['head_bounding_box_2d'] = [(head_bbox_2d_raw[i*2], head_bbox_2d_raw[i*2+1]) for i in range(4)]
            
            # Head bounding box 3D - direct unpack
            head_bbox_3d_raw = struct.unpack("<24f", buf[body_offset + self._body_field_offsets['head_bounding_box_3d']:body_offset + self._body_field_offsets['head_bounding_box_3d'] + 96])
            body['head_bounding_box_3d'] = [(head_bbox_3d_raw[i*3], head_bbox_3d_raw[i*3+1], head_bbox_3d_raw[i*3+2]) for i in range(8)]
            
            # Head position (3 floats) - direct unpack
            body['head_position'] = list(struct.unpack("<fff", buf[body_offset + self._body_field_offsets['head_position']:body_offset + self._body_field_offsets['head_position'] + 12]))
            
            # Number of keypoints
            num_kp = struct.unpack("<I", buf[body_offset + self._body_field_offsets['num_keypoints']:body_offset + self._body_field_offsets['num_keypoints'] + 4])[0]
            body['num_keypoints'] = num_kp
            
            # Keypoints 2D (18 keypoints, 2 floats each) - direct unpack using pre-calculated offsets
            kp_2d_offset = body_offset + self._body_field_offsets['keypoints_2d']
            keypoints_2d = []
            for j in range(18):
                kp = struct.unpack("<ff", buf[kp_2d_offset + j*8:kp_2d_offset + j*8 + 8])
                keypoints_2d.append(list(kp))
            body['keypoints_2d'] = keypoints_2d[:num_kp] if num_kp > 0 else []
            
            # Keypoints 3D (18 keypoints, 3 floats each) - direct unpack using pre-calculated offsets
            kp_3d_offset = body_offset + self._body_field_offsets['keypoints_3d']
            keypoints_3d = []
            for j in range(18):
                kp = struct.unpack("<fff", buf[kp_3d_offset + j*12:kp_3d_offset + j*12 + 12])
                keypoints_3d.append(list(kp))
            body['keypoints_3d'] = keypoints_3d[:num_kp] if num_kp > 0 else []
            
            bodies.append(body)
        
        return bodies

    def close(self) -> None:
        """Close connections to shared memory."""
        if self.shm_image_block is not None:
            try:
                self.shm_image_block.close()
                print("[CLIENT] Disconnected from image shared memory")
            except Exception as e:
                print(f"[CLIENT] Error closing image memory: {e}")
            finally:
                self.shm_image_block = None
                self.image_buf = None
        
        if self.shm_body_block is not None:
            try:
                self.shm_body_block.close()
                print("[CLIENT] Disconnected from body shared memory")
            except Exception as e:
                print(f"[CLIENT] Error closing body memory: {e}")
            finally:
                self.shm_body_block = None
                self.body_buf = None
        
        self.image_shape = None
        self.last_image_frame_counter = 0
        self.last_body_frame_counter = 0
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def main() -> None:
    """Example usage of ZedClient with body tracking visualization."""
    import cv2
    from body_tracking_visualizer import visualize_bodies_2d
    
    client = ZedClient()
    
    if client.shm_image_block is None:
        print("[CLIENT] Image shared memory not available. Is the server running?")
        return
    image_width = client.image_shape[1]
    image_height = client.image_shape[0]
    cv2.namedWindow("ZED Client - Body Tracking", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ZED Client - Body Tracking", image_width, image_height)
    
    try:
        while True:
            # Grab latest image
            image = client.grab_image(wait_for_new=False, timeout=0.1)
            if image is not None:
                # Grab latest body data
                bodies = client.grab_bodies(wait_for_new=False, timeout=0.1)
                
                # Visualize bodies on image
                image_cv = image.copy()  # Work on a copy to avoid modifying original
                if bodies is not None and len(bodies) > 0:
                    # Get body format from first body (assuming all bodies have same format)
                    body_format = 18  # Default, can be extracted from body data if needed
                    try:
                        image_cv = visualize_bodies_2d(image_cv, bodies, body_format=body_format)
                        print(f"[CLIENT] Detected {len(bodies)} person(s)")
                    except Exception as e:
                        print(f"[CLIENT] Error visualizing bodies: {e}")
                        import traceback
                        traceback.print_exc()
                
                cv2.imshow("ZED Client - Body Tracking", image_cv)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):  # ESC or q
                break
            
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted by user")
    finally:
        cv2.destroyAllWindows()
        client.close()


if __name__ == "__main__":
    main()
