#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: makebooklet.sh failed at line $LINENO"; exit 1' ERR

if [ $# -lt 1 ]; then
    echo "Usage: $0 [options] <texfile>"
    echo "  -v       : verbose output"
    echo "  -c       : cleanup build files and uninstall packages after build"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
verbose=0
cleanup=0

echo "Processing parameters..."
while [ $# -gt 1 ]; do
    case "$1" in
        -v) verbose=1; shift ;;
        -c) cleanup=1; shift ;;
        *) echo "Unknown parameter: $1"; shift ;;
    esac
done

# -shell-escape is needed for lyluatex to call external programs
echo "Creating booklet..."
if [ "$verbose" -eq 1 ]; then
    lualatex -shell-escape --jobname="${1}Booklet" "\def\pdfname{$1.pdf}\input{$SCRIPT_DIR/makebooklet.tex}"
else
    lualatex -shell-escape --jobname="${1}Booklet" "\def\pdfname{$1.pdf}\input{$SCRIPT_DIR/makebooklet.tex}" > /dev/null 2>&1
fi

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
