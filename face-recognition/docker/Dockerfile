# Ultralytics YOLO for JetPack 6 (PyTorch + CUDA already configured)
FROM ultralytics/ultralytics:latest-jetson-jetpack6

ENV DEBIAN_FRONTEND=noninteractive
ENV COLCON_WS=/root/ros2_ws
ENV ROS_DISTRO=humble

# ============================================
# ROS2 Humble Installation
# ============================================

# # Set locale
# RUN apt-get update && apt-get install -y locales && \
#     locale-gen en_US en_US.UTF-8 && \
#     update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
# ENV LANG=en_US.UTF-8

# # Add ROS2 apt repository
# RUN apt-get update && apt-get install -y software-properties-common curl gnupg lsb-release && \
#     curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc -o /tmp/ros.asc && \
#     gpg --batch --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg /tmp/ros.asc && \
#     echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" > /etc/apt/sources.list.d/ros2.list && \
#     rm /tmp/ros.asc

# # Install ROS2 Humble base
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     ros-humble-ros-base \
#     ros-humble-sensor-msgs \
#     ros-humble-std-msgs \
#     ros-humble-geometry-msgs \
#     python3-rosdep \
#     python3-colcon-common-extensions \
#     && rm -rf /var/lib/apt/lists/*

# # Initialize rosdep
# RUN rosdep init || true && rosdep update

# ============================================
# Additional Dependencies
# ============================================

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

# ============================================
# ROS2 cv_bridge build
# ============================================

# WORKDIR ${COLCON_WS}

# # Clone cv_bridge from source (to avoid OpenCV conflict)
# RUN mkdir -p ${COLCON_WS}/src && \
#     cd ${COLCON_WS}/src && \
#     git clone -b humble https://github.com/ros-perception/vision_opencv.git && \
#     git clone -b humble https://github.com/ros-perception/image_common.git

# # rosdep dependencies for cv_bridge
# RUN cd ${COLCON_WS} && \
#     rosdep install -i --from-path src --rosdistro humble -y \
#     --skip-keys="libopencv-dev cv_bridge" || true

# # Build cv_bridge
# RUN bash -c "source /opt/ros/humble/setup.bash && \
#     cd ${COLCON_WS} && \
#     colcon build --symlink-install --packages-select cv_bridge image_transport"

# ============================================
# Workspace Setup
# ============================================

# Create directories for models
RUN mkdir -p /workspace/models /workspace/database

# Setup bashrc
# RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
#     echo "source ${COLCON_WS}/install/setup.bash" >> ~/.bashrc && \
#     echo "alias cb='colcon build --symlink-install'" >> ~/.bashrc

# Entrypoint
COPY ros_entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
