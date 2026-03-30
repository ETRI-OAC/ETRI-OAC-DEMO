#!/bin/bash
# Run Dynamixel pan-tilt ROS 2 node inside the Demo GUI container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/../demo-gui/docker"
CONTAINER_NAME="demo-gui"
COMMAND="source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash && cd /root/workspace/demo-gui/openpath_CANINE_middleware/python_scripts && python3 pantiltNode.py"

cd "$DOCKER_DIR"

# Start the container only if it is not already running
echo "[*] Starting $CONTAINER_NAME container..."
docker compose -f docker-compose.yml up -d || true
echo "[*] Running pantiltNode.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
