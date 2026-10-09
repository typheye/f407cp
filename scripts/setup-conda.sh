#!/usr/bin/env bash
# Create/update the conda environment, then build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

command -v conda >/dev/null 2>&1 || {
  echo "[ERROR] Conda was not found. Install Miniconda/Anaconda and retry." >&2
  exit 1
}

if conda env list | awk 'NF && $1 !~ /^#/ {print $1}' | grep -qx "janpnp"; then
  conda env update -n janpnp -f "$ROOT/environment.yml" --prune
else
  conda env create -f "$ROOT/environment.yml"
fi

conda run --no-capture-output -n janpnp bash "$ROOT/scripts/build.sh"

echo ""
echo "Ready. Run:"
echo "  conda activate janpnp"
echo "  dist/JAPKit"
