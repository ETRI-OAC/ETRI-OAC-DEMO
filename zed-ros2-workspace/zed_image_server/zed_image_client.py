#!/usr/bin/env python3
"""
ZED image client using shared memory + OpenCV viewer.

Run this on the host (or another container sharing the same SHM namespace)
while `zed_image_server.py` is running in the ZED container.
"""

import struct
import time

import cv2
import multiprocessing.shared_memory as shm
import numpy as np


SHM_NAME = "zed_image_shm"

# Header: 6 * uint32 (little-endian)
# [0] magic = 0x5A454449 ("ZEDI")
# [1] width
# [2] height
# [3] channels
# [4] dtype_code (0=uint8)
# [5] frame_counter
HEADER_UINT_COUNT = 6
HEADER_BYTES = HEADER_UINT_COUNT * 4
MAGIC = 0x5A454449


def main() -> None:
    try:
        shm_block = shm.SharedMemory(name=SHM_NAME, create=False)
    except FileNotFoundError:
        print(f"[CLIENT] Shared memory '{SHM_NAME}' not found. Start server first.")
        return

    print(f"[CLIENT] Attached to shared memory '{SHM_NAME}' ({shm_block.size} bytes)")

    buf = shm_block.buf

    # Read static header once
    header_raw = bytes(buf[:HEADER_BYTES])
    magic, width, height, channels, dtype_code, _ = struct.unpack("<6I", header_raw)

    if magic != MAGIC:
        print(f"[CLIENT] Invalid magic in header (got {hex(magic)}, expected {hex(MAGIC)})")
        shm_block.close()
        return

    if channels != 3 or dtype_code != 0:
        print(f"[CLIENT] Unsupported format: channels={channels}, dtype_code={dtype_code}")
        shm_block.close()
        return

    print(f"[CLIENT] Image format: {width}x{height}x{channels} uint8 BGR")

    pixel_bytes = width * height * channels

    cv2.namedWindow("ZED SHM Viewer", cv2.WINDOW_NORMAL)

    last_frame_counter = None
    first_frame_shown = False

    try:
        while True:
            # Re-read header to get latest frame_counter
            header_raw = bytes(buf[:HEADER_BYTES])
            _, _, _, _, _, frame_counter = struct.unpack("<6I", header_raw)

            if frame_counter == 0 or frame_counter == last_frame_counter:
                # No new frame yet
                time.sleep(0.01)
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord("q"):  # ESC or q
                    break
                continue

            last_frame_counter = frame_counter

            # Read pixel data
            frame_raw = bytes(buf[HEADER_BYTES : HEADER_BYTES + pixel_bytes])
            frame = np.frombuffer(frame_raw, dtype=np.uint8).reshape((height, width, channels))

            cv2.imshow("ZED SHM Viewer", frame)

            # Resize the window once on first valid frame
            if not first_frame_shown:
                cv2.resizeWindow("ZED SHM Viewer", width, height)
                first_frame_shown = True
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):  # ESC or q
                break

    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted by user.")
    finally:
        cv2.destroyAllWindows()
        shm_block.close()
        print("[CLIENT] Detached from shared memory.")


if __name__ == "__main__":
    main()

