# Reuse existing container so the model is only downloaded on first run
CONTAINER_NAME="vlm-server"
IMAGE="vllm/vllm-openai:latest"
VLLM_CMD="vllm serve cpatonn/Qwen3-VL-4B-Instruct-AWQ-4bit --gpu-memory-utilization 0.3 --max-model-len 8192"

# Check if the image exists locally. If not, pull it.
if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
  echo "Image $IMAGE not found locally. Pulling from registry..."
  docker pull "$IMAGE"
else
  echo "Image $IMAGE found locally."
fi

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
  docker run -it --name "$CONTAINER_NAME" --runtime=nvidia --network host \
  --gpus all \
  --pull never \
  "$IMAGE" $VLLM_CMD
fi
