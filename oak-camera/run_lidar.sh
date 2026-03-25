#!/bin/bash
# Run RPLidar ROS 2 node inside the RPLidar container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../nav2/docker"
CONTAINER_NAME="rplidar"
COMMAND="ros2 run rplidar_ros rplidar_node \
  --ros-args \
  -p serial_port:=/dev/ttyUSB1 \
  -p serial_baudrate:=1000000 \
  -p scan_frequency:=20.0"

cd "$DOCKER_DIR"

# Start the container only if it is not already running
if docker ps -q -f name=$CONTAINER_NAME -f status=running | grep -q .; then
  echo "[*] Container $CONTAINER_NAME is already running."
elif docker ps -a -q -f name=$CONTAINER_NAME | grep -q .; then
  echo "[*] Starting existing $CONTAINER_NAME container..."
  docker start $CONTAINER_NAME
else
  echo "[*] Creating and starting $CONTAINER_NAME container..."
  docker compose -f docker-compose.yml up -d
fi

echo "[*] Running rplidar_node in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
