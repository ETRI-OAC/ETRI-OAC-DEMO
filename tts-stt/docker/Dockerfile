# Ubuntu 24.04 for TTS/STT services (CPU + Hailo-10H GenAI Whisper)
FROM ubuntu:24.04
WORKDIR /root/workspace

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    build-essential \
    cmake \
    git \
    ffmpeg \
    software-properties-common \
    portaudio19-dev \
    libportaudio2 \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory /root/workspace

# Python dependencies
RUN pip install --break-system-packages \
    "numpy<2" \
    sherpa-onnx==1.12.19 \
    soundfile \
    sounddevice \
    protobuf \
    cffi \
    coloredlogs \
    humanfriendly \
    librosa \
    requests \
    flask \
    onnxruntime

# Whisper backends (CPU fallback)
RUN pip install --break-system-packages -U openai-whisper
RUN pip install --break-system-packages faster-whisper

# Pin NumPy <2 again (whisper may have upgraded it)
RUN pip install --break-system-packages "numpy<2"

# Hailo-10H: HailoRT system libs + Python bindings + hailo-apps GenAI
RUN --mount=type=bind,source=.,target=/ctx \
    if ls /ctx/hailort*.deb 1>/dev/null 2>&1; then \
        cp /ctx/hailort*.deb /tmp/ && \
        dpkg --unpack /tmp/hailort*.deb && ldconfig && \
        if ls /ctx/hailort*.whl 1>/dev/null 2>&1; then \
            pip install --break-system-packages /ctx/hailort*.whl; \
        fi && \
        rm -f /tmp/hailort*.deb && \
        pip install --break-system-packages "git+https://github.com/hailo-ai/hailo-apps.git#egg=hailo-apps[gen-ai]" && \
        pip install --break-system-packages "numpy<2" && \
        hailo-download-resources --group whisper_chat --arch hailo10h || true && \
        echo "[HAILO] HailoRT + hailo-apps GenAI + Whisper model installed"; \
    else \
        echo "[HAILO] No hailort .deb found, STT CPU-only"; \
    fi

COPY entrypoint.sh /sbin/entrypoint.sh
RUN chmod 755 /sbin/entrypoint.sh

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["bash"]
