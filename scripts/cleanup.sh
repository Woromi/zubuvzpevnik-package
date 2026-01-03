#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: cleanup.sh failed at line $LINENO"; exit 1' ERR

auxFiles=$(find . | grep -Ev '.git/' | grep -E '\.aux$|\.log$|\.out$|\.toc$|\.idx$|\.ilg$|\.ind$|\.sxc$|\.sbx$|\.sxd$|\.fls$|\.fdb_latexmk$|\.aut$')
for file in $auxFiles; do
    rm -rf "$file"
done

# Remove the package from ~/texmf/tex/latex (safe: verify exact path first)
PACKAGE_PATH="$HOME/texmf/tex/latex/zubuvzpevnik"
if [ -d "$PACKAGE_PATH" ]; then
    rm -r "$PACKAGE_PATH" || { echo "ERROR: Failed to remove package"; exit 1; }
    echo "Package removed: $PACKAGE_PATH"
fi
|/tmp-ly$