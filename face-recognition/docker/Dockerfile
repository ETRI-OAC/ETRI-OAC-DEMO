# Ultralytics YOLO for JetPack 6 (PyTorch + CUDA already configured)
FROM ultralytics/ultralytics:latest-jetson-jetpack6

ENV DEBIAN_FRONTEND=noninteractive

# System dependencies + cv_bridge build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    libboost-python-dev \
    libboost-dev \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Fix setuptools version for ROS2 build compatibility
RUN pip3 install "setuptools<70"

# ArcFace Recognition
RUN pip3 install insightface onnxruntime-gpu requests flask

# Pin NumPy version (OpenCV compatibility)
RUN pip3 install "numpy<2"

# Create directories for models
RUN mkdir -p /workspace/models /workspace/database

WORKDIR /root/workspace
RUN git config --global --add safe.directory /root/workspace

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
