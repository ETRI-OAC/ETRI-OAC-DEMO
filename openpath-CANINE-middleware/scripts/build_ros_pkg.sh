#!/bin/bash

# 현재 스크립트의 디렉토리 경로
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HUMBLE_SETUP="/opt/ros/humble/install/setup.bash"
SCRIPT_SETUP="${PARENT_DIR}/ros_pkg/install/setup.bash"

# ROS 2 Humble 확인
if [ -f "$HUMBLE_SETUP" ]; then
    echo "ROS 2 Humble found. Sourcing $HUMBLE_SETUP"
    source "$HUMBLE_SETUP"
else
    echo "Error: ROS 2 Humble is not found in /opt/ros."
    exit 1
fi

cd "${PARENT_DIR}/ros_pkg"

colcon build --packages-select canine_msgs_v2 rplidar_ros --symlink-install

echo "Build Finish"