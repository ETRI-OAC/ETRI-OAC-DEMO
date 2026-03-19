#!/bin/bash
# Launch all servers in one Terminator window with split panes (using tmux).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="servers"

# Kill existing session so we start fresh
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create session with first server in pane 0
tmux new-session -d -s "$SESSION" -n "all" "cd '$REPO_ROOT' && ./vlm/run_vlm_server.sh; exec bash"
# tmux new-session -d -s "$SESSION" -n "all" "cd '$REPO_ROOT'; exec bash"
# Split into panes and run each server (pane 0 already has VLM)
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_stt_server.sh; exec bash"
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./tts-stt/run_tts_server.sh; exec bash"
tmux split-window -h -t "$SESSION" "cd '$REPO_ROOT' && ./face-recognition/run_face_recognition_server.sh; exec bash"
tmux split-window -v -t "$SESSION.0" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_middleware.sh; exec bash"
tmux split-window -v -t "$SESSION.4" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_lidar.sh; exec bash"
tmux split-window -v -t "$SESSION.5" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_pantilt.sh; exec bash"
tmux split-window -v -t "$SESSION.6" "cd '$REPO_ROOT' && ./zed-ros2-workspace/run_oak_server.sh; exec bash"

# Even out pane sizes
tmux select-layout -t "$SESSION" tiled

echo "[*] Opening one Terminator window with all servers in split panes..."
terminator -e "tmux attach -t $SESSION"
