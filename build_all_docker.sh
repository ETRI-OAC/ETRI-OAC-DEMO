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

# 2. Hailo Inference + Face Recognition
build "Hailo Inference" "hailo-inference/docker"

# 3. Nav2 + RPLidar
build "Nav2" "nav2/docker"

# 4. Demo GUI (PyQt5 + ROS 2 + CANINE middleware)
build "Demo GUI" "demo-gui/docker"

# 5. TTS-STT
build "TTS-STT" "tts-stt/docker"

# 6. VLM (disabled — SDK 1.7.0 genai does not support Krackan NPU)
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
