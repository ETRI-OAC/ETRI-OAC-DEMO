#!/bin/bash
# Run RPLidar ROS 2 node inside the RPLidar container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../nav2/docker"
CONTAINER_NAME="rplidar"
COMMAND="source /opt/ros/jazzy/setup.bash && ros2 run rplidar_ros rplidar_node \
  --ros-args \
  -p serial_port:=/dev/ttyUSB1 \
  -p serial_baudrate:=1000000 \
  -p scan_frequency:=20.0"

cd "$DOCKER_DIR"

# Start the container only if it is not already running
echo "[*] Starting $CONTAINER_NAME container..."
docker compose -f docker-compose-rplidar.yml up -d || true
echo "[*] Running rplidar_node in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
