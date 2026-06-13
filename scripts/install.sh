#!/bin/bash
# Install the zubuvzpevnik package into your home TeX tree (~/texmf/tex/latex)
# so it can be used from any document (\usepackage{zubuvzpevnik}) outside this
# repository. Building this repo's songbooks does NOT need this: the project
# build scripts put the package on TEXINPUTS directly. Run scripts/uninstall.sh
# to remove it again.
set -euo pipefail
trap 'echo "ERROR: install.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Copies .sty/.cls/songpart and the lilypond/ includes. The package locates its
# own lilypond directory via kpse, so embedded sheet music works once installed.
mkdir -p ~/texmf/tex/latex/zubuvzpevnik
cp -r "$SCRIPT_DIR/../zubuvzpevnik" ~/texmf/tex/latex
echo "Installed zubuvzpevnik into ~/texmf/tex/latex/zubuvzpevnik"
