#!/bin/bash
# Stop all project containers
for c in base-zed_ros2_env-1 hailo-inference rplidar nav2 face-recognition base-tts-stt-1 vlm-server; do
    docker stop "$c" 2>/dev/null && echo "Stopped $c" || true
done
