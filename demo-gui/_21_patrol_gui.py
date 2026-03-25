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
from clients.stt_client import STTClient
from clients.tts_client import TTSClient
from clients.face_recognition_client import FaceRecognitionClient
# from clients.vlm_client import VLLMClient
from _20_vlm_gui import VLLMClient, VLLMThread
from zed_wrapper.body_tracking_visualizer import visualize_bodies_2d
from utils.pid import PIDControllerClass

# GUI
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from gui_threads import DemoQtWidget

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float64MultiArray
from action_msgs.srv import CancelGoal
from action_msgs.msg import GoalStatusArray
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

# WAYPOINTS = [((-2.88689, -1.29752, 0., 0., 0., -0.417859, 0.908512)), #(x,y,z,qx,qy,qz,qw)
#             ((1.56717, -6.46273, 0., 0., 0., -0.418961, 0.908004)),
#             ((3.58321, -8.42727, 0., 0., 0., -0.399719, 0.916638)),
#             # ((7.33938, -12.266, 0., 0., 0., -0.407712, 0.913111))
# ]

WAYPOINTS = [((0.694054, -8.85587, 0., 0., 0., -0.684484, 0.729028)), #(x,y,z,qx,qy,qz,qw)
            ((-4.57819, -14.2423, 0., 0., 0., -0.711791, 0.702391)),
            ((-5.20466, -22.4224, 0., 0., 0., -0.666923, 0.745127)),
            ((3.49335, -35.6834, 0., 0., 0., -0.68235, 0.731026))
]



