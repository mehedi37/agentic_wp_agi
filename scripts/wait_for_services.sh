#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for backend health endpoint..."
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/api/health > /dev/null; then
    echo "Backend is healthy."
    exit 0
  fi
  sleep 2
done

echo "Backend did not become healthy in time." >&2
exit 1
