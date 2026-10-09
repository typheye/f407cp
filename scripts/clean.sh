#!/usr/bin/env bash
# Remove build artifacts and Python caches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

echo "[INFO] Cleaning build artifacts..."

if [ -d "$ROOT/build" ]; then
  echo "[INFO] Removing build/..."
  rm -rf "$ROOT/build"
fi
if [ -d "$ROOT/dist" ]; then
  echo "[INFO] Removing dist/..."
  rm -rf "$ROOT/dist"
fi

echo "[INFO] Removing Python cache files..."
if [ -d "$ROOT/src" ]; then
  find "$ROOT/src" -type d \
    \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \
       -o -name '*.egg-info' \) -print -exec rm -rf {} + 2>/dev/null || true
  find "$ROOT/src" -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -delete 2>/dev/null || true
fi

echo "[OK] Clean complete."
