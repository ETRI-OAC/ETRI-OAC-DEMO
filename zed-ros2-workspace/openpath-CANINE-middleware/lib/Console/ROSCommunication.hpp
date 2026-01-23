//
// Created by jh on 25. 2. 3.
//

#ifndef ROSCOMMUNICATION_HPP
#define ROSCOMMUNICATION_HPP

#include <Eigen/Dense>
#include <chrono>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include "tf2_ros/transform_broadcaster.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include <canine_msgs_v2/msg/canine_state.hpp>
#include <canine_msgs_v2/msg/canine_command.hpp>
#include "SharedMemory.h"

#include "tf2_ros/static_transform_broadcaster.h"
#include <geometry_msgs/msg/transform_stamped.hpp>
// #include "sensor_msgs/msg/laser_scan.hpp"

class ROSCommunication : public rclcpp::Node
{
public:
  ROSCommunication(const rclcpp::NodeOptions& opts);
  void publishStates();
  void publishOdom();
  void publishOdomTF();
  void package_canine_state_msg(canine_msgs_v2::msg::CANINEState& msg);
  void topic_callback_canine_command(const canine_msgs_v2::msg::CANINECommand::SharedPtr msg);

private:
  void resetStates();
  void checkCommandTimeout();
  void publishBasetoLidarTF();
  // void publishScan();
  rclcpp::TimerBase::SharedPtr timer_canine_states;
  rclcpp::TimerBase::SharedPtr timer_canine_odom;
  rclcpp::TimerBase::SharedPtr timer_canine_odom_tf;
  rclcpp::Publisher<canine_msgs_v2::msg::CANINEState>::SharedPtr publisher_canine_states;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr publisher_canine_odom;
  std::shared_ptr<tf2_ros::TransformBroadcaster> publisher_canine_odom_tf;
  rclcpp::Subscription<canine_msgs_v2::msg::CANINECommand>::SharedPtr subscription_canine_command;

  // rclcpp::Publisher<sensor_msgs::msg::LaserScan>::SharedPtr lidar_pub_;
  // rclcpp::TimerBase::SharedPtr timer_lidar_scan_;
  std::shared_ptr<tf2_ros::StaticTransformBroadcaster> static_tf_broadcaster_;

  rclcpp::Time last_command_time_;
  bool command_received_once = false;
  rclcpp::TimerBase::SharedPtr timer_canine_command_timeout;
};



#endif //ROSCOMMUNICATION_HPP

