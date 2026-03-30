#!/bin/bash
# Run stt_server.py inside the tts-stt container (Whisper STT, port 8001).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="base-tts-stt-1"
DOCKER_COMPOSE_FILE="docker-compose.yml"
COMMAND="cd /root/workspace/tts-stt && python3 stt_server.py --backend auto"

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

echo "[*] Running stt_server.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"

# Optional: revoke xhost when script exits
xhost -si:localuser:root 2>/dev/null || true
