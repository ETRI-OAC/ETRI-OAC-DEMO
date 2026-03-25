#!/bin/bash
CONTAINER_NAME="demo-gui"
if docker ps -q -f name="$CONTAINER_NAME" -f status=running | grep -q .; then
    docker exec -it "$CONTAINER_NAME" bash -c "source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash 2>/dev/null; exec bash"
else
    cd "$(dirname "${BASH_SOURCE[0]}")"
    docker compose exec demo bash
fi
