#!/bin/bash
# Run CANINE middleware inside the OAK-ROS2 container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="base-zed_ros2_env-1"
DOCKER_COMPOSE_FILE="docker-compose.yaml"
COMMAND="cd /root/workspace/zed-ros2-workspace/test_scripts && ./1_middleware.sh"

# Must run compose from docker dir so volume ../../ resolves to project root
cd "$DOCKER_DIR"

# Optional: DISPLAY for GUI (e.g. cv2.imshow). Reuse host DISPLAY if set.
if [ -z "$DISPLAY" ]; then
  if [ -S "/tmp/.X11-unix/X0" ]; then
    export DISPLAY=":0"
  else
    export DISPLAY="${DISPLAY:-:0}"
  fi
fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

# Start the container only if it is not already running
if docker ps -q -f name=$CONTAINER_NAME -f status=running | grep -q .; then
  echo "[*] Container $CONTAINER_NAME is already running."
elif docker ps -a -q -f name=$CONTAINER_NAME | grep -q .; then
  echo "[*] Starting existing $CONTAINER_NAME container..."
  docker start $CONTAINER_NAME
else
  echo "[*] Creating and starting $CONTAINER_NAME container..."
  docker compose -f docker-compose.yaml -p $CONTAINER_NAME up -d
fi

# Run the server inside the container (foreground; Ctrl+C stops the server)
echo "[*] Running canine_middleware in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"