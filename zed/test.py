import os
import cv2
import numpy as np
import pyzed.sl as sl

CAMERA_FPS = 30

class zedManager:
    def __init__(self):
        self.camera_fps = CAMERA_FPS
        self.zed = sl.Camera()
        self.image_left = sl.Mat()
        self.image_right = sl.Mat()
        self.save_dir = "./zed_image"
        os.makedirs(self.save_dir, exist_ok=True)
        # Open cv2 window
        cv2.namedWindow("ZED Camera", cv2.WINDOW_NORMAL)
        self.open_camera()

    def __del__(self):
        self.close_camera()
        self.zed.close()
        print("[ZED] Closed ZED Camera.")

    def open_camera(self):
        # Open the camera
        init_params = sl.InitParameters()
        init_params.camera_resolution = sl.RESOLUTION.AUTO  # Use HD720 opr HD1200 video mode, depending on camera type.
        init_params.camera_fps = 30                 # Set camera fps
        err = self.zed.open(init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print("[ZED] Camera Open : "+repr(err)+". Exit program.")
            exit()
        else:
            print("[ZED] Initialized ZED Camera.")
            # Get one image to determine window size
            runtime_parameters = sl.RuntimeParameters()
            if self.zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
                self.zed.retrieve_image(self.image_left, sl.VIEW.LEFT_BGR)
                # Get image dimensions and set window size
                height = self.image_left.get_height()
                width = self.image_left.get_width()
                cv2.resizeWindow("ZED Camera", width, height)
                print(f"[ZED] Window size set to {width}x{height}")

    def close_camera(self):
        self.zed.close()

    def get_image(self):
        runtime_parameters = sl.RuntimeParameters()
        if self.zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
            self.zed.retrieve_image(self.image_left, sl.VIEW.LEFT_BGR)
            self.time_stamp = self.zed.get_timestamp(sl.TIME_REFERENCE.CURRENT)
            return True
        return False
    
def main():
    zed_test = zedManager()
    try:
        while True:
            if zed_test.get_image():
                # Convert ZED Mat to numpy array for OpenCV display
                image_ocv = zed_test.image_left.get_data()
                # Display the image
                cv2.imshow("ZED Camera", image_ocv)
                # Break loop on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                print("[ZED] Failed to grab image")
                break
    except KeyboardInterrupt:
        pass
    finally:
        zed_test.close_camera()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()