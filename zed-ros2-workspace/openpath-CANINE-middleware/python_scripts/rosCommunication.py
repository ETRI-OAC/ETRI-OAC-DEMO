import numpy as np
from rclpy.node import Node
from canine_msgs_v2.msg import CANINECommand,CANINEState

class ROSCommunication(Node):
    def __init__(self,SharedMemoryManager):
        super().__init__('ros_python_communication')
        self.subscription_canine_states = self.create_subscription(
            CANINEState,
            'canine_states',
            self.topic_callback_canine_states,
            10
        )

        self.publisher_canine_command = self.create_publisher(
            CANINECommand,
            'canine_command'
            ,10
        )

        self.timer_canine_command = self.create_timer(0.02, self.timer_callback)

        self.subscription_canine_states
        self.publisher_canine_command
        self.timer_canine_command
        
        self.shm = SharedMemoryManager
        self.cnt = 0
        self.prevCMD = -1

    def topic_callback_canine_states(self, msg):
        self.shm.middleware_connected = True
        self.shm.local_time = msg.local_time
        self.shm.fsm_state = msg.fsm_state

        self.shm.global_base_position = np.array([msg.global_base_position.x, msg.global_base_position.y, msg.global_base_position.z])
        self.shm.global_base_velocity = np.array([msg.global_base_velocity.x, msg.global_base_velocity.y, msg.global_base_velocity.z])
        self.shm.global_base_angular_velocity = np.array([msg.global_base_angular_velocity.x, msg.global_base_angular_velocity.y, msg.global_base_angular_velocity.z])
        self.shm.global_base_euler_angle = np.array([msg.global_base_euler_angle.x, msg.global_base_euler_angle.y, msg.global_base_euler_angle.z])
        self.shm.global_base_quaternion = np.array([msg.global_base_quaternion.x, msg.global_base_quaternion.y, msg.global_base_quaternion.z, msg.global_base_quaternion.w])
        
        self.shm.body_base_velocity = np.array([msg.body_base_velocity.x, msg.body_base_velocity.y, msg.body_base_velocity.z])
        self.shm.body_base_angular_velocity = np.array([msg.body_base_angular_velocity.x, msg.body_base_angular_velocity.y, msg.body_base_angular_velocity.z])

        # For debugging
        # self.get_logger().info(f'Local Time: {self.shm.local_time}')
        # print('Gait Table \n',self.shm.gait_table)
        # print('Global Base Position \n',self.shm.global_base_position)
        # print('Global Base Velocity \n',self.shm.global_base_velocity)
        # print('Body Base Velocity \n',self.shm.body_base_velocity)
        # print('Global Base Quaternion \n',self.shm.global_base_quaternion)


    def timer_callback(self):
        msg = CANINECommand()
        msg = self.shm.cmd

        if self.prevCMD == self.shm.cmd.command:
            self.cnt = self.cnt + 1
        else:
            self.cnt = 0

        # if self.cnt > 50:
        #     self.cnt = 0
        #     self.shm.cmd.command = 0

        self.prevCMD = self.shm.cmd.command
        self.publisher_canine_command.publish(msg)

