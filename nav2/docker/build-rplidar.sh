#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Copy rplidar_ros source for Docker build context
mkdir -p ros2_src
cp -r ../../oak-camera/docker/ros2_src/rplidar_ros ros2_src/

docker compose -f docker-compose-rplidar.yml build

# Clean up copied source
rm -rf ros2_src
