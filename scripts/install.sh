#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: install.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install the package
mkdir -p ~/texmf/tex/latex/zubuvzpevnik
cp -r "$SCRIPT_DIR/../zubuvzpevnik" ~/texmf/tex/latex
cp "$SCRIPT_DIR/../zubuvzpevnik/zubuvzpevnik.ily" "$SCRIPT_DIR/../songs"
