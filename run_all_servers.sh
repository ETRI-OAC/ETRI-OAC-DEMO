#!/bin/bash
# Launch all servers in a Terminator window with 8 split panes.
# Requires: terminator

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$REPO_ROOT/.terminator_servers.conf"

# --- Dependency check ---
if ! command -v terminator &>/dev/null; then
    echo "[ERROR] terminator가 설치되어 있지 않습니다."
    echo "  설치: sudo apt install terminator"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker가 설치되어 있지 않습니다."
    echo "  설치: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# --- Cleanup: kill and remove previous containers ---
echo "[*] Cleaning up previous containers..."
for c in base-zed_ros2_env-1 hailo-inference rplidar nav2 demo-gui face-recognition base-tts-stt-1 vlm-server oak-camera; do
    docker rm -f "$c" 2>/dev/null || true
done
echo "[*] Cleanup done."

# --- Write Terminator layout config ---
cat > "$CONFIG_FILE" << EOF
[global_config]
[keybindings]
[profiles]
  [[default]]
    scrollback_lines = 5000
[layouts]
  [[servers]]
    [[[window0]]]
      type = Window
      parent = ""
      size = 1920, 1080
    [[[h_main]]]
      type = HPaned
      parent = window0
      ratio = 0.5
      order = 0
    [[[v_left]]]
      type = VPaned
      parent = h_main
      ratio = 0.5
      order = 0
    [[[v_right]]]
      type = VPaned
      parent = h_main
      ratio = 0.5
      order = 1
    [[[v_left_top]]]
      type = VPaned
      parent = v_left
      ratio = 0.5
      order = 0
    [[[v_left_bot]]]
      type = VPaned
      parent = v_left
      ratio = 0.5
      order = 1
    [[[v_right_top]]]
      type = VPaned
      parent = v_right
      ratio = 0.5
      order = 0
    [[[v_right_bot]]]
      type = VPaned
      parent = v_right
      ratio = 0.5
      order = 1
    [[[term_hailo]]]
      type = Terminal
      parent = v_left_top
      order = 0
      command = bash -c 'cd $REPO_ROOT && ./run_hailo_server.sh; exec bash'
      title = Hailo Inference
    [[[term_stt]]]
      type = Terminal
      parent = v_left_top
      order = 1
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./tts-stt/run_stt_server.sh; exec bash'
      title = STT
    [[[term_tts]]]
      type = Terminal
      parent = v_left_bot
      order = 0
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./tts-stt/run_tts_server.sh; exec bash'
      title = TTS
    [[[term_face]]]
      type = Terminal
      parent = v_left_bot
      order = 1
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./hailo-inference/run_face_recognition_server.sh; exec bash'
      title = Face Recognition
    [[[term_middleware]]]
      type = Terminal
      parent = v_right_top
      order = 0
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./oak-camera/run_middleware.sh; exec bash'
      title = CANINE Middleware
    [[[term_lidar]]]
      type = Terminal
      parent = v_right_top
      order = 1
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./oak-camera/run_lidar.sh; exec bash'
      title = RPLidar
    [[[term_pantilt]]]
      type = Terminal
      parent = v_right_bot
      order = 0
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./oak-camera/run_pantilt.sh; exec bash'
      title = Pan-Tilt
    [[[term_oak]]]
      type = Terminal
      parent = v_right_bot
      order = 1
      command = bash -c 'sleep 4 && cd $REPO_ROOT && ./oak-camera/run_oak_server.sh; exec bash'
      title = OAK Camera
[plugins]
EOF

echo "[*] Opening Terminator with all servers..."
terminator --config "$CONFIG_FILE" --layout servers
