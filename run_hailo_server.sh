#!/bin/bash
# Run hailo_inference_server.py inside the Hailo Inference container.
# This server owns the Hailo device and serves inference requests to
# oak_server (pose) and face_recognition (SCRFD) via TCP port 8003.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/hailo-inference/docker"
CONTAINER_NAME="hailo-inference"

COMMAND="cd /root/workspace && python3 hailo_inference_server.py --port 8003"

# Must run compose from docker dir so volume ../../ resolves to project root
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

# Run the server inside the container (foreground; Ctrl+C stops the server)
echo "[*] Running hailo_inference_server.py in container..."
docker exec -it $CONTAINER_NAME bash -c "$COMMAND"
