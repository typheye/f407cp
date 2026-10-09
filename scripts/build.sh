#!/usr/bin/env bash
# Freeze JAPKit with PyInstaller.
#
# Usage: scripts/build.sh [--install]
#   --install  also copy the built binary into $CONDA_PREFIX/bin
set -euo pipefail

INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --install|-Install) INSTALL=1 ;;
    *) echo "[ERROR] Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BUILD_ROOT="$PROJECT_ROOT/build"
DIST_ROOT="$PROJECT_ROOT/dist"
SOURCE_ROOT="$PROJECT_ROOT/src"
SPEC="$SOURCE_ROOT/japkit/japkit.spec"

# Re-enter inside the conda environment if we are not already there.
if [ "${CONDA_DEFAULT_ENV:-}" != "janpnp" ]; then
  command -v conda >/dev/null 2>&1 || {
    echo "[ERROR] Conda not found. Run scripts/setup-conda.sh first." >&2; exit 1; }
  echo "[INFO] Re-running inside the 'janpnp' conda environment..."
  args=(--no-capture-output -n janpnp bash "$0")
  [ "$INSTALL" -eq 1 ] && args+=(--install)
  exec conda run "${args[@]}"
fi

python -c "import PyInstaller, PyQt5, pyqtgraph, numpy, cv2" >/dev/null 2>&1 || {
  echo "[ERROR] Missing build dependency. Run scripts/setup-conda.sh first." >&2; exit 1; }

rm -rf "$BUILD_ROOT" "$DIST_ROOT"
mkdir -p "$DIST_ROOT"

# PyInstaller freezes <name> as a bare executable file.
echo "[INFO] python -m PyInstaller --noconfirm --clean --distpath $DIST_ROOT $SPEC"
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST_ROOT" \
  --workpath "$BUILD_ROOT/pyinstaller/japkit" \
  "$SPEC"

EXPECTED="$DIST_ROOT/JAPKit"
if [ ! -f "$EXPECTED" ]; then
  echo "[ERROR] Expected output was not generated: $EXPECTED" >&2
  exit 1
fi
echo "[OK] JAPKit built successfully: $(( $(stat -c %s "$EXPECTED") / 1024 )) KB"

if [ "$INSTALL" -eq 1 ]; then
  [ -n "${CONDA_PREFIX:-}" ] || {
    echo "[ERROR] No active Conda environment. Activate 'janpnp' before using --install." >&2
    exit 1; }
  mkdir -p "$CONDA_PREFIX/bin"
  cp "$EXPECTED" "$CONDA_PREFIX/bin/"
  echo "[OK] Installed JAPKit to $CONDA_PREFIX/bin"
fi

echo ""
echo "Build complete:"
echo "  dist/JAPKit"
