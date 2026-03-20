#!/bin/bash
# Run VLM server using Gemma-3-4b-it-mm on Ryzen AI NPU (no CUDA)
# Runs inside vlm-server Docker container.
# Provides an OpenAI-compatible API on port 8000.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"
MODEL_DIR="${SCRIPT_DIR}/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu"

# Check if model is downloaded (on host, before container starts)
if [ ! -d "$MODEL_DIR" ]; then
  echo "Model not found at $MODEL_DIR"
  echo "Downloading from HuggingFace..."
  python3 -m pip install --user huggingface_hub 2>/dev/null || true
  python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu',
    local_dir='${MODEL_DIR}',
)
print('Download complete.')
"
fi

# Build extra docker compose args for optional NPU mounts
EXTRA_ARGS=""
if [ -d "/opt/ryzenai" ]; then
  EXTRA_ARGS="$EXTRA_ARGS -v /opt/ryzenai:/opt/ryzenai:ro"
  EXTRA_ARGS="$EXTRA_ARGS -e XLNX_VART_FIRMWARE=/opt/ryzenai/share/phoenix/1x4.xclbin"
  echo "[VLM] Ryzen AI SDK found at /opt/ryzenai"
fi
if [ -d "/lib/firmware/amdnpu" ]; then
  EXTRA_ARGS="$EXTRA_ARGS -v /lib/firmware/amdnpu:/lib/firmware/amdnpu:ro"
  echo "[VLM] NPU firmware found at /lib/firmware/amdnpu"
fi
if [ -e "/dev/accel" ]; then
  EXTRA_ARGS="$EXTRA_ARGS --device /dev/accel:/dev/accel"
  echo "[VLM] NPU device /dev/accel detected"
else
  echo "[VLM] No NPU device found — running on CPU only"
fi

echo "Starting VLM server (Gemma-3-4b-it-mm on Ryzen AI NPU)..."
echo "  Model: /root/workspace/vlm/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu"
echo "  Port:  8000"
echo "  API:   http://localhost:8000/v1/chat/completions"

# Build image if needed, then run with optional NPU mounts
docker compose -f "$DOCKER_DIR/docker-compose.yml" -p base build vlm 2>/dev/null || true

# Stop existing container if running
docker stop vlm-server 2>/dev/null || true
docker rm vlm-server 2>/dev/null || true

# Run with conditional NPU mounts via docker run
# (docker compose doesn't support conditional volumes)
docker run --rm --name vlm-server \
  --privileged \
  --network host \
  --ipc host \
  -v "$(cd "$SCRIPT_DIR/.." && pwd):/root/workspace" \
  $EXTRA_ARGS \
  --restart unless-stopped \
  vlm-ryzenai:latest \
  python3 /root/workspace/vlm/vlm_server.py \
    --model-dir /root/workspace/vlm/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu \
    --port 8000
