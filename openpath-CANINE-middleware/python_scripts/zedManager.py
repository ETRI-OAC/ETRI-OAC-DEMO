import os
import pyzed.sl as sl

CAMERA_FPS = 30

class zedManager:
    def __init__(self,SharedMemoryManager):
        self.shm = SharedMemoryManager
        self.camera_fps = CAMERA_FPS
        self.zed = sl.Camera()
        self.image_left = sl.Mat()
        self.image_right = sl.Mat()
        self.save_dir = "./zed_image"
        os.makedirs(self.save_dir, exist_ok=True)
        self.open_camera()

    def __del__(self):
        self.close_camera()
        self.zed.close()
        print("[ZED] Closed ZED Camera.")

    def open_camera(self):
        # Open the camera
        init_params = sl.InitParameters()
        init_params.camera_resolution = sl.RESOLUTION.AUTO  # Use HD720 opr HD1200 video mode, depending on camera type.
        init_params.camera_fps = self.camera_fps                 # Set camera fps
        err = self.zed.open(init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print("[ZED] Camera Open : "+repr(err)+". Exit program.")
            exit()
        else:
            print("[ZED] Initialized ZED Camera.")

    def close_camera(self):
        self.zed.close()

    def get_image(self):
        print("get image1")
        runtime_parameters = sl.RuntimeParameters()
        if self.zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
            self.zed.retrieve_image(self.image_left, sl.VIEW.LEFT)
            self.zed.retrieve_image(self.image_right, sl.VIEW.LEFT)
            self.time_stamp = self.zed.get_timestamp(sl.TIME_REFERENCE.CURRENT)
            self.shm.left_image[0] = self.image_left
            self.shm.right_image[0] = self.image_right
        print("get image2")

    def save_image(self):
        filename = os.path.join(self.save_dir, f"zed_image_left.png")
        self.shm.left_image[0].write(filename)
        filename = os.path.join(self.save_dir, f"zed_image_right.png")
        self.shm.right_image[0].write(filename)
        print("Saved images")