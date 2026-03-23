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

# ONNX Runtime — CPU build at image build time.
# onnxruntime-vitisai is NOT on PyPI; it is installed at container startup
# from the AMD Ryzen AI SDK wheel in /opt/ryzenai (mounted from host).
RUN pip3 install --break-system-packages onnxruntime \
    && echo "[VLM] ONNX Runtime (CPU) installed"

WORKDIR /root/workspace

RUN git config --global --add safe.directory /root/workspace

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
