#!/bin/bash
# Build all Docker images in dependency order.
# Run once after initial clone or when Dockerfiles change.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=()

build() {
    local name="$1"
    local dir="$2"
    echo ""
    echo "============================================================"
    echo "  Building: $name"
    echo "  Directory: $dir"
    echo "============================================================"
    cd "$REPO_ROOT/$dir"
    if ./build.sh; then
        echo "[OK] $name"
    else
        echo "[FAIL] $name"
        FAILED+=("$name")
    fi
}

echo "============================================================"
echo "  ETRI-OAC-DEMO Docker Build (all containers)"
echo "============================================================"

# 1. OAK-Camera (camera server, base for other ROS containers)
build "OAK-Camera" "oak-camera/docker"

# 2. Hailo Inference server
build "Hailo Inference" "hailo-inference/docker"

# 3. Face Recognition (separate image from Hailo Inference)
echo ""
echo "============================================================"
echo "  Building: Face Recognition"
echo "  Directory: hailo-inference/docker"
echo "============================================================"
cd "$REPO_ROOT/hailo-inference/docker"
if docker compose -f docker-compose-face.yaml build; then
    echo "[OK] Face Recognition"
else
    echo "[FAIL] Face Recognition"
    FAILED+=("Face Recognition")
fi

# 4. Nav2
build "Nav2" "nav2/docker"

# 5. RPLidar (copies ros2_src from oak-camera before building)
echo ""
echo "============================================================"
echo "  Building: RPLidar"
echo "  Directory: nav2/docker"
echo "============================================================"
cd "$REPO_ROOT/nav2/docker"
if ./build-rplidar.sh; then
    echo "[OK] RPLidar"
else
    echo "[FAIL] RPLidar"
    FAILED+=("RPLidar")
fi

# 6. Demo GUI (PyQt5 + ROS 2 + CANINE middleware)
build "Demo GUI" "demo-gui/docker"

# 7. TTS-STT
build "TTS-STT" "tts-stt/docker"

# 8. VLM (disabled — SDK 1.7.0 genai does not support Krackan NPU)
# Uncomment to build:
# build "VLM" "vlm/docker"

echo ""
echo "============================================================"
if [ ${#FAILED[@]} -eq 0 ]; then
    echo "  All builds succeeded!"
else
    echo "  Failed: ${FAILED[*]}"
fi
echo "============================================================"
