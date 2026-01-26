# add higher directory path
import sys
import os
import time
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zed_wrapper.zed_client import ZedClient
from openpath_CANINE_middleware.python_scripts.pantiltManager import pantiltManager
from utils.pid import PIDControllerClass

class faceTracking:
    def __init__(self):
        self.zed_client = ZedClient()
        self.pantilt = pantiltManager()
        self.pantilt.reset_error()
        self.pid = PIDControllerClass(k_p= 10, k_d = 1)
        self.pid.reset()
        self.tolerance = 10 # degrees
        self.dt = 0.05
        self.t_s = time.time()
        self.center_cam_xy = np.array([self.zed_client.image_shape[1]/2, self.zed_client.image_shape[0]/2])

        self.pantilt.set_position(np.array([0, 0]))
    
    def move_pantilt(self):
        # get face position from zed_client
        bodies = self.zed_client.grab_bodies()
        if len(bodies) > 0:
            face_xy = np.array(bodies[0]['keypoints_2d'][0])
            print("face_xy: ", face_xy)
        else:
            print("No face found")
            return
        
        # get current pantilt position
        current_position = self.pantilt.read_position()

        # calculate target pantilt position
        err_pixel = face_xy - self.center_cam_xy
        err_pixel[0] = -err_pixel[0]/self.center_cam_xy[0]
        err_pixel[1] = err_pixel[1]/self.center_cam_xy[1]
        t_curr = time.time() - self.t_s
        self.pid.update_with_error(t_curr = t_curr, err_curr = err_pixel)
        target_position = current_position + self.pid.out()
        self.pantilt.set_position(target_position)

        # sleep
        time.sleep(self.dt)
    
    def close(self):
        self.zed_client.close()
        self.pantilt.disable_torque()
        self.pantilt.close_dxl()

def main():
    face_tracking = faceTracking()
    try:
        while True:
            face_tracking.move_pantilt()
    except KeyboardInterrupt:
        print("Keyboard interrupt")
    finally:
        face_tracking.close()
        print("Face tracking closed")

if __name__ == "__main__":
    main()
