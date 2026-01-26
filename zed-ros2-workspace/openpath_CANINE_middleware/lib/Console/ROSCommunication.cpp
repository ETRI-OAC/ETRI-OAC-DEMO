//
// Created by jh on 25. 2. 3.
//

#include "ROSCommunication.hpp"

extern pCAMEL_SHM sharedCamel;

ROSCommunication::ROSCommunication(const rclcpp::NodeOptions& opts)
    : rclcpp::Node("canine_middleware", opts)
{
    subscription_canine_command = this->create_subscription<canine_msgs_v2::msg::CANINECommand>(
        "canine_command", 10,std::bind(&ROSCommunication::topic_callback_canine_command, this, std::placeholders::_1));
    publisher_canine_states = this->create_publisher<canine_msgs_v2::msg::CANINEState>("canine_states", 10);
    publisher_canine_odom = this->create_publisher<nav_msgs::msg::Odometry>("odom", 10);
    publisher_canine_odom_tf = std::make_shared<tf2_ros::TransformBroadcaster>(this);

    // lidar_pub_ = this->create_publisher<sensor_msgs::msg::LaserScan>("/scan", 10);
    // timer_lidar_scan_ = this->create_wall_timer(std::chrono::milliseconds(50), std::bind(&ROSCommunication::publishScan, this));

    timer_canine_states = this->create_wall_timer(
        std::chrono::milliseconds(10),
        std::bind(&ROSCommunication::publishStates, this));
    timer_canine_odom = this->create_wall_timer(
        std::chrono::milliseconds(10),
        std::bind(&ROSCommunication::publishOdom, this));
    timer_canine_odom_tf = this->create_wall_timer(
        std::chrono::milliseconds(10),
        std::bind(&ROSCommunication::publishOdomTF, this));

    timer_canine_command_timeout = this->create_wall_timer(
        std::chrono::milliseconds(100),
        std::bind(&ROSCommunication::checkCommandTimeout, this));

    static_tf_broadcaster_ = std::make_shared<tf2_ros::StaticTransformBroadcaster>(this);
    publishBasetoLidarTF();
    // publishScan();

}

void ROSCommunication::publishStates()
{
    if (sharedCamel->bIsConnect)
    {
        auto msg = canine_msgs_v2::msg::CANINEState();
        package_canine_state_msg(msg);
        publisher_canine_states->publish(msg);
    }
}

void ROSCommunication::publishBasetoLidarTF()
{
    geometry_msgs::msg::TransformStamped tf;

    tf.header.stamp = this->now();
    // tf.header.stamp = rclcpp::Time(0);
    tf.header.frame_id = "base_footprint";
    tf.child_frame_id = "laser_frame";

    tf.transform.translation.x = -0.002;
    tf.transform.translation.y = 0.0;
    tf.transform.translation.z = 0.177;

    // tf.transform.rotation.w = 1.0;

    tf2::Quaternion q;
    q.setRPY(0.0, 0.0, M_PI);

    tf.transform.rotation.x = q.x();
    tf.transform.rotation.y = q.y();
    tf.transform.rotation.z = q.z();
    tf.transform.rotation.w = q.w();

    static_tf_broadcaster_->sendTransform(tf);
}

// void ROSCommunication::publishOdom()
// {
//     if (sharedCamel->bIsConnect)
//     {
//         auto msg = nav_msgs::msg::Odometry();
//         msg.header.stamp = this->now();
//         msg.header.frame_id = "odom";
//         msg.child_frame_id = "base_footprint";
//         msg.twist.twist.linear.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[0];
//         msg.twist.twist.linear.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[1];
//         msg.twist.twist.linear.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[2];
//         msg.twist.twist.angular.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[0];
//         msg.twist.twist.angular.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[1];
//         msg.twist.twist.angular.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[2];
//         msg.pose.pose.position.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[0];
//         msg.pose.pose.position.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[1];
//         msg.pose.pose.position.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[2];
//         msg.pose.pose.orientation.w = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[0];
//         msg.pose.pose.orientation.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[1];
//         msg.pose.pose.orientation.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[2];
//         msg.pose.pose.orientation.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[3];
//         std::array<double, 36> cov = {
//             0.02, 0, 0, 0, 0, 0,
//             0, 0.02, 0, 0, 0, 0,
//             0, 0, 0.02, 0, 0, 0,
//             0, 0, 0, 0.02, 0, 0,
//             0, 0, 0, 0, 0.02, 0,
//         };
//         msg.pose.covariance = cov;
//         publisher_canine_odom->publish(msg);
//     }
//     RCLCPP_INFO(this->get_logger(),
//             "basePosition = (%f, %f, %f), quat = (%f,%f,%f,%f)",
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[0],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[1],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[2],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[0],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[1],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[2],
//             sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[3]);

