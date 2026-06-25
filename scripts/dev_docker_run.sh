#!/usr/bin/env bash
set -euo pipefail

mkdir -p data vault inbox artifacts

docker run --rm -p 8000:8000 \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  -v "$PWD/vault:/app/vault" \
  -v "$PWD/inbox:/app/inbox" \
  -v "$PWD/artifacts:/app/artifacts" \
  ncp-aai
