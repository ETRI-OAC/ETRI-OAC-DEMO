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

# Install AMD Ryzen AI NPU packages from host-mounted /opt/ryzenai/wheels/
# (not on PyPI — wheels must be placed on host at /opt/ryzenai/wheels/)
WHEEL_DIR="/opt/ryzenai/wheels"
if python3 -c "from onnxruntime import get_available_providers; assert 'VitisAIExecutionProvider' in get_available_providers()" 2>/dev/null; then
    echo "[VLM] VitisAI EP already installed — NPU enabled"
elif [ -d "$WHEEL_DIR" ] && ls "$WHEEL_DIR"/onnxruntime_vitisai*.whl 2>/dev/null | grep -q .; then
    echo "[VLM] Installing AMD Ryzen AI wheels from $WHEEL_DIR ..."
    # Install in dependency order
    for PKG in \
        "voe-*.whl" \
        "vitis_aie_essentials-*.whl" \
        "device_essentials_strx-*.whl" \
        "ryzenai_dynamic_dispatch-*.whl" \
        "onnxruntime_vitisai-*.whl"
    do
        WHL=$(ls "$WHEEL_DIR"/$PKG 2>/dev/null | head -1)
        if [ -n "$WHL" ]; then
            echo "[VLM]   Installing $(basename $WHL) ..."
            pip3 install --break-system-packages --quiet "$WHL" \
                || echo "[VLM]   WARNING: failed to install $(basename $WHL)"
        else
            echo "[VLM]   WARNING: $PKG not found in $WHEEL_DIR"
        fi
    done
    python3 -c "from onnxruntime import get_available_providers; assert 'VitisAIExecutionProvider' in get_available_providers()" 2>/dev/null \
        && echo "[VLM] VitisAI EP installed — NPU enabled" \
        || echo "[VLM] VitisAI EP not available after install — CPU only"
else
    echo "[VLM] $WHEEL_DIR not found — CPU only"
    echo "[VLM] To enable NPU: sudo mkdir -p $WHEEL_DIR && sudo cp <wheels> $WHEEL_DIR/"
fi

echo "VLM container is ready!"

# Execute the CMD from docker-compose (vlm_server.py) or fallback to bash
exec "$@"
