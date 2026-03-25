# Demo GUI Container (PyQt5, ROS 2 client, shared memory reader)
FROM ros:jazzy-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python-is-python3 \
    build-essential \
    git \
    libgl1 \
    libglib2.0-0 \
    libxcb-xinerama0 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    ffmpeg \
    libportaudio2 \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-nav2-msgs \
    ros-jazzy-tf2-ros \
    && rm -rf /var/lib/apt/lists/*

# ROS 2 custom messages (canine_msgs_v2)
WORKDIR /root/ros2_ws/src
COPY ros2_src/canine_msgs_v2 ./canine_msgs_v2
WORKDIR /root/ros2_ws
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    colcon build --packages-select canine_msgs_v2"

# Python dependencies
RUN pip3 install --break-system-packages \
    PyQt5 \
    opencv-python-headless \
    "numpy<2" \
    requests \
    sounddevice \
    pydub \
    pynput

# DynamixelSDK (for pan-tilt control from demo scripts)
WORKDIR /root/third_party
RUN git clone https://github.com/ROBOTIS-GIT/DynamixelSDK.git
WORKDIR /root/third_party/DynamixelSDK/python
RUN pip3 install --break-system-packages . --no-build-isolation

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0

WORKDIR /root/workspace
RUN git config --global --add safe.directory /root/workspace || true

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
