# Ubuntu 24.04 + CUDA 12.6 for TTS/STT services (Desktop/x86_64, no JetPack)
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04
WORKDIR /root/workspace

# Set non-interactive frontend to avoid hanging
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    build-essential \
    cmake \
    git \
    ffmpeg \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory /root/workspace

# Configure pip to use PyPI as primary index
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.org/simple" >> /root/.pip/pip.conf && \
    echo "extra-index-url = https://pypi.ngc.nvidia.com" >> /root/.pip/pip.conf

# Install TTS-STT dependancies
RUN pip install --break-system-packages \
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
RUN pip install --break-system-packages flask --ignore-installed

# Install Whisper
RUN pip install --break-system-packages -U openai-whisper

# Sounddevice
RUN add-apt-repository universe && apt update && apt install libportaudio2 libasound2-dev -y

# Install onnxruntime-gpu (standard x86_64 wheel from PyPI)
RUN pip install --break-system-packages onnxruntime-gpu

COPY entrypoint.sh /sbin/entrypoint.sh
RUN chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["bash"]
