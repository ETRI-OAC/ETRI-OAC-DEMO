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

# 1. Hailo Inference (no dependencies, fastest)
build "Hailo Inference" "hailo-inference/docker"

# 2. OAK-ROS2 (camera + demo scripts)
build "OAK-ROS2" "oak-camera/docker"

# 3. RPLidar (needs rplidar_ros source from oak-camera)
build "RPLidar" "nav2/docker" # RPLidar merged into Nav2

# 4. Nav2 (standalone ROS 2 + Nav2)
build "Nav2" "nav2/docker"

# 5. Demo GUI (PyQt5 + ROS 2 client)
build "Demo GUI" "demo-gui/docker"

# 6. Face Recognition
build "Face Recognition" "hailo-inference/docker" # Face merged into Hailo

# 7. TTS-STT
build "TTS-STT" "tts-stt/docker"

# 8. VLM (disabled but buildable; downloads ~4GB model)
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
