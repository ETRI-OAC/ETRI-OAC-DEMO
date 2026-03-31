#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

DOWNLOADS=~/Downloads
DEB=hailort_5.2.0_amd64.deb
WHL=hailort-5.2.0-cp312-cp312-linux_x86_64.whl

for f in "$DEB" "$WHL"; do
    if [ ! -f "$f" ] && [ -f "$DOWNLOADS/$f" ]; then
        echo "[build] Copying $f from ~/Downloads"
        cp "$DOWNLOADS/$f" .
    fi
done

docker compose build
