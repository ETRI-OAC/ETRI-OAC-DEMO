#!/bin/bash
# Run CANINE middleware inside the demo-gui container.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../demo-gui/docker"
CONTAINER_NAME="demo-gui"
COMMAND="source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash && cd /root/workspace/demo-gui && ./1_middleware.sh"

cd "$DOCKER_DIR"

if [ -z "$DISPLAY" ]; then export DISPLAY=":0"; fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

echo "[*] Starting demo-gui container..."
docker compose up -d --force-recreate --remove-orphans

echo "[*] Running canine_middleware in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
