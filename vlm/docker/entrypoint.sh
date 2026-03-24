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

# AMD Ryzen AI NPU runtime setup.
# The Dockerfile already installs onnxruntime_vitisai + onnxruntime_genai_ryzenai.
# Here we install ONLY the runtime dependencies (voe, vitis_aie_essentials, etc.)
# that VitisAI EP needs to initialize. We skip onnxruntime_vitisai itself to avoid
# overwriting the ORT shared libs and breaking CastAvx op registration.
WHEEL_DIR="/opt/ryzenai/wheels"
if python3 -c "from onnxruntime import get_available_providers; assert 'VitisAIExecutionProvider' in get_available_providers()" 2>/dev/null; then
    echo "[VLM] VitisAI EP already available — NPU enabled"
elif [ -d "$WHEEL_DIR" ]; then
    echo "[VLM] Installing NPU runtime deps from $WHEEL_DIR (skipping onnxruntime*)..."
    for PKG in \
        "voe-*.whl" \
        "vitis_aie_essentials-*.whl" \
        "device_essentials_strx-*.whl" \
        "ryzenai_dynamic_dispatch-*.whl"
    do
        WHL=$(ls "$WHEEL_DIR"/$PKG 2>/dev/null | head -1)
        if [ -n "$WHL" ]; then
            echo "[VLM]   Installing $(basename $WHL) ..."
            pip3 install --break-system-packages --quiet --no-deps "$WHL" \
                || echo "[VLM]   WARNING: failed to install $(basename $WHL)"
        fi
    done
    if python3 -c "from onnxruntime import get_available_providers; assert 'VitisAIExecutionProvider' in get_available_providers()" 2>/dev/null; then
        echo "[VLM] VitisAI EP activated — NPU enabled"
    else
        echo "[VLM] VitisAI EP still not available — CPU only (CastAvx may work anyway)"
    fi
else
    echo "[VLM] $WHEEL_DIR not found — CPU only"
fi

# Verify genai import
if python3 -c "import onnxruntime_genai" 2>/dev/null; then
    echo "[VLM] onnxruntime-genai-ryzenai OK"
else
    echo "[VLM] WARNING: onnxruntime-genai import failed"
fi

# Patch genai_config.json: replace "RyzenAI" provider with correct one.
# The AMD model ships with provider_options: [{"RyzenAI":{}}] but this
# provider doesn't exist as a loadable .so. With VitisAI EP → use VitisAI.
# Without VitisAI EP → remove provider_options entirely for CPU fallback.
VITISAI_AVAILABLE=false
python3 -c "from onnxruntime import get_available_providers; assert 'VitisAIExecutionProvider' in get_available_providers()" 2>/dev/null && VITISAI_AVAILABLE=true

for cfg in /root/models/*/genai_config.json /root/workspace/vlm/models/*/genai_config.json; do
    [ -f "$cfg" ] || continue
    if grep -q '"RyzenAI"' "$cfg"; then
        if [ "$VITISAI_AVAILABLE" = true ]; then
            echo "[VLM] Patching $cfg: RyzenAI → VitisAI provider"
            python3 -c "
import json
cfg_path = '$cfg'
with open(cfg_path) as f:
    data = json.load(f)
for section in ['decoder', 'vision']:
    s = data.get('model', {}).get(section, {}).get('session_options', {})
    if 'provider_options' in s:
        s['provider_options'] = [{'VitisAIExecutionProvider': {}}]
with open(cfg_path, 'w') as f:
    json.dump(data, f, indent=4)
print(f'  Patched: {cfg_path}')
"
        else
            echo "[VLM] Patching $cfg: removing RyzenAI provider (CPU fallback)"
            python3 -c "
import json
cfg_path = '$cfg'
with open(cfg_path) as f:
    data = json.load(f)
for section in ['decoder', 'vision']:
    s = data.get('model', {}).get(section, {}).get('session_options', {})
    if 'provider_options' in s:
        del s['provider_options']
    if 'hybrid_opt_token_backend' in s:
        del s['hybrid_opt_token_backend']
with open(cfg_path, 'w') as f:
    json.dump(data, f, indent=4)
print(f'  Patched: {cfg_path}')
"
        fi
    fi
done

echo "VLM container is ready!"

# Execute the CMD from docker-compose (vlm_server.py) or fallback to bash
exec "$@"
