#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: makebooklet.sh failed at line $LINENO"; exit 1' ERR

if [ $# -lt 1 ]; then
    echo "Usage: $0 [options] <jobname>"
    echo "  jobname  : base name of the PDF to reorder (jobname.pdf -> jobnameBooklet.pdf)"
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

booklet_cmd=(lualatex -interaction=nonstopmode -halt-on-error \
    "--jobname=${1}Booklet" "\\def\\pdfname{$1.pdf}\\input{$SCRIPT_DIR/makebooklet.tex}")

echo "Creating booklet..."
if [ "$verbose" -eq 1 ]; then
    "${booklet_cmd[@]}"
elif ! "${booklet_cmd[@]}" > /dev/null 2>&1; then
    echo "lualatex failed, end of ${1}Booklet.log:"
    tail -n 30 "${1}Booklet.log"
    exit 1
fi

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
