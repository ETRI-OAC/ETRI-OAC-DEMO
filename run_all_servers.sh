#!/bin/bash
# Launch all servers using tmux split panes.
# Requires: tmux (필수), terminator (선택 — 없으면 현재 터미널에서 tmux 실행)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="servers"

# --- Dependency check ---
if ! command -v tmux &>/dev/null; then
    echo "[ERROR] tmux가 설치되어 있지 않습니다."
    echo "  설치: sudo apt install tmux"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker가 설치되어 있지 않습니다."
    echo "  설치: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# --- Cleanup: kill previous session and containers ---
echo "[*] Cleaning up previous session..."
tmux kill-session -t "$SESSION" 2>/dev/null || true

for c in base-zed_ros2_env-1 hailo-inference rplidar nav2 demo-gui face-recognition base-tts-stt-1 vlm-server; do
    docker kill "$c" 2>/dev/null || true
done
sleep 1

echo "[*] Cleanup done."

# --- Launch servers in tmux panes ---
# Pane 0: Hailo inference server (must start first — oak_server & face_recognition depend on it)
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

# VLM disabled — SDK 1.7.0 genai doesn't support Krackan NPU yet
# Nav2 launched separately: ./oak-camera/run_nav2_indoor.sh or run_nav2_outdoor.sh

# Even out pane sizes
tmux select-layout -t "$SESSION" tiled

# Open in terminator if available, otherwise attach directly
if command -v terminator &>/dev/null; then
    echo "[*] Opening Terminator window with all servers..."
    terminator -e "tmux attach -t $SESSION"
else
    echo "[*] terminator not found. Attaching tmux directly."
    echo "    (설치하려면: sudo apt install terminator)"
    tmux attach -t "$SESSION"
fi
