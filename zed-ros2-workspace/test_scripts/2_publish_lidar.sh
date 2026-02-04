source "/opt/ros/$ROS_DISTRO/install/setup.bash"
source "/opt/ros/$ROS_DISTRO/setup.bash"
source "/root/ros2_ws/install/local_setup.bash"

ros2 run rplidar_ros rplidar_node \
--ros-args \
-p serial_port:=/dev/ttyUSB1 \
-p serial_baudrate:=1000000 \
-p scan_frequency:=20.0
