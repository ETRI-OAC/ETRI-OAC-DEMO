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
PS1="🐳 Face Recognition "
PS1+="${bright_green}\u${reset}"                   # user
PS1+=":${bright_blue}\w${reset}"                   # path
PS1+='$( __git_ps1 " ['"${bright_cyan}"'%s'"${reset}"']" )'  # branch
PS1+=" \$ "

export PS1

EOF
fi

set -e

# Trust the mounted repo path to avoid Git "dubious ownership" error
if [ -d "/home" ]; then
    git config --global --add safe.directory /home || true
fi

# Auto-register faces from database/ if images exist and pkl is missing or outdated
DB_DIR="/root/workspace/hailo-inference/database"
DB_FILE="$DB_DIR/known_faces.pkl"
if [ -d "$DB_DIR" ]; then
    IMAGE_COUNT=$(find "$DB_DIR" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) 2>/dev/null | wc -l)
    if [ "$IMAGE_COUNT" -gt 0 ]; then
        # Re-register if pkl doesn't exist or any image is newer than pkl
        NEED_REGISTER=false
        if [ ! -f "$DB_FILE" ]; then
            NEED_REGISTER=true
        else
            NEWER=$(find "$DB_DIR" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) -newer "$DB_FILE" 2>/dev/null | head -1)
            if [ -n "$NEWER" ]; then
                NEED_REGISTER=true
            fi
        fi
        if [ "$NEED_REGISTER" = true ]; then
            echo "[ENTRYPOINT] Registering $IMAGE_COUNT face(s) from $DB_DIR..."
            cd /root/workspace/hailo-inference
            # Try Hailo first, fall back to CPU if server not available
            python3 register_face.py --use-hailo-server --directory "$DB_DIR" --database "$DB_FILE" 2>/dev/null \
                || python3 register_face.py --no-hailo --directory "$DB_DIR" --database "$DB_FILE" || true
            echo "[ENTRYPOINT] Face registration complete."
        else
            echo "[ENTRYPOINT] Face database up to date ($DB_FILE)."
        fi
    fi
fi

echo "Face Recognition container is ready!"

# Execute the command passed to the container
exec "$@"
