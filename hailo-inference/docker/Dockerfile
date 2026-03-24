# Hailo-10 Inference Server (TCP :8003, shares device with all services)
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

# HailoRT 5.2.0: system libs (.deb) + Python bindings (.whl)
COPY hailort_5.2.0_amd64.deb hailort-5.2.0-cp312-cp312-linux_x86_64.whl /tmp/
RUN dpkg --unpack /tmp/hailort_5.2.0_amd64.deb && ldconfig \
    && pip3 install --break-system-packages /tmp/hailort-5.2.0-cp312-cp312-linux_x86_64.whl \
    && pip3 install --break-system-packages "numpy<2" \
    && rm -f /tmp/hailort*.deb /tmp/hailort*.whl \
    && echo "[HAILO] HailoRT 5.2.0 installed"

WORKDIR /root/workspace
RUN git config --global --add safe.directory /root/workspace || true

CMD ["sleep", "infinity"]
