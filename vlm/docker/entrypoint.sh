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
bright_cyan="\[\033[1;36m\]"
bright_green="\[\033[1;32m\]"
bright_blue="\[\033[1;34m\]"

# Prompt format with git branch
PS1="🧠 VLM "
PS1+="${bright_green}\u${reset}"
PS1+=":${bright_blue}\w${reset}"
PS1+='$( __git_ps1 " ['"${bright_cyan}"'%s'"${reset}"']" )'
PS1+=" \$ "

export PS1

EOF
fi

set -e

# Trust the mounted repo path
if [ -d "/home" ]; then
    git config --global --add safe.directory /home || true
fi

echo "VLM container is ready!"

# Execute the CMD from docker-compose (vlm_server.py) or fallback to bash
exec "$@"
