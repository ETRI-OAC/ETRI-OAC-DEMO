import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from canine_msgs_v2.msg import CANINECommand

class RepubTwist2Canine(Node):
    def __init__(self,debug=False):
        super().__init__('repub_twist2canine')
        self.publisher_ = self.create_publisher(CANINECommand, 'canine_command', 10)
        self.subscription_ = self.create_subscription(Twist, 'cmd_vel', self.twist_callback, 10)
        self.debug = debug

    def twist_callback(self, msg):
        if self.debug:
            self.get_logger().info('Received twist: %f %f %f' % (msg.linear.x, msg.linear.y, msg.angular.z))
        cmd_msg = CANINECommand()
        cmd_msg.reference_base_velocity = [msg.linear.x, msg.linear.y]
        cmd_msg.reference_base_yaw_velocity = msg.angular.z
        self.publisher_.publish(cmd_msg)


def main(args=None):
    rclpy.init(args=args)
    node = RepubTwist2Canine(debug=True)
    try:
        print("[RepubTwist2Canine] Republishing twist to canine command")
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('[RepubTwist2Canine] Keyboard interrupt, shutting down.')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()