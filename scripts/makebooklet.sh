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

jobname=$1

# Impose two A5 pages per A4 sheet. --short-edge: short-edge duplex (uniform
# orientation). --no-crop: keep the A5 margins.
booklet_cmd=(pdfbook2 --paper=a4paper --short-edge --no-crop "${jobname}.pdf")

echo "Creating booklet..."
if [ "$verbose" -eq 1 ]; then
    "${booklet_cmd[@]}"
elif ! out=$("${booklet_cmd[@]}" 2>&1); then
    echo "pdfbook2 failed:"
    echo "$out" | tail -n 30
    exit 1
fi

# pdfbook2 writes <jobname>-book.pdf; rename to the expected <jobname>Booklet.pdf
mv -f "${jobname}-book.pdf" "${jobname}Booklet.pdf"

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
