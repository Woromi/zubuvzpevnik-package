#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: cleanup.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# LaTeX build files, from the repo root. Keeps .sbx: the next first pass needs it.
find "$SCRIPT_DIR/.." -name .git -prune -o -type f \( \
    -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
    -o -name '*.idx' -o -name '*.ilg' -o -name '*.ind' -o -name '*.sxc' \
    -o -name '*.sxd' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.aut' \
    \) -exec rm -f {} +
