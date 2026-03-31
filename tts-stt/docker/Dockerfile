# Ubuntu 24.04 for TTS/STT services (CPU only, no CUDA/GPU)
FROM ubuntu:24.04
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

# Configure pip
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.org/simple" >> /root/.pip/pip.conf

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

# Install Whisper backends
RUN pip install --break-system-packages -U openai-whisper  # fallback
RUN pip install --break-system-packages faster-whisper      # default (CPU-optimized)

# Sounddevice
RUN add-apt-repository universe && apt update && apt install libportaudio2 libasound2-dev -y

# Pin NumPy <2 for pickle compatibility with hailo-inference container
RUN pip install --break-system-packages "numpy<2"

# Install onnxruntime (CPU only)
RUN pip install --break-system-packages onnxruntime

# Hailo-10 HailoRT (optional — auto-detected: uses device[1] if 2+ Hailo present)
RUN --mount=type=bind,source=.,target=/ctx \
    if ls /ctx/hailort*.deb 1>/dev/null 2>&1; then \
        cp /ctx/hailort*.deb /tmp/ && \
        dpkg -i /tmp/hailort*.deb || apt-get install -f -y && \
        pip install --break-system-packages hailort && \
        rm -f /tmp/hailort*.deb && \
        echo "[HAILO] HailoRT installed (STT uses device[1] if 2+ Hailo)"; \
    else \
        echo "[HAILO] No hailort .deb found, STT CPU-only"; \
    fi

COPY entrypoint.sh /sbin/entrypoint.sh
RUN chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["bash"]