class faceIdentificationWithNav(Node):
    def __init__(self, zed_client, tts_client, face_recognition_client, use_navigation= True, use_audio=True):
        super().__init__('face_identification_with_nav')

        # Init zed client and tts client
        self.zed_client = zed_client
        self.image_display = self.zed_client.grab_image()
        self.tts_client = tts_client
        
        # Init face recognition
        self.face_recognition_client = face_recognition_client
        self.face_id_memory = {} # {id: name}
        self.recognized_names = set() # set of recognized names
        self.target_id = 0
        self.target_id_prev = 0
        self.face_recognition_cnt = 0
        self.not_unknown_cnt = 0
        self.not_looking_cnt = 0
        self.recognition_name = None
        self.use_audio = use_audio
        self.use_navigation = use_navigation

        # Init pan-tilt
        self.pantilt_state = [0., -30.]
        self.pantilt_command = [0., -30.]
        self.pid = PIDControllerClass(k_p= 30, k_d = 1, out_min=-30, out_max=30, dim=1, out_alpha=0.5)
        self.pid.reset()
        self.center_cam_xy = np.array([self.zed_client.image_shape[1]/2, self.zed_client.image_shape[0]/2])
        self.t_s = time.time()

        # Init navigation
        self.navigation_status = "Waiting"
        self.navigation_resume_flag = True
        self.current_waypoint_index = 0
        self.waypoints = WAYPOINTS
        self.stop = False

        # Init cv2 window
        if self.zed_client.shm_image_block is None:
            print("[CLIENT] Image shared memory not available. Is the server running?")
            return
        self.image_width = self.zed_client.image_shape[1]
        self.image_height = self.zed_client.image_shape[0]
        # cv2.namedWindow("ZED Client - Body Tracking", cv2.WINDOW_NORMAL)
        # cv2.resizeWindow("ZED Client - Body Tracking", self.image_width, self.image_height)

        # Init ROS2 Components
        self.pub_face_pose = self.create_publisher(PoseStamped, 'face_pose', 10)
        self.sub_pantilt_state = self.create_subscription(Float64MultiArray, 'pantilt_state', self.pantilt_state_callback, 10)
        self.pub_pantilt_command = self.create_publisher(Float64MultiArray, 'pantilt_command', 10)
        self.subscription = self.create_subscription(GoalStatusArray,'/navigate_to_pose/_action/status',self.nav_status_callback, 1)
        self.timer = self.create_timer(0.02, self.timer_callback)
        self.timer_flag = False

        # Init pan-tilt pose
        for _ in range(30):
            print(f"[PAN-TILT] Publishing command: {self.pantilt_command}")
            self.publish_pantilt_command()
            time.sleep(0.02)

    """___MAIN LOOP___"""
    def timer_callback(self):
        # print("A")
        # Update Navigation Status
        if self.use_navigation:
            self.handle_nav_goal()
        # if self.stop:
        #     # print("[NAV2] Stop Flag On")
        #     time.sleep(0.01)
        #     return

        # Update Image and Bodies from ZED
        image = self.zed_client.grab_image()
        self.image_display = image.copy()
        bodies = self.zed_client.grab_bodies()
        # print("B")
        # Check if person detected
        if bodies is not None and len(bodies) > 0: # at least one person detected
            self.image_display = self.overlay_bodies_on_image(self.image_display, bodies)
            bodies = self.filter_bodies(bodies, 2.3) # Leave only bodies in the threshold distance
            filtered_body_ids = self.get_body_ids(bodies)
            not_treated_ids = []
            for id in filtered_body_ids:
                if not id in self.face_id_memory.keys():
                    not_treated_ids.append(id)

            if len(not_treated_ids) > 0:
                self.target_id = not_treated_ids[0]
                face_recognition_flag = True
            else:
                face_recognition_flag = False
            
            # Check if the target id is changed
            if self.target_id_prev != self.target_id:
                self.target_id_prev = self.target_id
                # initialize face recognition counters
                self.not_looking_cnt = 0
                self.face_recognition_cnt = 0
                self.not_unknown_cnt = 0
                self.recognition_name = None

            # Stop Navigation if there is a person who is not treated before
            if self.navigation_status == "Navigating" and face_recognition_flag:
                print("Face recognition started, canceling navigation")
                self.cancel_nav2_navigation()
                # time.sleep(0.1)
                return
            # Resume Navigation if there is no person who is not treated before
            elif self.navigation_status == "Cancelled" and not face_recognition_flag:
                print("Face recognition ended, resuming navigation")
                self.navigation_resume_flag = True
                # time.sleep(0.5)
                time.sleep(0.01)
                return
        else: # nobody detected
            if self.navigation_status == "Cancelled":
                self.navigation_resume_flag = True
                # time.sleep(0.5)
                time.sleep(0.01)
                return

        # print("C")
        # Process each face in the threshold distance
        for body in bodies:
            if body['id'] == self.target_id:
                self.publish_face_pose(body) # publish face pose, which will be used in future
                face_image, bbox = self.crop_face(image, body)
                if face_image is not None: # if face is in the image (not out of bounds)
                    # Check if the person is looking at the camera
                    is_looking_at_cam = self.is_person_looking_at_cam(body)
                    if is_looking_at_cam:
                        result,_ = self.face_recognition_client.recognize(face_image, measure_time=False)
                        self.overlay_face_recognition_result(self.image_display, bbox, body['id'], result['name'], result['similarity'], "looking")
                        self.not_looking_cnt = 0 # reset not looking counter
                        self.face_recognition_cnt += 1
                        if result['name'] != "Unknown": 
                            if self.recognition_name is None: # first recognition
                                self.recognition_name = result['name']
                            else:
                                self.not_unknown_cnt += 1
                            if result['name'] in self.recognized_names: # already recognized
                                # update target id and initialize counters
                                self.face_id_memory[body['id']] = result['name']
                                self.target_id += 1
                                self.face_recognition_cnt = 0
                                self.not_unknown_cnt = 0
                                self.recognition_name = None
                        if self.face_recognition_cnt > 30: # if face recognition is successful for 20 frames
                            if self.not_unknown_cnt > 5: # if not unknown for 5 rames out of 20 frames
                                self.face_id_memory[body['id']] = self.recognition_name
                                self.recognized_names.add(self.recognition_name)
                                if self.use_audio:
                                    self.tts_client.speak(text=f"{self.recognition_name} 님 안녕하세요.")
                            else:
                                self.face_id_memory[body['id']] = "Unknown"
                                if self.use_audio:
                                    self.tts_client.speak(text="등록되지 않은 인물입니다. 확인 부탁드립니다.")
                            # update target id and initialize counters
                            self.target_id += 1
                            self.face_recognition_cnt = 0
                            self.not_unknown_cnt = 0
                            self.recognition_name = None
                    else: # the person is not looking at the camera
                        self.not_looking_cnt += 1
                        self.overlay_face_recognition_result(self.image_display, bbox, body['id'], "Recognizing...", 0.0, "not looking")
                        if self.not_looking_cnt > 60: # if not looking for 60 frames
                            if self.use_audio:
                                self.tts_client.speak(text="카메라를 응시해주세요")
                            # initialize counters
                            self.not_looking_cnt = 0
                            self.face_recognition_cnt = 0
                            self.not_unknown_cnt = 0
                            self.recognition_name = None
                self.move_pantilt(body)
            else: # the person is not the target person
                _, bbox = self.crop_face(image, body)
                if bbox is not None: # if face is in the image (not out of bounds)
                    self.overlay_face_bbox(self.image_display, bbox, body['id'], self.face_id_memory.get(body['id'], "Not recognized"))
        self.timer_flag = True
        # print("D")
        # self.imshow(self.image_display)
        # print("E")

    """___NAVIGATION FUNCTIONS___"""
    def send_navigation_goal(self, goal, frame_id='map'):
        """
            Send a navigation goal to Nav2
            Args:
                goal: (x,y,z,qx,qy,qz,qw)
            Returns:
                None
        """
        # 1. heavy
        client = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.get_logger().info('Waiting for Nav2 action server...')
        if not client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Nav2 action server not available!')
            return None
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = frame_id
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        # Set Position
        goal_msg.pose.pose.position.x = goal[0]
        goal_msg.pose.pose.position.y = goal[1]
        
        # Convert degrees to Quaternion for orientation (Z-axis rotation)
        goal_msg.pose.pose.orientation.z = goal[5]
        goal_msg.pose.pose.orientation.w = goal[6]

        self.get_logger().info(f'Goal sent to Nav2')
        send_goal_future = client.send_goal_async(goal_msg) # Bug: The client doesn't receive the response from the service


    def handle_nav_goal(self):
        """
            Handle navigation goal
        """
        if self.navigation_status == "Goal Reached":
            if self.current_waypoint_index < len(self.waypoints) - 1:
                print(f"Updating to waypoint {self.current_waypoint_index + 1}")
                self.current_waypoint_index += 1 # update waypoint index
                self.send_navigation_goal(self.waypoints[self.current_waypoint_index])
            else:
                print("Reached the last waypoint")
                self.navigation_status = "End"
                self.stop = True

        elif not self.stop and self.navigation_resume_flag:
            print(f"Resuming navigation to waypoint {self.current_waypoint_index}")
            self.navigation_resume_flag = False
            self.pantilt_command = [0.,-30.]
            self.publish_pantilt_command()
            self.send_navigation_goal(self.waypoints[self.current_waypoint_index])
        # # print("Handling navigation goal")
        # # print("navigation status:", self.navigation_status)
        # if self.stop and self.navigation_status not in  ["Cancelled", "Goal Reached"]:
        #     self.cancel_nav2_navigation()
        #     # self.navigation_resume_flag = True
        # elif self.navigation_status == "Goal Reached":
        #     if self.current_waypoint_index < len(self.waypoints) - 1:
        #         print(f"Updating to waypoint {self.current_waypoint_index + 1}")
        #         self.current_waypoint_index += 1 # update waypoint index
        #         self.send_navigation_goal(self.waypoints[self.current_waypoint_index])
        #     else:
        #         print("Reached the last waypoint")
        #         self.navigation_status = "End"
        #         self.stop = True
        # elif not self.stop and self.navigation_resume_flag: # kisang, here
        #     print(f"Resuming navigation to waypoint {self.current_waypoint_index}")
        #     self.navigation_resume_flag = False
        #     self.pantilt_command = [0.,-30.]
        #     self.publish_pantilt_command()
        #     self.send_navigation_goal(self.waypoints[self.current_waypoint_index])

    def cancel_nav2_navigation(self):
        """
        Sends a cancel request to Nav2
        """
        # 1. Create the service client
        # Note: Action services are hidden by default, so we use the full path
        client = self.create_client(CancelGoal, '/navigate_to_pose/_action/cancel_goal')

        self.get_logger().info('Waiting for cancel service...')
        if not client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('Cancel service not available!')
            return None

        # 2. Create the request
        # A UUID of all zeros [0,0...] tells Nav2 to cancel ALL active goals
        request = CancelGoal.Request()
        request.goal_info.goal_id.uuid = [0] * 16 
        request.goal_info.stamp.sec = 0
        request.goal_info.stamp.nanosec = 0
        
        # 3. Call the service and block until it finishes
        future = client.call_async(request) # Bug: The client doesn't receive the response from the service
        self.get_logger().info('Sent cancel request to Nav2')

    def nav_status_callback(self, msg):
        """
            Subscrilbe and save the navigation status
        """
        print(msg.status_list[-1].status)
        if msg.status_list[-1].status == 2:
            self.navigation_status = "Navigating"
        elif msg.status_list[-1].status == 5:
            self.navigation_status = "Cancelled"
        elif msg.status_list[-1].status == 4:
            self.navigation_status = "Goal Reached"
        else:
            self.navigation_status = "Unknown"
        print(f"[NAV STATUS] Recived status id: {msg.status_list[-1].status}, status: {self.navigation_status}")

    """___PAN-TILT FUNCTIONS___"""
    def pantilt_state_callback(self, msg):
        """
            Subscrilbe and save the pantilt state
        """
        self.pantilt_state = msg.data
    
    def publish_pantilt_command(self):
        """
            Publish the pantilt command in position (deg)
        """
        msg = Float64MultiArray()
        msg.data = self.pantilt_command
        self.pub_pantilt_command.publish(msg)

    def move_pantilt(self, body):
        """
        Move the pantilt motor to lock on the face of the given body on the middle of the image (only x-axis)
        """
        face_xy = np.array(body['keypoints_2d'][0])
        current_position = np.array(self.pantilt_state)

        # calculate target pantilt position
        err_pixel_x = face_xy[0] - self.center_cam_xy[0]
        err_pixel_x = -err_pixel_x/self.center_cam_xy[0]
        # err_pixel[1] = err_pixel[1]/self.center_cam_xy[1]
        t_curr = time.time() - self.t_s
        self.pid.update_with_error(t_curr = t_curr, err_curr = err_pixel_x)
        target_position = current_position
        target_position[0] += self.pid.out()
        self.pantilt_command = target_position.tolist()
        self.publish_pantilt_command()

    """___FACE RECOGNITION FUNCTIONS___"""
    def crop_face(self, image, body):
        """
            Crop the face of the given body on the middle of the image
            If the face is out of bounds, return None
        """
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

    def publish_face_pose(self, body):
        """
            Publish the face pose and orientations
        """
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
        """
            Check if the person is looking at the camera
            Args:
                body: the body of the person
                threshold: the threshold of the yaw angle
            Returns:
                True if the person is looking at the camera, False otherwise
        """
        face_orientation = body['head_orientation']
        # get yaw from quaternion
        sin_yaw = 2 * (face_orientation[3]*face_orientation[2] + face_orientation[0]*face_orientation[1])
        cos_yaw = 1 - 2 * (face_orientation[1]*face_orientation[1] + face_orientation[2]*face_orientation[2])
        yaw = np.arctan2(sin_yaw, cos_yaw)
        if abs(yaw) > np.deg2rad(180 - threshold):
            return True
        else:
            return False
    
    def speak_look_at_cam(self):
        """
            Speak the message to the user to look at the camera
        """
        text = "카메라를 응시해주세요"
        print("[TTS] speaking: ", text)
        response, _ = self.tts_client.speak(text=text)
        return response.get("success")

    """___VISULIZATION FUNCTIONS___"""
    def overlay_bodies_on_image(self, image, bodies):
        """
            Overlay the skeleton on the image
            Args:
                image: the image to overlay the bodies on
                bodies: the bodies to overlay on the image
            Returns:
                The image with the bodies overlaid
        """
        if bodies is not None and len(bodies) > 0:
            image = visualize_bodies_2d(image, bodies, body_format=34)
        return image
    
    def overlay_face_recognition_result(self, image, face_bbox, id, name, similarity, info=None):
        x1, y1, x2, y2 = face_bbox
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

        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.rectangle(image, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 0, 255), -1)

        # Draw text (white)
        text_org = (x1 + 5, y2 + text_height + 5)
        cv2.putText(image, text, text_org, font, font_scale, (255, 255, 255), thickness, lineType=cv2.LINE_AA)

    def overlay_face_bbox(self, image, face_bbox, id, name="Not recognized"):
        """
            Overlay the face bbox on the image
            If the face is not recognized yet, the box will be yellow
            If the face is in the database, the box will be green
            If the face is not in the database, the box will be orange
        """
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

        if name == "Not recognized":    # yellow color
            color = (0, 255, 255)
        elif name == "Unknown":         # orange color
            color = (0, 165, 255)
        else:                           # green color
            color = (0, 255, 0)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2) # bbox
        cv2.rectangle(image, (rect_x1, rect_y1), (rect_x2, rect_y2), color, -1) # text background

        # Draw text (black)
        text_org = (x1 + 5, y2 + text_height + 5)
        cv2.putText(image, text, text_org, font, font_scale, (0, 0, 0), thickness, lineType=cv2.LINE_AA)

    """___HELPERS___"""
    def close(self):
        cv2.destroyAllWindows()
        self.zed_client.close()

    def imshow(self, image):
        cv2.imshow("ZED Client - Body Tracking", image)
        cv2.waitKey(1)

    def filter_bodies(self, bodies, dist=6):
        bodies = [body for body in bodies if body['head_position'][0] **2 + body['head_position'][1] **2 < dist **2]
        return bodies

    def get_body_ids(self, bodies):
        return [body['id'] for body in bodies]

