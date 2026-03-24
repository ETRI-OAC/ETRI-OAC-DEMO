#!/bin/bash
# Run Dynamixel pan-tilt ROS 2 node inside the Demo GUI container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../demo/docker"
CONTAINER_NAME="demo-gui"
COMMAND="cd /root/workspace/openpath_CANINE_middleware/python_scripts && python3 pantiltNode.py"

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

echo "[*] Running pantiltNode.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
