#!/bin/bash
# Launch all servers using tmux split panes.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="servers"

if ! command -v tmux &>/dev/null; then
    echo "[ERROR] tmux가 설치되어 있지 않습니다: sudo apt install tmux"
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
echo "[*] Cleaning up previous session and containers..."
tmux kill-session -t "$SESSION" 2>/dev/null || true
for c in base-zed_ros2_env-1 hailo-inference rplidar nav2 demo-gui face-recognition base-tts-stt-1 vlm-server oak-camera; do
    docker rm -f "$c" 2>/dev/null || true
done
echo "[*] Cleanup done."

# Pane 0: Hailo inference server (먼저 시작 — OAK/얼굴인식이 의존)
tmux new-session -d -s "$SESSION" -n "all" "cd '$REPO_ROOT' && ./run_hailo_server.sh; exec bash"
sleep 3

# Pane 1: STT
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_stt_server.sh; exec bash"
# Pane 2: TTS
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_tts_server.sh; exec bash"
# Pane 3: Face Recognition
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./hailo-inference/run_face_recognition_server.sh; exec bash"
# Pane 4: CANINE Middleware
tmux split-window -v -t "$SESSION.0" "cd '$REPO_ROOT' && ./oak-camera/run_middleware.sh; exec bash"
# Pane 5: RPLidar
tmux split-window -v -t "$SESSION.4" "cd '$REPO_ROOT' && ./oak-camera/run_lidar.sh; exec bash"
# Pane 6: Pan-Tilt
tmux split-window -v -t "$SESSION.5" "cd '$REPO_ROOT' && ./oak-camera/run_pantilt.sh; exec bash"
# Pane 7: OAK-D Camera + Pose
tmux split-window -v -t "$SESSION.6" "cd '$REPO_ROOT' && ./oak-camera/run_oak_server.sh; exec bash"

# VLM 비활성 — Ryzen AI SDK 1.7.0이 Krackan NPU 미지원
# Nav2는 별도 실행: ./oak-camera/run_nav2_indoor.sh 또는 run_nav2_outdoor.sh

tmux select-layout -t "$SESSION" tiled

echo "[*] Opening Terminator window with all servers..."
terminator -e "tmux attach -t $SESSION"
