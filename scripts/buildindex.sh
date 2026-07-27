#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: buildindex.sh failed at line $LINENO"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <jobname>"
    echo "  jobname: base name of .sxd file (e.g., 'index' for index.sxd)"
    exit 1
fi

# Czech collation sets the index order; the locale spelling varies per system.
LOC=""
for cand in cs_CZ.utf8 cs_CZ.UTF-8 cs_CZ; do
    LOC="$(locale -a 2>/dev/null | grep -Fixm1 -- "$cand" || true)"
    [ -n "$LOC" ] && break
done

if [ -n "$LOC" ]; then
    texlua "$SCRIPT_DIR/songidx.lua" -l "$LOC" "${1}.sxd" "${1}.sbx"
else
    echo "WARNING: no Czech locale found; sorting index with the system default locale" >&2
    texlua "$SCRIPT_DIR/songidx.lua" "${1}.sxd" "${1}.sbx"
fi
