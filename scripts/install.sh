#!/bin/sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install the package
mkdir -p ~/texmf/tex/latex/zubuvzpevnik
cp -r "$SCRIPT_DIR/../zubuvzpevnik" ~/texmf/tex/latex
