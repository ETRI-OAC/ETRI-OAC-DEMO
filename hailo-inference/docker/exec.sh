#!/bin/bash
CONTAINER_NAME="hailo-inference"
if docker ps -q -f name="$CONTAINER_NAME" -f status=running | grep -q .; then
    docker exec -it "$CONTAINER_NAME" bash
else
    cd "$(dirname "${BASH_SOURCE[0]}")"
    docker compose exec hailo-inference bash
fi
