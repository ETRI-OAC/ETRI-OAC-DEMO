import numpy as np
import rclpy
from rclpy.node import Node
from canine_msgs_v2.msg import CANINECommand,CANINEState
from geometry_msgs.msg import Twist
from pynput import keyboard
import time

class ROSCommunication(Node):
    def __init__(self):
        super().__init__('ros_python_communication')

        self.middleware_connected = False # For the first time connection check
        self.cmd = CANINECommand()
        self.last_cmd_time = 0.0
        self.command_timeout = 0.2
        self.state = CANINEState()

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

        self.timer_canine_command = self.create_timer(0.02, self.timer_callback) # 50 Hz command publishing


    def topic_callback_canine_states(self, msg):
        self.middleware_connected = True
        self.local_time = msg.local_time
        self.fsm_state = msg.fsm_state

        self.global_base_position = np.array([msg.global_base_position.x, msg.global_base_position.y, msg.global_base_position.z])
        self.global_base_velocity = np.array([msg.global_base_velocity.x, msg.global_base_velocity.y, msg.global_base_velocity.z])
        self.global_base_angular_velocity = np.array([msg.global_base_angular_velocity.x, msg.global_base_angular_velocity.y, msg.global_base_angular_velocity.z])
        self.global_base_euler_angle = np.array([msg.global_base_euler_angle.x, msg.global_base_euler_angle.y, msg.global_base_euler_angle.z])
        self.global_base_quaternion = np.array([msg.global_base_quaternion.x, msg.global_base_quaternion.y, msg.global_base_quaternion.z, msg.global_base_quaternion.w])
        
        self.body_base_velocity = np.array([msg.body_base_velocity.x, msg.body_base_velocity.y, msg.body_base_velocity.z])
        self.body_base_angular_velocity = np.array([msg.body_base_angular_velocity.x, msg.body_base_angular_velocity.y, msg.body_base_angular_velocity.z])

        # For debugging
        # self.get_logger().info(f'Local Time: {self.shm.local_time}')
        # print('Gait Table \n',self.shm.gait_table)
        # print('Global Base Position \n',self.shm.global_base_position)
        # print('Global Base Velocity \n',self.shm.global_base_velocity)
        # print('Body Base Velocity \n',self.shm.body_base_velocity)
        # print('Global Base Quaternion \n',self.shm.global_base_quaternion)


    def timer_callback(self):
        current_time = time.time()
        if current_time - self.last_cmd_time > self.command_timeout:
            print("Debug: No command received for 0.5 seconds")
            self.cmd.reference_base_velocity = [0.0,0.0]
            self.cmd.reference_base_yaw_velocity = 0.0
        msg = self.cmd
        self.publisher_canine_command.publish(msg)
        print(f'Reference Base Velocity: {msg.reference_base_velocity}')
        print(f'Reference Base Yaw Velocity: {msg.reference_base_yaw_velocity}')
        print(f'Command: {msg.command}')

class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__('keyboard_teleop')
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.running = False

        self.cmd_vel_publisher = self.create_publisher(
            Twist,
            'cmd_vel'
            ,10
        )

    def on_press(self, key):
        try:
            cmd_vel = Twist()
            print(f'Key {key.char} pressed')
            if key.char == 'w': # go forward
                cmd_vel.linear.x = 0.4
                cmd_vel.linear.y = 0.0
                cmd_vel.angular.z = 0.0
            elif key.char == 'x': # go backward
                cmd_vel.linear.x = -0.4
                cmd_vel.linear.y = 0.0
                cmd_vel.angular.z = 0.0
            elif key.char == 'a': # go left
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = 0.4
                cmd_vel.angular.z = 0.0
            elif key.char == 'd': # go right
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = -0.4
                cmd_vel.angular.z = 0.0
            elif key.char == 'q': # turn left
                cmd_vel.angular.z = 0.3
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = 0.0
            elif key.char == 'e': # turn right
                cmd_vel.angular.z = -0.3
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = 0.0
            elif key.char == 's': # stop
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = 0.0
                cmd_vel.angular.z = 0.0
            else:
                print(f'Invalid key {key.char} pressed')
                cmd_vel.linear.x = 0.0
                cmd_vel.linear.y = 0.0
                cmd_vel.angular.z = 0.0
            self.cmd_vel_publisher.publish(cmd_vel)
        except AttributeError:
            print(f'Special key {key} pressed')

    def run(self):
        self.running = True
        self.listener.start()
        self.listener.join()

    def stop(self):
        self.running = False
        self.listener.stop()
        self.listener.join()
        self.listener.close()
        self.listener = None


def main():
    rclpy.init()
    keyboard_teleop = KeyboardTeleop()
    keyboard_teleop.run()
    try:
        while keyboard_teleop.running:
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Keyboard interrupt")
    finally:
        keyboard_teleop.cmd_vel_publisher.publish(Twist()) # stop the robot
        keyboard_teleop.stop()
        rclpy.shutdown()
        print("Keyboard teleop stopped")

if __name__ == "__main__":
    main()