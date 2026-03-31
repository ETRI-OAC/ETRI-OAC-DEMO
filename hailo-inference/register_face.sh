#!/bin/bash
# Register faces from database/ directory inside the face-recognition container.
# Uses CPU-only mode (InsightFace SCRFD) — no Hailo server needed.
#
# Usage: ./register_face.sh [--directory ./database/] [--name "홍길동" --image photo.jpg]
# Default (no args): --directory ./database/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
CONTAINER_NAME="face-recognition"
ARGS="${@:---directory ./database/}"

cd "$DOCKER_DIR"

# Start container if not running
docker compose -f docker-compose-face.yaml up -d 2>/dev/null || true

echo "[*] Registering faces in container ($ARGS)..."
docker exec -it $CONTAINER_NAME bash -c "cd /root/workspace/hailo-inference && python3 register_face.py --no-hailo $ARGS"
