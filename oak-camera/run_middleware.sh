#!/bin/bash
# Run CANINE middleware inside the demo-gui container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../demo-gui/docker"
CONTAINER_NAME="demo-gui"
COMMAND="source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash && cd /root/workspace/demo-gui && ./1_middleware.sh"

cd "$DOCKER_DIR"

if [ -z "$DISPLAY" ]; then export DISPLAY=":0"; fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

if docker ps -q -f name=$CONTAINER_NAME -f status=running | grep -q .; then
  echo "[*] Container $CONTAINER_NAME is already running."
elif docker ps -a -q -f name=$CONTAINER_NAME | grep -q .; then
  echo "[*] Starting existing $CONTAINER_NAME container..."
  docker start $CONTAINER_NAME
else
  echo "[*] Creating and starting $CONTAINER_NAME container..."
  docker compose up -d
fi

echo "[*] Running canine_middleware in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
