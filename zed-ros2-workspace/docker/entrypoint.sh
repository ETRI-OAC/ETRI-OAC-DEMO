#!/bin/bash
set -e

# 1. Export essential ROS 2 environment variables
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export RCUTILS_COLORIZED_OUTPUT=1 # ROS 2 로그 가독성 향상

# Append Git prompt, PS1 config, and ROS 2 sourcing to .bashrc if not already present
BASHRC="/root/.bashrc"

if ! grep -q "git-prompt.sh" "$BASHRC"; then
cat << 'EOF' >> "$BASHRC"

# Custom Git-aware prompt
if [ -f "/usr/share/git/git-prompt.sh" ]; then
    source "/usr/share/git/git-prompt.sh"
elif [ -f "/etc/bash_completion.d/git-prompt" ]; then
    source "/etc/bash_completion.d/git-prompt"
fi

# ANSI colors
green="\[\033[0;32m\]"
blue="\[\033[0;34m\]"
reset="\[\033[0m\]"
bright_green="\[\033[1;32m\]"
bright_blue="\[\033[1;34m\]"
bright_cyan="\[\033[1;36m\]"

# Prompt format with git branch
PS1="🐳 OAK-ROS2 "
PS1+="${bright_green}\u${reset}"                   # user
PS1+=":${bright_blue}\w${reset}"                   # path
PS1+='$( __git_ps1 " ['"${bright_cyan}"'%s'"${reset}"']" )'  # branch
PS1+=" \$ "

export PS1

# Source ROS 2 base and workspace (Interactive shell)
source "/opt/ros/$ROS_DISTRO/setup.bash"
if [ -f "/root/ros2_ws/install/setup.bash" ]; then
    source "/root/ros2_ws/install/setup.bash"
fi
EOF
fi

# 2. Source ROS 2 environment for the entrypoint context
source "/opt/ros/$ROS_DISTRO/setup.bash"
if [ -f "/root/ros2_ws/install/setup.bash" ]; then
    source "/root/ros2_ws/install/setup.bash"
fi

# 3. Welcome information
echo "==================================="
echo "     OAK-D ROS2 Docker Image       "
echo "==================================="
echo " * ROS distro        : $ROS_DISTRO"
echo " * DDS middleware    : $RMW_IMPLEMENTATION"
echo " * ROS 2 Workspaces  : $COLCON_PREFIX_PATH"
echo " * ROS 2 Domain ID   : $ROS_DOMAIN_ID"
echo " * Local IPs         : $(hostname -I)"
echo "-----------------------------------"  
echo " Note: Host and Docker image Domain ID must match to allow communication."

# Trust the mounted repo path to avoid Git "dubious ownership" error
if [ -d "/home" ]; then
    git config --global --add safe.directory /home || true
fi

# Dockerfile에서 설정한 workspace 경로도 추가
git config --global --add safe.directory /root/workspace || true

# Copy pre-cached Hailo HEF models to workspace (survives volume mount)
HAILO_CACHE="/root/hailo_models_cache"
HAILO_DEST="/root/workspace/hailo_models"
if [ -d "$HAILO_CACHE" ] && ls "$HAILO_CACHE"/*.hef 2>/dev/null | grep -q .; then
    mkdir -p "$HAILO_DEST"
    for hef in "$HAILO_CACHE"/*.hef; do
        fname=$(basename "$hef")
        if [ ! -f "$HAILO_DEST/$fname" ]; then
            cp "$hef" "$HAILO_DEST/"
            echo "[HAILO] Copied $fname from image cache to $HAILO_DEST"
        fi
    done
fi

exec "$@"