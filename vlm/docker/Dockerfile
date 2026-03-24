# Ubuntu 24.04 for VLM (Gemma-3-4b-it-mm on Ryzen AI NPU, no CUDA/GPU)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies for VLM server
RUN pip3 install --break-system-packages \
    flask \
    "numpy<2" \
    pillow \
    transformers \
    huggingface_hub \
    sentencepiece \
    protobuf

# AMD ONNX Runtime: onnxruntime_vitisai replaces generic onnxruntime.
# onnxruntime_genai_ryzenai provides CastAvx custom op required by the model.
# Do NOT install generic onnxruntime — it conflicts and breaks CastAvx registration.
COPY onnxruntime_vitisai-*.whl onnxruntime_genai_ryzenai-*.whl /root/amd_wheels/
RUN pip3 install --break-system-packages --no-deps /root/amd_wheels/onnxruntime_vitisai-*.whl \
    && pip3 install --break-system-packages --no-deps /root/amd_wheels/onnxruntime_genai_ryzenai-*.whl \
    && echo "[VLM] ONNX Runtime VitisAI + GenAI (AMD) installed"

# Download VLM model at build time (~4GB, cached in Docker layer)
ARG VLM_MODEL_ID=amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu
ARG VLM_MODEL_DIR=/root/models/Gemma-3-4b-it-mm-onnx-ryzenai-npu
RUN python3 -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='${VLM_MODEL_ID}', local_dir='${VLM_MODEL_DIR}'); \
print('[VLM] Model downloaded successfully')"

WORKDIR /root/workspace

RUN git config --global --add safe.directory /root/workspace

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
