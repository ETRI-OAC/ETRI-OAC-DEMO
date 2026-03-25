#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Copy canine_msgs_v2 for ROS 2 message build
mkdir -p ros2_src
cp -r ../../oak-camera/docker/ros2_src/canine_msgs_v2 ros2_src/

docker compose build

# Clean up
rm -rf ros2_src
