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


SHM_NAME = "zed_image_shm"

# Header layout (all uint32, little-endian):
# [0] magic = 0x5A454449  ("ZEDI" for sanity check)
# [1] width
# [2] height
# [3] channels
# [4] dtype_code (0=uint8, 1=float32, etc. currently only 0 used)
# [5] frame_counter
HEADER_UINT_COUNT = 6
HEADER_BYTES = HEADER_UINT_COUNT * 4


def allocate_size(width: int, height: int, channels: int, bytes_per_channel: int = 1) -> int:
    """Return total shared memory size in bytes for given image shape."""
    return HEADER_BYTES + width * height * channels * bytes_per_channel


class ZedImageServer:
    def __init__(self, shm_name: str = SHM_NAME):
        self.shm_name = shm_name
        self.camera = sl.Camera()
        self.image_left = sl.Mat()
        self.frame_counter = 0
        self.shm_block: shm.SharedMemory | None = None
        self.frame_shape: Tuple[int, int, int] | None = None  # (h, w, c)

        self._open_camera()
        self._init_shared_memory()

    def _open_camera(self) -> None:
        init_params = sl.InitParameters()
        init_params.camera_resolution = sl.RESOLUTION.AUTO
        init_params.camera_fps = 30
        init_params.depth_mode = sl.DEPTH_MODE.NONE

        err = self.camera.open(init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            raise RuntimeError(f"Failed to open ZED camera: {err}")

        print("[ZED] Camera initialized.")

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

    def _init_shared_memory(self) -> None:
        assert self.frame_shape is not None
        h, w, c = self.frame_shape
        total_size = allocate_size(w, h, c, bytes_per_channel=1)

        # Try to create; if exists, attach and reuse size (must be >= needed)
        try:
            self.shm_block = shm.SharedMemory(name=self.shm_name, create=True, size=total_size)
            print(f"[SHM] Created shared memory '{self.shm_name}' ({total_size} bytes)")
        except FileExistsError:
            # Attach to existing block
            existing = shm.SharedMemory(name=self.shm_name, create=False)
            if existing.size < total_size:
                existing.close()
                raise RuntimeError(
                    f"Existing shared memory '{self.shm_name}' is too small "
                    f"({existing.size} < {total_size} bytes)"
                )
            self.shm_block = existing
            print(
                f"[SHM] Attached to existing shared memory '{self.shm_name}' "
                f"({existing.size} bytes, need {total_size})"
            )

        # Relax permissions so non-root host user can read it
        try:
            shm_path = f"/dev/shm/{self.shm_name}"
            os.chmod(shm_path, 0o666)
            print(f"[SHM] Set permissions 666 on {shm_path}")
        except FileNotFoundError:
            print("[SHM] Warning: backing file not found to chmod; "
                  "ensure host/container share /dev/shm")
        except PermissionError as e:
            print(f"[SHM] Warning: chmod failed: {e}")

        # Initialize header with static fields
        buf = self.shm_block.buf
        magic = 0x5A454449  # 'ZEDI'
        width, height, channels = self.frame_shape[1], self.frame_shape[0], self.frame_shape[2]
        dtype_code = 0  # uint8
        frame_counter = 0
        header = struct.pack(
            "<6I", magic, width, height, channels, dtype_code, frame_counter
        )
        buf[:HEADER_BYTES] = header
        print(f"[SHM] Header initialized for {width}x{height}x{channels} uint8")

    def run(self) -> None:
        runtime_params = sl.RuntimeParameters()
        buf = self.shm_block.buf
        h, w, c = self.frame_shape

        try:
            print(f"[SERVER] Publishing frames into shared memory '{self.shm_name}'. Ctrl+C to stop.")
            while True:
                if self.camera.grab(runtime_params) != sl.ERROR_CODE.SUCCESS:
                    print("[ZED] Grab failed, retrying...")
                    time.sleep(0.01)
                    continue

                self.camera.retrieve_image(self.image_left, sl.VIEW.LEFT_BGR)
                image_np = self.image_left.get_data()  # (h, w, 4) or (h, w, 3) depending on SDK

                # Ensure shape is (h, w, 3) uint8 BGR
                array = np.asarray(image_np, dtype=np.uint8)
                if array.shape[-1] == 4:
                    array = array[..., :3]
                if array.shape != (h, w, c):
                    array = array.reshape((h, w, c))

                # Write pixel data after header
                pixel_bytes = array.tobytes(order="C")
                buf[HEADER_BYTES : HEADER_BYTES + len(pixel_bytes)] = pixel_bytes

                # Update frame counter in header (last uint32)
                self.frame_counter += 1
                buf[HEADER_BYTES - 4 : HEADER_BYTES] = struct.pack("<I", self.frame_counter)

                # Small sleep to approximately match camera FPS
                time.sleep(1.0 / 30.0)

        except KeyboardInterrupt:
            print("\n[SERVER] Stopping...")
        finally:
            self.close()

    def close(self) -> None:
        if self.camera is not None:
            self.camera.close()
            print("[ZED] Camera closed.")
        if self.shm_block is not None:
            try:
                self.shm_block.close()
                # Do NOT unlink here by default so clients can attach after server exit.
                # If you want auto-clean, uncomment the next line:
                # self.shm_block.unlink()
                print(f"[SHM] Detached from shared memory '{self.shm_name}'")
            except FileNotFoundError:
                pass


def main() -> None:
    server = ZedImageServer()
    server.run()


if __name__ == "__main__":
    main()

