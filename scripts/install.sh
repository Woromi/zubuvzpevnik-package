#!/bin/bash
# Install into ~/texmf for use outside this repo (not needed to build it here).
set -euo pipefail
trap 'echo "ERROR: install.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p ~/texmf/tex/latex/zubuvzpevnik
cp -r "$SCRIPT_DIR/../zubuvzpevnik" ~/texmf/tex/latex
echo "Installed zubuvzpevnik into ~/texmf/tex/latex/zubuvzpevnik"
