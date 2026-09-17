#!/bin/bash
# Remove LaTeX build files.
#
#   cleanup.sh          the whole repository, recursively -- which also collects
#                       the strays an editor leaves next to a song it compiled
#   cleanup.sh DIR...   those directories only, and not below them: a build
#                       leaves its files flat in the directory it ran in, and
#                       that directory is not necessarily ours to recurse into
#
# Keeps .sbx, which the next first pass reads, and tmp-ly, the LilyPond cache
# (no extension of theirs is on the list below). See docs/building.md.
set -euo pipefail
trap 'echo "ERROR: cleanup.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

depth=(-maxdepth 1)
if [ $# -eq 0 ]; then
    set -- "$SCRIPT_DIR/.."
    depth=()
fi

find "$@" "${depth[@]}" -name .git -prune -o -type f \( \
    -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.toc' \
    -o -name '*.idx' -o -name '*.ilg' -o -name '*.ind' -o -name '*.sxc' \
    -o -name '*.sxd' -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.aut' \
    \) -exec rm -f {} +