class PatrolThread(QThread):
    signal = pyqtSignal(object) # body_ids, image
    def __init__(self, patrol_client):
        super().__init__()
        self.client = patrol_client

    def run(self):
        cnt = 0
        while True:
            # spin ros2 node
            rclpy.spin_once(self.client, timeout_sec = 0.02)
            # print("ros2 node spinning!")
            # print("navigation status: ", self.client.navigation_status, "waypoint idx: ", self.client.current_waypoint_index/len(WAYPOINTS))
            if self.client.timer_flag == True:
                cnt += 1
                if cnt > 15:
                    self.signal.emit(self.client.image_display) # image


def main():
    app = QApplication(sys.argv)
    rclpy.init()
    stt_client = STTClient()
    tts_client = TTSClient()
    zed_client = ZedClient()
    face_recognition_client = FaceRecognitionClient()
    patrol_client = faceIdentificationWithNav(
        zed_client,
        tts_client,
        face_recognition_client,
        use_navigation= True,
        use_audio=True
        )
    patrol_thread = PatrolThread(patrol_client)
    # vllm_client = VLLMClient(
    #     api_url = "http://localhost:8000",
    #     stt_client = stt_client,
    #     tts_client = tts_client,
    #     zed_client = zed_client
    # )
    # vlm_thread = VLLMThread(vllm_client)
    qt_widget = DemoQtWidget(
        # vlm_thread=vlm_thread,
        vlm_thread=None,
        patrol_thread=patrol_thread,
        usertracking_thread=None
    )
    qt_widget.show()
    app.exec_()
    rclpy.shutdown()

if __name__ == "__main__":
    main()