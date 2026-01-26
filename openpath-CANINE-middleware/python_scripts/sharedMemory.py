import numpy as np
from canine_msgs_v2.msg import CANINECommand

np.set_printoptions(precision=3)

class SharedMemoryManager:
    def __init__(self):
        # Canine states information
        self.local_time = 0.0
        self.fsm_state = -1
        self.global_base_position = np.zeros(3)
        self.global_base_velocity = np.zeros(3)
        self.global_base_euler_angle = np.zeros(3)
        self.global_base_quaternion = np.zeros(4)
        self.global_base_angular_velocity = np.zeros(3)
        self.body_base_velocity = np.zeros(3)
        self.body_base_angular_velocity = np.zeros(3)
        self.middleware_connected = False

        self.cmd = CANINECommand()
        self.cmd.command = 0
        self.cmd.reference_base_velocity = [0.0, 0.0]
        self.cmd.reference_base_yaw_velocity = 0.0

        self.pantilt_position = np.zeros(2)
        self.pantilt_goal_position = np.zeros(2)

        self.left_image = {}
        self.right_image = {}