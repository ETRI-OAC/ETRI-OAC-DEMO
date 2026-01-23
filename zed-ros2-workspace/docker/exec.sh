#!/bin/bash
# Simple script to exec into zed_env container with bash

# ===== Default values =====
PROJECT_NAME="base"

# ===== Parse arguments =====
while [[ "$#" -gt 0 ]]; do
  case $1 in
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

# ===== Get directory of this script =====
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# ===== Exec into container =====
docker compose -f "$DIR/docker-compose.yml" -p "$PROJECT_NAME" exec zed_ros2_env bash
