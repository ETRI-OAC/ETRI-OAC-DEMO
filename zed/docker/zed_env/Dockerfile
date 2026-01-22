# ZED SDK Dockerfile
FROM stereolabs/zed:5.1-tools-devel-l4t-r36.4

# Set the working directory
WORKDIR /home

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV XDG_RUNTIME_DIR=/tmp/runtime-root

# Configure APT and update
RUN apt-get clean && apt-get update

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nano \
    git git-lfs


# Install Python packages
RUN pip3 install --upgrade pip && pip3 install opencv-python


# Prepare entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
