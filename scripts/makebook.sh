#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: makebook.sh failed at line $LINENO"; exit 1' ERR

if [ $# -lt 1 ]; then
    echo "Usage: $0 [options] <jobname>"
    echo "  jobname   : base name of the PDF to impose (jobname.pdf -> jobnameBook.pdf)"
    echo "  -s sheets : sheets of paper per signature, as a target (default 5)"
    echo "  -v        : verbose output"
    echo "  -c        : cleanup build files in the output directory after build"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
verbose=0
cleanup=0
target=5

while [ $# -gt 1 ]; do
    case "$1" in
        -s) target=$2; shift 2 ;;
        -v) verbose=1; shift ;;
        -c) cleanup=1; shift ;;
        *) echo "Unknown parameter: $1"; shift ;;
    esac
done
jobname=$1
src="${jobname}.pdf"

[ -f "$src" ] || { echo "ERROR: $src not found"; exit 1; }

# One sheet of paper carries four A5 pages, so the book has to end on a whole
# sheet; \padbookpages in malyzpevnik.cls is what guarantees it.
pages=$(pdfinfo "$src" 2>/dev/null | awk '/^Pages:/{print $2}')
if [ -z "$pages" ]; then
    echo "ERROR: cannot read the page count of $src (pdfinfo missing?)" >&2
    exit 1
fi
if [ "$((pages % 4))" -ne 0 ]; then
    echo "ERROR: $src has $pages pages, which is not a multiple of 4, so the last"
    echo "       sheet would be incomplete. Add \\padbookpages before \\end{document}"
    echo "       -- see docs/internals.md."
    exit 1
fi
sheets=$((pages / 4))

# An even number of signatures, as near the target thickness as it can get.
# Sheet counts then differ by at most one, which is all a hand-sewn spine wants,
# and nothing has to be padded beyond the whole sheet above.
best=0
bestcost=-1
for ((n = 2; n <= sheets; n += 2)); do
    cost=$(( sheets * 100 / n - target * 100 ))
    [ "$cost" -lt 0 ] && cost=$(( -cost ))
    if [ "$bestcost" -lt 0 ] || [ "$cost" -lt "$bestcost" ]; then
        bestcost=$cost
        best=$n
    fi
done
# The search starts at two signatures, so a book of one sheet finds none.
if [ "$sheets" -lt 2 ]; then
    best=1
elif [ "$best" -lt 2 ]; then
    best=2
fi
nsig=$best
base=$((sheets / nsig))
extra=$((sheets % nsig))

plan=""
planlist=""
for ((k = 0; k < nsig; k++)); do
    s=$base
    [ "$k" -lt "$extra" ] && s=$((s + 1))
    plan="$plan $s"
    planlist="${planlist:+$planlist, }$s"
done

echo "Imposing $pages pages ($sheets sheets) as $nsig signatures of $planlist sheets..."

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

imposed=()
first=1
k=0
for s in $plan; do
    k=$((k + 1))
    last=$((first + s * 4 - 1))
    mkdir -p "$tmp/sig$k"
    # pdfseparate/pdfunite rather than pdfjam: pdfjam re-lays the pages out on
    # its own paper, which would rescale them off A5 before pdfbook2 ever runs.
    # poppler chatters "Found recursive dicts" once per page on these files.
    pdfseparate -f "$first" -l "$last" "$src" "$tmp/sig$k/p-%04d.pdf" 2>"$tmp/poppler.err"
    pdfunite "$tmp/sig$k"/p-*.pdf "$tmp/sig$k.pdf" 2>>"$tmp/poppler.err"
    # --short-edge: uniform page orientation. --no-crop: keep the A5 margins.
    # Run inside $tmp: pdfbook2 renames a scratch file out of the working
    # directory, which fails across filesystems when $tmp is on tmpfs.
    if [ "$verbose" -eq 1 ]; then
        (cd "$tmp" && pdfbook2 --paper=a4paper --short-edge --no-crop "sig$k.pdf")
    elif ! out=$(cd "$tmp" && pdfbook2 --paper=a4paper --short-edge --no-crop "sig$k.pdf" 2>&1); then
        echo "pdfbook2 failed on signature $k:"
        echo "$out" | tail -n 30
        exit 1
    fi
    imposed+=("$tmp/sig$k-book.pdf")
    first=$((last + 1))
done

pdfunite "${imposed[@]}" "${jobname}Book.pdf" 2>>"$tmp/poppler.err"
# pdfunite writes this merge with a broken xref (trailer /Size below the /Root
# object); viewers repair it silently, a printer may not. mutool rewrites the
# file losslessly. See docs/building.md.
if command -v mutool >/dev/null; then
    mutool clean -gg "${jobname}Book.pdf" "$tmp/clean.pdf" 2>>"$tmp/poppler.err" && mv "$tmp/clean.pdf" "${jobname}Book.pdf"
else
    echo "  Note: install mupdf-tools (mutool) to repair the PDF's cross-reference table before printing."
fi
[ "$verbose" -eq 1 ] && [ -s "$tmp/poppler.err" ] && sort -u "$tmp/poppler.err"

sides=$(pdfinfo "${jobname}Book.pdf" 2>/dev/null | awk '/^Pages:/{print $2}')
echo "Finished: ${jobname}Book.pdf${sides:+ ($sheets sheets, $sides printed sides)}"
echo "  Print duplex on the short edge, then fold in runs of $planlist sheets."

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files..."
    "$SCRIPT_DIR/cleanup.sh" .
fi
