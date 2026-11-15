#!/bin/bash
# Install the package into ~/texmf for use outside a songbook checkout (a checkout puts this
# directory on TEXINPUTS instead, see docs/building.md).
set -euo pipefail
trap 'echo "ERROR: install.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET=~/texmf/tex/latex/zubuvzpevnik

# The TeX side only: the scripts, docs and git metadata stay here.
mkdir -p "$TARGET"
cp "$PACKAGE_DIR"/*.sty "$PACKAGE_DIR"/*.cls "$PACKAGE_DIR"/*.cfg "$TARGET"
cp -r "$PACKAGE_DIR"/feature "$PACKAGE_DIR"/songpart "$PACKAGE_DIR"/lilypond "$PACKAGE_DIR"/lua "$PACKAGE_DIR"/img "$TARGET"
echo "Installed zubuvzpevnik into $TARGET"
