# Ubuntu 24.04 for Face Recognition (CPU + optional Hailo-10, no CUDA/GPU)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    git \
    libgl1 \
    libglib2.0-0 \
    libboost-python-dev \
    libboost-dev \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Fix setuptools version for build compatibility
RUN pip3 install --break-system-packages "setuptools<70"

# ArcFace Recognition (CPU onnxruntime — no CUDA)
RUN pip3 install --break-system-packages insightface onnxruntime requests flask

# Pin NumPy version (OpenCV compatibility)
RUN pip3 install --break-system-packages "numpy<2"

# OpenCV
RUN pip3 install --break-system-packages opencv-python-headless

# Hailo-10 HailoRT (optional — shares Hailo device with OAK-ROS2 for face detection)
RUN --mount=type=bind,source=.,target=/ctx \
    if ls /ctx/hailort*.deb 1>/dev/null 2>&1; then \
        cp /ctx/hailort*.deb /tmp/ && \
        dpkg -i /tmp/hailort*.deb || apt-get install -f -y && \
        pip3 install --break-system-packages hailort && \
        rm -f /tmp/hailort*.deb && \
        echo "[HAILO] HailoRT installed (face detection acceleration)"; \
    else \
        echo "[HAILO] No hailort .deb found, face detection on CPU only"; \
    fi

# Create directories for models
RUN mkdir -p /workspace/models /workspace/database

WORKDIR /root/workspace
RUN git config --global --add safe.directory /root/workspace

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
