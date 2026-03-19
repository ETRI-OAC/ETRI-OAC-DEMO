#!/bin/bash
cd $(dirname $0)

echo "Building OAK-ROS2 Docker image for Ubuntu 24.04 + ROS 2 Jazzy..."

docker build -t oak_ros2_ubuntu24:latest \
  -f ./Dockerfile.ubuntu-jazzy .