// }

void ROSCommunication::publishOdom()
{
    auto msg = nav_msgs::msg::Odometry();
    msg.header.stamp = this->now();
    msg.header.frame_id = "odom";
    msg.child_frame_id = "base_footprint";

    msg.twist.twist.linear.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[0];
    msg.twist.twist.linear.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[1];
    msg.twist.twist.linear.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[2];

    msg.twist.twist.angular.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[0];
    msg.twist.twist.angular.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[1];
    msg.twist.twist.angular.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[2];

    msg.pose.pose.position.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[0];
    msg.pose.pose.position.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[1];
    msg.pose.pose.position.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[2];

    tf2::Quaternion q;
    q.setRPY(
        sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[0],
        sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[1],
        sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[2]
    );
    msg.pose.pose.orientation = tf2::toMsg(q);
    publisher_canine_odom->publish(msg);
    // RCLCPP_INFO(this->get_logger(),
    //     "twist = (%f, %f, %f), rpy = (%f,%f,%f)",
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[0],
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[1],
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[2],
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[0],
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[1],
    //     sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[2]);
}

void ROSCommunication::publishOdomTF()
{
    if (sharedCamel->bIsConnect)
    {
        double roll = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[0];
        double pitch = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[1];
        double yaw = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy[2];
        double x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[0];
        double y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[1];
        double z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[2];

        geometry_msgs::msg::TransformStamped tf;
        tf.header.stamp = this->now();
        tf.header.frame_id = "odom";
        tf.child_frame_id = "base_footprint";

        tf2::Quaternion q1;
        q1.setRPY(roll, pitch, yaw);

        tf.transform.translation.x = x;
        tf.transform.translation.y = y;
        tf.transform.translation.z = z;
        tf.transform.rotation = tf2::toMsg(q1);

        publisher_canine_odom_tf->sendTransform(tf);
    }
}

void ROSCommunication::resetStates()
{
    if (sharedCamel->bIsConnect)
    {
        sharedCamel->ros2Data.isConnected = false;
        
        sharedCamel->ros2Data.baseRefVelX = 0.0;
        sharedCamel->ros2Data.baseRefVelY = 0.0;
        sharedCamel->ros2Data.baseRefAngVelZ = 0.0;
    }
}

void ROSCommunication::package_canine_state_msg(canine_msgs_v2::msg::CANINEState& msg)
{
    msg.local_time = sharedCamel->CAMEL_DATA_NEW.middlewareData.localTime;
    msg.fsm_state = sharedCamel->CAMEL_DATA_NEW.middlewareData.FSMState;

    // TODO: If jh needs odom. topic, we have to change this part
    msg.global_base_position.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition.x();
    msg.global_base_position.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition.y();
    msg.global_base_position.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition.z();
    //
    msg.global_base_velocity.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity.x();
    msg.global_base_velocity.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity.y();
    msg.global_base_velocity.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity.z();
    msg.global_base_euler_angle.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy.x();
    msg.global_base_euler_angle.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy.y();
    msg.global_base_euler_angle.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.rpy.z();
    msg.global_base_quaternion.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[1];
    msg.global_base_quaternion.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[2];
    msg.global_base_quaternion.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[3];
    msg.global_base_quaternion.w = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[0];
    msg.global_base_angular_velocity.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseAngularVelocity.x();
    msg.global_base_angular_velocity.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseAngularVelocity.y();
    msg.global_base_angular_velocity.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseAngularVelocity.z();

    msg.body_base_velocity.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseVelocity.x();
    msg.body_base_velocity.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseVelocity.y();
    msg.body_base_velocity.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseVelocity.z();
    msg.body_base_angular_velocity.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity.x();
    msg.body_base_angular_velocity.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity.y();
    msg.body_base_angular_velocity.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity.z();

    msg.odom.twist.twist.linear.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[0];
    msg.odom.twist.twist.linear.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[1];
    msg.odom.twist.twist.linear.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.baseVelocity[2];
    msg.odom.twist.twist.angular.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[0];
    msg.odom.twist.twist.angular.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[1];
    msg.odom.twist.twist.angular.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.body.baseAngularVelocity[2];
    msg.odom.pose.pose.position.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[0];
    msg.odom.pose.pose.position.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.basePosition[1];
    msg.odom.pose.pose.position.z = 0.0;
    msg.odom.pose.pose.orientation.w = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[0];
    msg.odom.pose.pose.orientation.x = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[1];
    msg.odom.pose.pose.orientation.y = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[2];
    msg.odom.pose.pose.orientation.z = sharedCamel->CAMEL_DATA_NEW.middlewareData.global.quat[3];
}


