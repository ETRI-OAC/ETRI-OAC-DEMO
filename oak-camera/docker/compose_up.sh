# ===== Default values =====
PROJECT_NAME="base"
DISPLAY_ID=""

# ===== Parse arguments =====
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --display)
      DISPLAY_ID=":$2"
      shift 2
      ;;
    --project)
      PROJECT_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown parameter: $1"
      exit 1
      ;;
  esac
done

# ===== Auto-detect DISPLAY =====
if [ -z "$DISPLAY_ID" ]; then
  # First, check if DISPLAY is already set in environment
  if [ -n "$DISPLAY" ]; then
    DISPLAY_ID="$DISPLAY"
    echo "[*] Using DISPLAY from environment: $DISPLAY_ID"
  else
    # Try to find available X displays
    # Check for X11 socket files
    if [ -S "/tmp/.X11-unix/X0" ]; then
      DISPLAY_ID=":0"
      echo "[*] Auto-detected DISPLAY: $DISPLAY_ID (from /tmp/.X11-unix/X0)"
    elif [ -S "/tmp/.X11-unix/X1" ]; then
      DISPLAY_ID=":1"
      echo "[*] Auto-detected DISPLAY: $DISPLAY_ID (from /tmp/.X11-unix/X1)"
    else
      # Try to get from who command or ps
      DISPLAY_FROM_WHO=$(who | grep -oP '\(:\K[0-9]+' | head -1)
      if [ -n "$DISPLAY_FROM_WHO" ]; then
        DISPLAY_ID=":$DISPLAY_FROM_WHO"
        echo "[*] Auto-detected DISPLAY: $DISPLAY_ID (from active session)"
      else
        # Fallback to :0
        DISPLAY_ID=":0"
        echo "[*] Using default DISPLAY: $DISPLAY_ID (fallback)"
      fi
    fi
  fi
else
  echo "[*] Using manually specified DISPLAY: $DISPLAY_ID"
fi

# ===== Setup env vars =====
export DISPLAY=$DISPLAY_ID
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export PROJECT_NAME=$PROJECT_NAME
  
echo "[*] Final DISPLAY=$DISPLAY"
echo "[*] XAUTHORITY=$XAUTHORITY"

# ===== Allow safe local X11 access =====
xhost +si:localuser:root

# ===== Run docker-compose =====
# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
docker compose -f "$DIR/docker-compose.yml" -p "$PROJECT_NAME" up

# ===== Cleanup =====
xhost -si:localuser:root
