# add higher directory path
import sys
import os
import cv2

import time
import numpy as np
# Add project root and oak-camera to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'oak-camera'))
from clients.zed_client import ZedClient
from clients.face_recognition_client import FaceRecognitionClient
from clients.vlm_client import VLLMClient
from clients.body_tracking_visualizer import visualize_bodies_2d
from openpath_CANINE_middleware.python_scripts.pantiltManager import pantiltManager
from utils.pid import PIDControllerClass

class faceTracking:
    def __init__(self):
        self.zed_client = ZedClient()
        self.face_recognition_client = FaceRecognitionClient()
        self.pantilt = pantiltManager()
        self.pantilt.reset_error()
        self.pid = PIDControllerClass(k_p= 20, k_d = 1)
        self.pid.reset()
        self.tolerance = 10 # degrees
        self.dt = 1.0/30.0
        self.t_s = time.time()
        self.t_prev = time.time()
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
    
    def crop_face(self, image, bodies):
        if len(bodies) == 0:
            print("[CROP FACE] No face found")
            return None, None
        face_bbox_2d = np.array(bodies[0]['head_bounding_box_2d'])
        x1 = face_bbox_2d[0][0]
        x2 = face_bbox_2d[1][0]
        y1 = face_bbox_2d[1][1] - 50 # HEURISTIC: add 50 pixels to the top of the face
        y2 = face_bbox_2d[2][1]
        x1_c = np.clip(x1, 1, self.image_width-1)
        x2_c = np.clip(x2, 1, self.image_width-1)
        y1_c = np.clip(y1, 1, self.image_height-1)
        y2_c = np.clip(y2, 1, self.image_height-1)
        face_image = image[y1_c:y2_c, x1_c:x2_c]
        if face_image.size == 0:
            print("[CROP FACE] OUT OF BOUNDS")
            return None, None
        else:
            bbox = np.array([x1_c, y1_c, x2_c, y2_c])
        return face_image, bbox
    
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
            image = visualize_bodies_2d(image, bodies, body_format=34)
        return image
    
    def overlay_face_recognition_result(self, image, face_bbox, result):
        x1, y1, x2, y2 = face_bbox
        image = cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        text = f"{result['name']} ({result['similarity']:.2f})"

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0  # twice as big as 0.5
        thickness = 3

        # Get boundary of text
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        rect_x1 = x1
        rect_y1 = y2 + 5
        rect_x2 = x1 + text_width + 10   # padding
        rect_y2 = y2 + text_height + 15  # padding

        # Draw filled rectangle for background (red)
        cv2.rectangle(image, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 0, 255), -1)

        # Draw text (white)
        text_org = (x1 + 5, y2 + text_height + 5)
        cv2.putText(image, text, text_org, font, font_scale, (255, 255, 255), thickness, lineType=cv2.LINE_AA)

        return image

    def imshow(self, image):
        cv2.imshow("ZED Client - Body Tracking", image)
        cv2.waitKey(1)
    
    def sleep(self):
        t_curr = time.time()
        if t_curr - self.t_prev < self.dt:
            time.sleep(self.dt - (t_curr - self.t_prev))
        self.t_prev = t_curr

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
            T_base2cam_left = face_tracking.pantilt.get_T_base2cam_left()
            
            if bodies is not None and len(bodies) > 0: # if face detected
                face_image, bbox = face_tracking.crop_face(image, bodies)
                if face_image is not None: # if face is in the image (not out of bounds)
                    result,_ = face_tracking.face_recognition_client.recognize(face_image, measure_time=False)
                    image = face_tracking.overlay_bodies_on_image(image, bodies)
                    image = face_tracking.overlay_face_recognition_result(image, bbox, result)
                face_tracking.move_pantilt(bodies)
            
            face_tracking.imshow(image)
            face_tracking.sleep()

    except KeyboardInterrupt:
        print("Keyboard interrupt")

    finally:
        face_tracking.close()
        print("Face tracking closed")

if __name__ == "__main__":
    main()
