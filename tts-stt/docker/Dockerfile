FROM dustynv/l4t-pytorch:r36.4.0
WORKDIR /root/workspace

# Set non-interactive frontend to avoid hanging
ENV DEBIAN_FRONTEND=noninteractive
# ENV TZ=Europe/Paris

RUN apt update 
RUN apt install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    build-essential \
    cmake \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory /root/workspace

# Configure pip to use PyPI as primary index
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.org/simple" >> /root/.pip/pip.conf && \
    echo "extra-index-url = https://pypi.ngc.nvidia.com" >> /root/.pip/pip.conf

# Install TTS-STT dependancies
RUN pip install --index-url https://pypi.org/simple \
    sherpa-onnx==1.12.19 \
    soundfile \
    sounddevice \
    protobuf \
    cffi \
    coloredlogs \
    humanfriendly \
    librosa \
    requests

# install flask
RUN pip install flask --index-url https://pypi.org/simple --ignore-installed

# Install Whisper
RUN pip install --index-url https://pypi.org/simple -U openai-whisper

# Install onnxruntime-gpu wheel for ARM64 (Jetson)
COPY ./onnxruntime_gpu-1.18.0-cp310-cp310-linux_aarch64.whl /tmp/
RUN pip install /tmp/onnxruntime_gpu-1.18.0-cp310-cp310-linux_aarch64.whl  --index-url https://pypi.org/simple && \
    rm /tmp/onnxruntime_gpu-1.18.0-cp310-cp310-linux_aarch64.whl

COPY entrypoint.sh /sbin/entrypoint.sh
RUN chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["bash"]