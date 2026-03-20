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
    numpy \
    pillow \
    transformers \
    huggingface_hub \
    sentencepiece \
    protobuf

# ONNX Runtime — always install CPU build, then try NPU build on top
# onnxruntime-vitisai replaces onnxruntime when installed successfully.
# If it fails (SDK not available at build time), the CPU build remains.
RUN pip3 install --break-system-packages onnxruntime \
    && echo "[VLM] ONNX Runtime (CPU) installed"
RUN pip3 install --break-system-packages onnxruntime-vitisai 2>/dev/null \
    && echo "[VLM] ONNX Runtime (VitisAI/NPU) installed" \
    || echo "[VLM] onnxruntime-vitisai not available, CPU only"

WORKDIR /root/workspace

RUN git config --global --add safe.directory /root/workspace

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
