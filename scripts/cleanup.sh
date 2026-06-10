#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: cleanup.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Remove LaTeX build files (skips .git; safe with no matches or spaces in names)
find . -name .git -prune -o -type f \( \
    -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
    -o -name '*.idx' -o -name '*.ilg' -o -name '*.ind' -o -name '*.sxc' \
    -o -name '*.sxd' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.aut' \
    \) -exec rm -f {} +

# Remove the zubuvzpevnik package installed by install.sh
"$SCRIPT_DIR/uninstall.sh"
