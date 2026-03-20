#!/bin/bash
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

export PROJECT_NAME=$PROJECT_NAME

# ===== Get directory of this script =====
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# ===== Run docker-compose (with --build to pick up Dockerfile changes) =====
docker compose -f "$DIR/docker-compose.yml" -p "$PROJECT_NAME" up --build
