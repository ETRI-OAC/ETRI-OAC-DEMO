#!/bin/bash
# Register faces from database/ directory inside the face-recognition container.
# Automatically starts/stops hailo_inference_server for face detection.
#
# Usage: ./register_face.sh [--directory ./database/] [--name "홍길동" --image photo.jpg]
# Default (no args): --directory ./database/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="face-recognition"
HAILO_CONTAINER="hailo-inference"
ARGS="${@:---directory ./database/}"

cd "$DOCKER_DIR"

# Start face-recognition container
docker compose -f docker-compose-face.yaml up -d 2>/dev/null || true

# Check if hailo_inference_server is already running
HAILO_ALREADY_RUNNING=false
if docker exec $HAILO_CONTAINER bash -c "pgrep -f hailo_inference_server" &>/dev/null; then
    HAILO_ALREADY_RUNNING=true
    echo "[*] Hailo inference server already running."
else
    # Start hailo container and server in background
    echo "[*] Starting Hailo inference server..."
    docker compose -f docker-compose.yml up -d 2>/dev/null || true
    docker exec -d $HAILO_CONTAINER bash -c "cd /root/workspace/hailo-inference && python3 hailo_inference_server.py --port 8003"
    echo "[*] Waiting for Hailo server to be ready..."
    for i in $(seq 1 30); do
        if docker exec $CONTAINER_NAME bash -c "python3 -c \"import socket; s=socket.socket(); s.settimeout(1); s.connect(('localhost',8003)); s.close()\"" &>/dev/null; then
            echo "[*] Hailo server ready."
            break
        fi
        sleep 1
    done
fi

echo "[*] Registering faces ($ARGS)..."
docker exec -it $CONTAINER_NAME bash -c "cd /root/workspace/hailo-inference && python3 register_face.py --use-hailo-server $ARGS"

# Stop hailo server if we started it
if [ "$HAILO_ALREADY_RUNNING" = false ]; then
    echo "[*] Stopping Hailo inference server..."
    docker exec $HAILO_CONTAINER bash -c "pkill -f hailo_inference_server" 2>/dev/null || true
fi
