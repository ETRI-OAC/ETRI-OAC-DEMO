#!/bin/bash
# Run VLM server using Gemma-3-4b-it-mm on Ryzen AI NPU (no CUDA)
# Uses AMD's ONNX Runtime with Ryzen AI EP for NPU inference.
# Provides an OpenAI-compatible API on port 8000.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${SCRIPT_DIR}/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu"
SERVER_SCRIPT="${SCRIPT_DIR}/vlm_server.py"
PORT=8000

# Check if model is downloaded
if [ ! -d "$MODEL_DIR" ]; then
  echo "Model not found at $MODEL_DIR"
  echo "Downloading from HuggingFace..."
  pip install huggingface_hub 2>/dev/null || true
  python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu',
    local_dir='${MODEL_DIR}',
)
print('Download complete.')
"
fi

echo "Starting VLM server (Gemma-3-4b-it-mm on Ryzen AI NPU)..."
echo "  Model: $MODEL_DIR"
echo "  Port:  $PORT"
echo "  API:   http://localhost:${PORT}/v1/chat/completions"

python3 "$SERVER_SCRIPT" --model-dir "$MODEL_DIR" --port "$PORT"
