import os
import sys
import cv2
import numpy as np

# Add clients directory to path for ZedClient import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'clients'))
from zed_client import ZedClient

CAMERA_FPS = 30

class zedManager:
    """Camera manager that reads from shared memory (OAK-D or ZED server).

    Uses ZedClient (SHM-based) instead of opening a separate camera instance.
    The camera server (oak_server.py or zed_server.py) must be running.
    """
    def __init__(self, SharedMemoryManager):
        self.shm = SharedMemoryManager
        self.camera_fps = CAMERA_FPS
        self.client = None
        self.save_dir = "./zed_image"
        os.makedirs(self.save_dir, exist_ok=True)
        self.open_camera()

    def __del__(self):
        self.close_camera()
        print("[CAM] Closed camera client.")

    def open_camera(self):
        try:
            self.client = ZedClient()
            if self.client.shm_image_block is not None:
                print("[CAM] Connected to camera shared memory.")
            else:
                print("[CAM] Warning: Camera shared memory not available. Is the server running?")
        except Exception as e:
            print(f"[CAM] Failed to connect to camera shared memory: {e}")

    def close_camera(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    def get_image(self):
        if self.client is None:
            return
        image = self.client.grab_image(wait_for_new=False, timeout=0.1)
        if image is not None:
            self.shm.left_image[0] = image
            self.shm.right_image[0] = image  # Same image for both (stereo not needed here)

    def save_image(self):
        if self.shm.left_image[0] is not None:
            filename = os.path.join(self.save_dir, "zed_image_left.png")
            cv2.imwrite(filename, self.shm.left_image[0])
            filename = os.path.join(self.save_dir, "zed_image_right.png")
            cv2.imwrite(filename, self.shm.right_image[0])
            print("Saved images")