// void ROSCommunication::publishScan()
// {
//     if (sharedCamel->CAMEL_DATA_NEW.middlewareData.lidarSize <= 0)
//         return;

//     const int N = sharedCamel->CAMEL_DATA_NEW.middlewareData.lidarSize;
//     auto& lidar = sharedCamel->CAMEL_DATA_NEW.middlewareData.lidar2DPoints;

//     sensor_msgs::msg::LaserScan msg;
//     msg.header.stamp = this->now();
//     msg.header.frame_id = "laser_frame";

//     msg.angle_min = -M_PI;
//     msg.angle_max = M_PI;
//     msg.angle_increment = (msg.angle_max - msg.angle_min) / 360.0;
//     msg.range_min = 0.05;
//     msg.range_max = 15.0;

//     msg.ranges.assign(360, msg.range_max);
//     msg.intensities.assign(360, 0.0);

//     for (int i = 0; i < N; i++)
//     {
//         float x = lidar[i].x;
//         float y = lidar[i].y;

//         float distance = std::sqrt(x*x + y*y);
//         float angle    = std::atan2(y, x);

//         if (distance < msg.range_min || distance > msg.range_max)
//             continue;

//         int idx = (int)((angle - msg.angle_min) / msg.angle_increment);
//         if (idx < 0 || idx >= 360)
//             continue;

//         msg.ranges[idx] = distance;
//         msg.intensities[idx] = 1.0f - (distance / msg.range_max);
//     }

//     lidar_pub_->publish(msg);
// }

void ROSCommunication::topic_callback_canine_command(const canine_msgs_v2::msg::CANINECommand::SharedPtr msg)
{
    sharedCamel->ros2Data.isConnected = true;
    msg->reference_base_velocity.resize(2);
    double ros_ref_vel_x = msg->reference_base_velocity[0];
    double ros_ref_vel_y = msg->reference_base_velocity[1];
    double ros_ref_vel_w = msg->reference_base_yaw_velocity;

    sharedCamel->ros2Data.prevCommand = sharedCamel->ros2Data.command;
    sharedCamel->ros2Data.command = msg->command;
    sharedCamel->ros2Data.baseRefVelX = std::min(std::max(ros_ref_vel_x, -0.2), 0.5);
    sharedCamel->ros2Data.baseRefVelY = std::min(std::max(ros_ref_vel_y, -0.1), 0.1);
    sharedCamel->ros2Data.baseRefAngVelZ = std::min(std::max(ros_ref_vel_w, -0.8), 0.8);

    if (sharedCamel->ros2Data.command != sharedCamel->ros2Data.prevCommand)
    {
        sharedCamel->ros2Data.bNewCommand = true;
    }


    last_command_time_ = this->now();
    command_received_once = true;
}

void ROSCommunication::checkCommandTimeout()
{
    if (!command_received_once)
        return; // 아직 한 번도 메시지 안 왔다면 무시

    rclcpp::Time now = this->now();
    double elapsed_sec = (now - last_command_time_).seconds();

    if (elapsed_sec > 1.0)  // 1초 이상 미수신
    {
        RCLCPP_WARN(this->get_logger(),
            "No ros_command received for %.2f sec → Reset command.", elapsed_sec);

        resetStates();   // 🔥 네가 이미 구현한 함수 호출
        command_received_once = false;
    }
}