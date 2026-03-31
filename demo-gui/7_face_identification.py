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
from utils.transformations import rotation_matrix_to_quaternion
sys.path.append(os.path.join(PROJECT_ROOT, 'hailo-inference'))
from face_recognizer import coco17_to_arcface_landmarks

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float64MultiArray

class faceTracking(Node):
    def __init__(self):
        super().__init__('face_tracking')
        self.zed_client = ZedClient()
        self.face_recognition_client = FaceRecognitionClient()
        self.pid = PIDControllerClass(k_p= 20, k_d = 1)
        self.pid.reset()
        self.tolerance = 10 # degrees
        self.dt = 1.0/30.0
        self.t_s = time.time()
        self.t_prev = time.time()
        self.center_cam_xy = np.array([self.zed_client.image_shape[1]/2, self.zed_client.image_shape[0]/2])

        self.pantilt_state = [0., 0.]
        self.pantilt_command = [0., 0.]
        self.face_id_memory = {} # {id: name}
        self.target_id = 0

        # init cv2 window
        if self.zed_client.shm_image_block is None:
            print("[CLIENT] Image shared memory not available. Is the server running?")
            return
        self.image_width = self.zed_client.image_shape[1]
        self.image_height = self.zed_client.image_shape[0]
        cv2.namedWindow("ZED Client - Body Tracking", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("ZED Client - Body Tracking", self.image_width, self.image_height)

        self.face_recognition_cnt = 0
        self.not_unknown_cnt = 0
        self.recognition_name = None

        self.pub_face_pose = self.create_publisher(PoseStamped, 'face_pose', 10)
        self.sub_pantilt_state = self.create_subscription(Float64MultiArray, 'pantilt_state', self.pantilt_state_callback, 10)
        self.pub_pantilt_command = self.create_publisher(Float64MultiArray, 'pantilt_command', 10)
        self.timer = self.create_timer(0.02, self.timer_callback)

    def pantilt_state_callback(self, msg):
        self.pantilt_state = msg.data
    
    def publish_pantilt_command(self):
        msg = Float64MultiArray()
        msg.data = self.pantilt_command
        self.pub_pantilt_command.publish(msg)

    def crop_face(self, image, body):
        face_bbox_2d = np.array(body['head_bounding_box_2d'])
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
    
    def move_pantilt(self, body):
        # get face xy from body
        face_xy = np.array(body['keypoints_2d'][0])

        # get current pantilt position
        current_position = np.array(self.pantilt_state)

        # calculate target pantilt position
        err_pixel = face_xy - self.center_cam_xy
        err_pixel[0] = -err_pixel[0]/self.center_cam_xy[0]
        err_pixel[1] = err_pixel[1]/self.center_cam_xy[1]
        t_curr = time.time() - self.t_s
        self.pid.update_with_error(t_curr = t_curr, err_curr = err_pixel)
        target_position = current_position + self.pid.out()
        self.pantilt_command = target_position.tolist()
        self.publish_pantilt_command()
    
    def overlay_bodies_on_image(self, image, bodies):
        if bodies is not None and len(bodies) > 0:
            image = visualize_bodies_2d(image, bodies, body_format=34)
        return image
    
    def overlay_face_recognition_result(self, image, face_bbox, id, name, similarity, info=None):
        x1, y1, x2, y2 = face_bbox
        image = cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        if info is None:
            text = f"ID: {id} / {name} / ({similarity:.2f})"
        else:
            text = f"ID: {id} / {name} / ({similarity:.2f} / {info})"

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

    def overlay_face_bbox(self, image, face_bbox, id, name="not recognized"):
        x1, y1, x2, y2 = face_bbox
        text = f"ID: {id} / {name}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0  # twice as big as 0.5
        thickness = 3

        # Get boundary of text
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        rect_x1 = x1
        rect_y1 = y2 + 5
        rect_x2 = x1 + text_width + 10   # padding
        rect_y2 = y2 + text_height + 15  # padding

        if name == "not recognized": # yellow color
            color = (0, 255, 255)
        elif name == "unknown": # red
            color = (0, 0, 255)
        else: # green
            color = (0, 255, 0)
        image = cv2.rectangle(image, (x1, y1), (x2, y2), color, 2) # bbox
        cv2.rectangle(image, (rect_x1, rect_y1), (rect_x2, rect_y2), color, -1) # text background

        # Draw text (black)
        text_org = (x1 + 5, y2 + text_height + 5)
        cv2.putText(image, text, text_org, font, font_scale, (0, 0, 0), thickness, lineType=cv2.LINE_AA)

        return image

    def publish_face_pose(self, body):
        face_position = body['head_position']
        face_orientation = body['head_orientation']
        
        face_pose = PoseStamped()
        face_pose.header.stamp = self.get_clock().now().to_msg()
        face_pose.header.frame_id = 'camera_left'
        face_pose.pose.position.x = face_position[0]
        face_pose.pose.position.y = face_position[1]
        face_pose.pose.position.z = face_position[2]
        face_pose.pose.orientation.x = face_orientation[0]
        face_pose.pose.orientation.y = face_orientation[1]
        face_pose.pose.orientation.z = face_orientation[2]
        face_pose.pose.orientation.w = face_orientation[3]
        self.pub_face_pose.publish(face_pose)

    def is_person_looking_at_cam(self, body, threshold=20):
        face_orientation = body['head_orientation']
        # get yaw from quaternion
        sin_yaw = 2 * (face_orientation[3]*face_orientation[2] + face_orientation[0]*face_orientation[1])
        cos_yaw = 1 - 2 * (face_orientation[1]*face_orientation[1] + face_orientation[2]*face_orientation[2])
        yaw = np.arctan2(sin_yaw, cos_yaw)
        if abs(yaw) > np.deg2rad(180 - threshold):
            return True
        else:
            return False

    def sleep(self):
        t_curr = time.time()
        if t_curr - self.t_prev < self.dt:
            time.sleep(self.dt - (t_curr - self.t_prev))
        self.t_prev = t_curr

    def close(self):
        cv2.destroyAllWindows()
        self.zed_client.close()

    def imshow(self, image):
        cv2.imshow("ZED Client - Body Tracking", image)
        cv2.waitKey(1)

    def timer_callback(self):
        image = self.zed_client.grab_image()
        image_display = image.copy()
        bodies = self.zed_client.grab_bodies()

        if bodies is not None and len(bodies) > 0:
            image_display = self.overlay_bodies_on_image(image_display, bodies)
            if self.target_id < bodies[0]['id']: # new person detected
                self.target_id = bodies[0]['id']

        for body in bodies: # if person detected
            if body['id'] == self.target_id:
                self.publish_face_pose(body)
                face_image, bbox = self.crop_face(image, body)
                if face_image is not None: # if face is in the image (not out of bounds)
                    lmks = coco17_to_arcface_landmarks(body['keypoints_2d'], bbox.tolist())
                    lmks_list = lmks.tolist() if lmks is not None else None
                    result,_ = self.face_recognition_client.recognize(face_image, landmarks=lmks_list, measure_time=False)
                    is_looking_at_cam = self.is_person_looking_at_cam(body)
                    image_display = self.overlay_face_recognition_result(image_display, bbox, body['id'], result['name'], result['similarity'], "looking" if is_looking_at_cam else "not looking")
                self.move_pantilt(body)

                if is_looking_at_cam:
                    if result['name'] != "Unknown": 
                        if self.recognition_name is None: # first recognition
                            self.recognition_name = result['name']
                        else:
                            self.face_recognition_cnt += 1
                            self.not_unknown_cnt += 1

                    if self.face_recognition_cnt > 20: # if face recognition is successful for 20 frames
                        if self.not_unknown_cnt > 5: # if not unknown for 5 rames out of 20 frames
                            self.face_id_memory[body['id']] = self.recognition_name
                        else:
                            self.face_id_memory[body['id']] = "Unknown"
                        # update target id and initialize counters
                        self.target_id += 1
                        self.face_recognition_cnt = 0
                        self.not_unknown_cnt = 0
                        self.recognition_name = None
                else: # the person is not looking at the camera
                    # initialize counters
                    self.face_recognition_cnt = 0
                    self.not_unknown_cnt = 0
                    self.recognition_name = None
            else:
                _, bbox = self.crop_face(image_display, body)
                if body['id'] in self.face_id_memory:
                    name = self.face_id_memory[body['id']]
                else:
                    name = "not recognized"
                if bbox is not None: # if face is in the image (not out of bounds)
                    image_display = self.overlay_face_bbox(image_display, bbox, body['id'], name)

        self.imshow(image_display)

def main():
    rclpy.init()
    face_tracking = faceTracking()
    try:
        rclpy.spin(face_tracking)
    except KeyboardInterrupt:
        print("Keyboard interrupt")
    finally:
        face_tracking.close()
        rclpy.shutdown()
        print("Face tracking closed")

if __name__ == "__main__":
    main()
