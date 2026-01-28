#!/bin/bash
set -e

# Append Git prompt and PS1 config to .bashrc if not already present
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
red="\[\033[0;31m\]"
green="\[\033[0;32m\]"
yellow="\[\033[0;33m\]"
blue="\[\033[0;34m\]"
reset="\[\033[0m\]"
bright_black="\[\033[1;30m\]"
bright_red="\[\033[1;31m\]"
bright_green="\[\033[1;32m\]"
bright_yellow="\[\033[1;33m\]"
bright_blue="\[\033[1;34m\]"
bright_magenta="\[\033[1;35m\]"
bright_cyan="\[\033[1;36m\]"
bright_white="\[\033[1;37m\]"

# Prompt format with git branch
PS1="🐳 ZED-ROS2 "
PS1+="${bright_green}\u${reset}"                   # user
PS1+=":${bright_blue}\w${reset}"                   # path
PS1+='$( __git_ps1 " ['"${bright_cyan}"'%s'"${reset}"']" )'  # branch
PS1+=" \$ "

export PS1

source "/opt/ros/$ROS_DISTRO/install/setup.bash"
source "/opt/ros/$ROS_DISTRO/setup.bash"
source "/root/ros2_ws/install/local_setup.bash"

EOF
fi

# echo 'Available ZED packages:'
# ros2 pkg list | grep zed
# echo "---------------------"
# echo 'To start a ZED camera node:'
# echo '  ros2 launch zed_wrapper zed_camera.launch.py camera_model:=<zed|zedm|zed2|zed2i|zedx|zedxm|zedxonegs|zedxone4k|zedxonehdr|virtual>'
# echo "---------------------"
# exec "$@"

# setup ros2 environment
source "/opt/ros/$ROS_DISTRO/install/setup.bash"
source "/opt/ros/$ROS_DISTRO/setup.bash"
source "/root/ros2_ws/install/local_setup.bash"

export ROS_DOMAIN_ID=0

# Welcome information
echo "ZED ROS2 Docker Image"
echo "---------------------"
echo 'ROS distro: ' $ROS_DISTRO
echo 'DDS middleware: ' $RMW_IMPLEMENTATION
echo 'ROS 2 Workspaces:' $COLCON_PREFIX_PATH
echo 'ROS 2 Domain ID:' $ROS_DOMAIN_ID
echo ' * Note: Host and Docker image Domain ID must match to allow communication'
echo 'Local IPs:' $(hostname -I)
echo "---"  

set -e

# Trust the mounted repo path to avoid Git "dubious ownership" error
if [ -d "/home" ]; then
    git config --global --add safe.directory /home || true
fi

echo "ZED-ROS2 container is ready!"

# Start an interactive shell
exec bash
