#!/usr/bin/env bash
set -euo pipefail

mkdir -p data vault inbox artifacts

APP_HOST_PORT="${APP_HOST_PORT:-48673}"

docker run --rm -p "$APP_HOST_PORT:8000" \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  -v "$PWD/vault:/app/vault" \
  -v "$PWD/inbox:/app/inbox" \
  -v "$PWD/artifacts:/app/artifacts" \
  ncp-aai
