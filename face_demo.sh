#!/bin/bash
# Face recognition demo: Hailo inference + face recognition server + OAK camera + GUI

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$DISPLAY" ]; then export DISPLAY=":0"; fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

echo "[*] Cleaning up previous containers..."
for c in hailo-inference face-recognition base-zed_ros2_env-1 demo-gui base-tts-stt-1; do
    docker rm -f "$c" 2>/dev/null || true
done

echo "[*] Starting face recognition demo..."

gnome-terminal \
  --title="Face Demo" \
  --tab --title="Hailo Server"          -e "bash -c 'cd \"$REPO_ROOT\" && ./run_hailo_server.sh; exec bash'" \
  --tab --title="Face Server"           -e "bash -c 'sleep 5 && cd \"$REPO_ROOT\" && ./hailo-inference/run_face_recognition_server.sh; exec bash'" \
  --tab --title="TTS"                    -e "bash -c 'sleep 5 && cd \"$REPO_ROOT\" && ./tts-stt/run_tts_server.sh; exec bash'" \
  --tab --title="OAK Camera"            -e "bash -c 'sleep 5 && cd \"$REPO_ROOT\" && ./oak-camera/run_oak_server.sh; exec bash'" \
  --tab --title="Face Recognition GUI"  -e "bash -c 'sleep 5 && cd \"$REPO_ROOT/demo-gui/docker\" && docker compose up -d --no-recreate 2>/dev/null || true && sleep 5 && docker exec -it demo-gui bash -c \"source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash && cd /root/workspace/demo-gui && python3 face_recognition_demo.py\"; exec bash'"
