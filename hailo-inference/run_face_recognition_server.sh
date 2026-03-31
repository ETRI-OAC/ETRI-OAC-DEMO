#!/bin/bash
# Run face_recognition_server.py inside the face-recognition:latest container.
# Ensures the container is started, then executes the server in /root/workspace/face-recognition.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="face-recognition"
DOCKER_COMPOSE_FILE="docker-compose-face.yaml"
# When hailo_inference_server is running (recommended), use --use-hailo-server
# to share the Hailo device with oak_server and other services.
# Without it, face_recognition opens VDevice directly (may conflict with oak_server).
COMMAND="cd /root/workspace/hailo-inference && python3 face_recognition_server.py --use-hailo-server --warmup 5 --threshold 0.45"


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
docker compose -f docker-compose-face.yaml up -d || true
# Run the server inside the container (foreground; Ctrl+C stops the server)
echo "[*] Running face_recognition_server.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"

# Optional: revoke xhost when script exits
xhost -si:localuser:root 2>/dev/null || true
