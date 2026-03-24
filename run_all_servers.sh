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

# Kill existing session so we start fresh
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create session with first server in pane 0 — Hailo inference server must start first
# (oak_server and face_recognition connect to it as clients)
tmux new-session -d -s "$SESSION" -n "all" "cd '$REPO_ROOT' && ./run_hailo_server.sh; exec bash"
# Wait for Hailo server to initialize before starting dependent services
sleep 3
# Split into panes and run each server (pane 0 already has Hailo server)
# VLM disabled — SDK 1.7.0 genai doesn't support Krackan NPU yet
# tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./vlm/run_vlm_server.sh; exec bash"
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_stt_server.sh; exec bash"
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_tts_server.sh; exec bash"
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./face-recognition/run_face_recognition_server.sh; exec bash"
tmux split-window -v -t "$SESSION.0" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_middleware.sh; exec bash"
tmux split-window -v -t "$SESSION.5" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_lidar.sh; exec bash"
tmux split-window -v -t "$SESSION.6" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_pantilt.sh; exec bash"
tmux split-window -v -t "$SESSION.7" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_oak_server.sh; exec bash"

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
