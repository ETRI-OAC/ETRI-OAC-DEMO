#!/bin/bash
# Run oak_server.py (OAK-D Pro W camera + Hailo-10 pose) inside the OAK-ROS2 container.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="base-zed_ros2_env-1"
DOCKER_COMPOSE_FILE="docker-compose.yml"
# When hailo_inference_server is running (recommended), use --use-hailo-server
# to share the Hailo device with face_recognition and other services.
# Without it, oak_server opens VDevice directly (exclusive, no sharing).
COMMAND="cd /root/workspace/oak-camera/oak_wrapper && python3 oak_server.py --debug --use-hailo-server"

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
echo "[*] Starting $CONTAINER_NAME container..."
docker compose -f docker-compose.yml up -d || true
# Run the server inside the container (foreground; Ctrl+C stops the server)
echo "[*] Running oak_server.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"