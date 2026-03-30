#!/bin/bash
# Run CANINE middleware directly on the host (no Docker).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIDDLEWARE_DIR="${SCRIPT_DIR}/../demo-gui"

echo "[*] Running CANINE middleware on host..."
cd "$MIDDLEWARE_DIR"
./1_middleware.sh
