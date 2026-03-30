#!/bin/bash
# Run Nav2 indoor navigation (pre-built map) inside the Nav2 container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../nav2/docker"
CONTAINER_NAME="nav2"
COMMAND="source /opt/ros/jazzy/setup.bash && \
ros2 launch nav2_bringup bringup_launch.py \
  map:=/root/workspace/demo-gui/SLAM_Nav/map/map_etri.yaml \
  params_file:=/root/workspace/demo-gui/SLAM_Nav/config/nav2_params.yaml"

cd "$DOCKER_DIR"

# Optional: DISPLAY for RViz
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
echo "[*] Starting $CONTAINER_NAME container..."
docker compose -f docker-compose.yml up -d || true
echo "[*] Running Nav2 Indoor in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
