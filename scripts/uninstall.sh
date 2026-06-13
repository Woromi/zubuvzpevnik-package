#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: uninstall.sh failed at line $LINENO"; exit 1' ERR

# Remove the package installed by install.sh from ~/texmf/tex/latex.
# Safe: verify the exact path first.
PACKAGE_PATH="$HOME/texmf/tex/latex/zubuvzpevnik"
if [ -d "$PACKAGE_PATH" ]; then
    rm -r "$PACKAGE_PATH" || { echo "ERROR: Failed to remove package"; exit 1; }
    echo "Package removed: $PACKAGE_PATH"
fi
