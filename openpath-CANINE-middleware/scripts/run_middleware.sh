#!/bin/bash

# 현재 스크립트의 디렉토리 경로
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_SCRIPT_DIR="$(cd "${PARENT_DIR}/python_scripts/" && pwd)"
HUMBLE_SETUP="/opt/ros/humble/install/setup.bash"
SCRIPT_SETUP="${PARENT_DIR}/ros_pkg/install/setup.bash"
BUILD_DIR="$(cd "${PARENT_DIR}/build/" && pwd)"

# ROS 2 Humble 확인
if [ -f "$HUMBLE_SETUP" ]; then
    echo "ROS 2 Humble found. Sourcing $HUMBLE_SETUP"
    source "$HUMBLE_SETUP"
else
    echo "Error: Neither ROS 2 Humble nor Foxy found in /opt/ros."
    exit 1
fi

cd ${PARENT_DIR}/ros_pkg

# 현재 프로젝트가 빌드되었는지 확인
if [ -f "$SCRIPT_SETUP" ]; then
    echo "Project was built. Sourcing $SCRIPT_SETUP"
    source "$SCRIPT_SETUP"
else
    echo "Project was not built. Building project..."
    colcon build --packages-select canine_msgs_v2 sllidar_ros2
    if [ $? -ne 0 ]; then
        echo "Error: colcon build failed." >&2
        exit 1
    fi
    source "$SCRIPT_SETUP"
fi

if [ -d "${BUILD_DIR}" ]; then
    echo "CANINE middleware build folder path : $BUILD_DIR"
else
    echo "Build folder is not found."
    echo "Make build folder."
    cd ${PARENT_DIR}
    mkdir "build"
    BUILD_DIR="$(cd "${PARENT_DIR}/build/" && pwd)"
fi

cd ${BUILD_DIR}
cmake .. -DCMAKE_BUILD_TYPE=Release
make
cd "lib/Console"
./canine_middleware
