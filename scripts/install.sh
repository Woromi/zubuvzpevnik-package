#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: install.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install the package
mkdir -p ~/texmf/tex/latex/zubuvzpevnik
cp -r "$SCRIPT_DIR/../zubuvzpevnik" ~/texmf/tex/latex
cp -r "$SCRIPT_DIR/../zubuvzpevnik/lilypond" "$SCRIPT_DIR/../songs"

# Czech collation is needed for correct index sorting (see buildindex.sh)
if ! locale -a 2>/dev/null | grep -Eiq '^cs_CZ(\.utf-?8)?$'; then
    echo "WARNING: no Czech locale (cs_CZ) is installed; song indexes will sort"
    echo "         with the system default locale."
    echo "         On Debian/Ubuntu: sudo locale-gen cs_CZ.UTF-8"
fi
