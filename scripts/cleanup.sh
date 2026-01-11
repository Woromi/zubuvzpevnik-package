#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: cleanup.sh failed at line $LINENO"; exit 1' ERR

auxFiles=$(find . | grep -Ev '.git/' | grep -E '\.aux$|\.log$|\.out$|\.toc$|\.idx$|\.ilg$|\.ind$|\.sxc$|\.sxd$|\.fls$|\.fdb_latexmk$|\.aut$')
for file in $auxFiles; do
    rm -rf "$file"
done
