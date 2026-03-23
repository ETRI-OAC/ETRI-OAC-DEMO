#!/bin/bash
# Run tts_server.py inside the tts-stt container (Korean TTS, port 8002).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="base-tts-stt-1"
DOCKER_COMPOSE_FILE="docker-compose.yml"
COMMAND="cd /root/workspace/tts-stt && python3 tts_server.py"

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
  docker compose -f docker-compose.yml -p $CONTAINER_NAME up -d
fi

# Run the server inside the container (foreground; Ctrl+C stops the server)
echo "[*] Running tts_server.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"

# Optional: revoke xhost when script exits
xhost -si:localuser:root 2>/dev/null || true
