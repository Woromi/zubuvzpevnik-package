#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: buildindex.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <jobname>"
    echo "  jobname: base name of .sxd file (e.g., 'index' for index.sxd)"
    exit 1
fi

texlua "$SCRIPT_DIR/songidx.lua" -l cs_CZ.utf8 "${1}.sxd" "${1}.sbx"
