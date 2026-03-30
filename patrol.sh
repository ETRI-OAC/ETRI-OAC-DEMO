#!/bin/bash
# Indoor patrol demo: Nav2 (map-based) + twist republisher + patrol GUI (face recognition)
# Prerequisites: run_all_servers.sh is running, robot is in Walk mode, map is built

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$REPO_ROOT/.terminator_patrol.conf"

if ! command -v terminator &>/dev/null; then
    echo "[ERROR] terminator가 설치되어 있지 않습니다: sudo apt install terminator"
    exit 1
fi

# Setup DISPLAY/xhost
if [ -z "$DISPLAY" ]; then
    export DISPLAY=":0"
fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
xhost +si:localuser:root 2>/dev/null || true

cat > "$CONFIG_FILE" << EOF
[global_config]
[keybindings]
[profiles]
  [[default]]
    scrollback_lines = 5000
[layouts]
  [[patrol]]
    [[[window0]]]
      type = Window
      parent = ""
      size = 1920, 1080
    [[[h_main]]]
      type = HPaned
      parent = window0
      ratio = 0.4
      order = 0
    [[[v_left]]]
      type = VPaned
      parent = h_main
      ratio = 0.5
      order = 0
    [[[term_nav2]]]
      type = Terminal
      parent = v_left
      order = 0
      command = bash -c 'cd $REPO_ROOT && ./oak-camera/run_nav2_indoor.sh; exec bash'
      title = Nav2 Indoor
    [[[term_repub]]]
      type = Terminal
      parent = v_left
      order = 1
      command = bash -c 'sleep 5 && cd $REPO_ROOT && ./oak-camera/run_repub.sh; exec bash'
      title = Twist Republisher
    [[[term_gui]]]
      type = Terminal
      parent = h_main
      order = 1
      command = bash -c 'sleep 3 && cd $REPO_ROOT && docker exec -it demo-gui bash -c "source /opt/ros/jazzy/setup.bash && source /root/ros2_ws/install/local_setup.bash && cd /root/workspace/demo-gui && python3 _21_patrol_gui.py"; exec bash'
      title = Patrol GUI (Face Recognition)
[plugins]
EOF

echo "[*] Starting indoor patrol demo..."
echo "    - Nav2 Indoor (지도 기반 항법)"
echo "    - Twist Republisher (cmd_vel → CANINECommand)"
echo "    - Patrol GUI (순찰 + 얼굴 인식)"
echo ""
echo "[주의] 시작 전 확인:"
echo "  1. run_all_servers.sh 실행 중"
echo "  2. 로봇 Walk 모드"
echo "  3. RViz에서 초기 위치(2D Pose Estimate) 설정 필요"
echo ""

DBUS_SESSION_BUS_ADDRESS="" terminator --config "$CONFIG_FILE" --layout patrol
