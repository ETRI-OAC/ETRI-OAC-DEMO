#!/bin/bash
# Launch all servers in gnome-terminal tabs.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v gnome-terminal &>/dev/null; then
    echo "[ERROR] gnome-terminal이 설치되어 있지 않습니다: sudo apt install gnome-terminal"
    exit 1
fi
if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker가 설치되어 있지 않습니다."
    exit 1
fi

# Setup DISPLAY/xhost
if [ -z "$DISPLAY" ]; then export DISPLAY=":0"; fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

# Cleanup
echo "[*] Cleaning up previous containers..."
for c in base-zed_ros2_env-1 hailo-inference rplidar nav2 demo-gui face-recognition base-tts-stt-1 vlm-server oak-camera; do
    docker rm -f "$c" 2>/dev/null || true
done
echo "[*] Cleanup done."

echo "[*] Starting all servers in gnome-terminal tabs..."
gnome-terminal \
  --title="Servers" \
  --tab --title="Hailo"      -e "bash -c 'cd \"$REPO_ROOT\" && ./run_hailo_server.sh; exec bash'" \
  --tab --title="STT"        -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./tts-stt/run_stt_server.sh; exec bash'" \
  --tab --title="TTS"        -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./tts-stt/run_tts_server.sh; exec bash'" \
  --tab --title="Face"       -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./hailo-inference/run_face_recognition_server.sh; exec bash'" \
  --tab --title="Middleware" -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./oak-camera/run_middleware.sh; exec bash'" \
  --tab --title="LiDAR"      -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./oak-camera/run_lidar.sh; exec bash'" \
  --tab --title="Pan-Tilt"   -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./oak-camera/run_pantilt.sh; exec bash'" \
  --tab --title="OAK Camera" -e "bash -c 'sleep 4 && cd \"$REPO_ROOT\" && ./oak-camera/run_oak_server.sh; exec bash'"
