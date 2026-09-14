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

while [ $# -gt 1 ]; do
    case "$1" in
        -v) verbose=1; shift ;;
        -c) cleanup=1; shift ;;
        *) echo "Unknown parameter: $1"; shift ;;
    esac
done

jobname=$1

# Must be a multiple of 4 (docs/internals.md), or pdfbook2 pads at the end.
pages=$(pdfinfo "${jobname}.pdf" 2>/dev/null | awk '/^Pages:/{print $2}')
if [ -z "$pages" ]; then
    echo "WARNING: cannot read the page count of ${jobname}.pdf (pdfinfo missing?);" >&2
    echo "         skipping the multiple-of-4 check" >&2
elif [ "$((pages % 4))" -ne 0 ]; then
    echo "ERROR: ${jobname}.pdf has $pages pages, which is not a multiple of 4."
    echo "       The booklet would be imposed with the back cover on an inner"
    echo "       sheet face. Check the front matter length (a two-page index is"
    echo "       the usual cause) -- see \\padbookletpages in taborovyzpevnik.cls."
    exit 1
fi

# --short-edge: uniform page orientation. --no-crop: keep the A5 margins.
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

sides=$(pdfinfo "${jobname}Booklet.pdf" 2>/dev/null | awk '/^Pages:/{print $2}')
echo "Finished: ${jobname}Booklet.pdf${sides:+ ($((sides / 2)) sheets, $sides printed sides)}"

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
