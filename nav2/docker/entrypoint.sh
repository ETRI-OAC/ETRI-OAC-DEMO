#!/bin/bash
set -e

# Source ROS 2
source /opt/ros/jazzy/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=0

exec "$@"
