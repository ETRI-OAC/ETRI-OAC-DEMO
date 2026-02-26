# Reuse existing container so the model is only downloaded on first run
CONTAINER_NAME="vlm-server"
IMAGE="ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin"
VLLM_CMD="vllm serve cpatonn/Qwen3-VL-4B-Instruct-AWQ-4bit --gpu-memory-utilization 0.3 --max-model-len 8192"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  # Container already exists (from first run) – start it (model is already cached inside)
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container already running. Attaching..."
    docker attach "$CONTAINER_NAME"
  else
    echo "Starting existing container (model already cached)..."
    docker start -a "$CONTAINER_NAME"
  fi
else
  # First run – create named container (model will be downloaded; container is kept after exit)
  echo "First run: creating container and downloading model..."
  # docker run -it --name "$CONTAINER_NAME" --pull always --runtime=nvidia --network host \
  #   "$IMAGE" $VLLM_CMD
  # docker run -it --name "$CONTAINER_NAME" --runtime=nvidia --network host \
  #   --pull never \
  #   "$IMAGE" $VLLM_CMD
  docker run -it --name "$CONTAINER_NAME" --runtime=nvidia --network host \
  --pull never \
  "$IMAGE" $VLLM_CMD
fi
  # -e HF_HUB_OFFLINE=1 \
  # -e TRANSFORMERS_OFFLINE=1 \