#!/bin/bash
set -e

source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/local_setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0

exec "$@"
