# RPLidar ROS 2 Node (Jazzy)
FROM ros:jazzy-ros-base-noble

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-colcon-common-extensions \
    ros-jazzy-rmw-cyclonedds-cpp \
    python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

# Copy and build rplidar_ros
WORKDIR /root/ros2_ws/src
COPY ros2_src/rplidar_ros ./rplidar_ros

WORKDIR /root/ros2_ws
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    colcon build --packages-select rplidar_ros"

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0

WORKDIR /root/workspace
RUN git config --global --add safe.directory /root/workspace || true

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
