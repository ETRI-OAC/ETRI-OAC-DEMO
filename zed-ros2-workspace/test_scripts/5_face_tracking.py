# add higher directory path
import sys
import os
import cv2

import time
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zed_wrapper.zed_client import ZedClient
from zed_wrapper.body_tracking_visualizer import visualize_bodies_2d
from openpath_CANINE_middleware.python_scripts.pantiltManager import pantiltManager
from utils.pid import PIDControllerClass

class faceTracking:
    def __init__(self):
        self.zed_client = ZedClient()
        self.pantilt = pantiltManager()
        self.pantilt.reset_error()
        self.pid = PIDControllerClass(k_p= 20, k_d = 1)
        self.pid.reset()
        self.tolerance = 10 # degrees
        self.dt = 1.0/30.0
        self.t_s = time.time()
        self.center_cam_xy = np.array([self.zed_client.image_shape[1]/2, self.zed_client.image_shape[0]/2])

        self.pantilt.set_position(np.array([0, 0]))

        # init cv2 window
        if self.zed_client.shm_image_block is None:
            print("[CLIENT] Image shared memory not available. Is the server running?")
            return
        self.image_width = self.zed_client.image_shape[1]
        self.image_height = self.zed_client.image_shape[0]
        cv2.namedWindow("ZED Client - Body Tracking", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("ZED Client - Body Tracking", self.image_width, self.image_height)
        cv2.namedWindow("Face", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Face", int(1), int(1))
    
    def crop_face(self, image, bodies):
        if len(bodies) == 0:
            print("[CROP FACE] No face found")
            return None
        face_bbox_2d = np.array(bodies[0]['head_bounding_box_2d'])
        x1 = face_bbox_2d[0][0]
        x2 = face_bbox_2d[1][0]
        y1 = face_bbox_2d[1][1]
        y2 = face_bbox_2d[2][1]
        x1_c = np.clip(x1, 1, self.image_width-1)
        x2_c = np.clip(x2, 1, self.image_width-1)
        y1_c = np.clip(y1, 1, self.image_height-1)
        y2_c = np.clip(y2, 1, self.image_height-1)
        face_image = image[y1_c:y2_c, x1_c:x2_c]
        if face_image.size == 0:
            print("[CROP FACE] OUT OF BOUNDS")
        else:
            face_image = cv2.resize(face_image, (face_image.shape[1]*3, face_image.shape[0]*3))
            cv2.imshow("Face", face_image)
            cv2.waitKey(1)
        return face_image
    
    def move_pantilt(self, bodies):
        if len(bodies) > 0:
            face_xy = np.array(bodies[0]['keypoints_2d'][0])
        else:
            print("[PANTILT] No face found")
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
    
    def overlay_bodies_on_image(self, image, bodies):
        if bodies is not None and len(bodies) > 0:
            image = visualize_bodies_2d(image, bodies, body_format=18)
        return image

    def imshow(self, image):
        cv2.imshow("ZED Client - Body Tracking", image)
        cv2.waitKey(1)
    
    def close(self):
        cv2.destroyAllWindows()
        self.zed_client.close()
        self.pantilt.disable_torque()
        self.pantilt.close_dxl()

def main():
    face_tracking = faceTracking()
    try:
        while True:
            image = face_tracking.zed_client.grab_image()
            bodies = face_tracking.zed_client.grab_bodies()
            if bodies is not None and len(bodies) > 0:
                face_image = face_tracking.crop_face(image, bodies)
                image = face_tracking.overlay_bodies_on_image(image, bodies)
                face_tracking.move_pantilt(bodies)
            
            face_tracking.imshow(image)
            time.sleep(face_tracking.dt)

    except KeyboardInterrupt:
        print("Keyboard interrupt")

    finally:
        face_tracking.close()
        print("Face tracking closed")

if __name__ == "__main__":
    main()
