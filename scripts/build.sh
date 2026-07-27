#!/bin/bash
set -euo pipefail
trap 'echo "ERROR: build.sh failed at line $LINENO"; exit 1' ERR

if [ $# -lt 1 ]; then
    echo "Usage: $0 [options] <texfile>"
    echo "  -i index      : specify the name of index file you want to build"
    echo "  -l lang[,...] : include only songs with given language(s)"
    echo "  -e lang[,...] : exclude songs with given language(s)"
    echo "  -o output     : output PDF filename (without extension)"
    echo "  -v            : verbose output"
    echo "  -c            : cleanup build files after build"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
indexFiles=""
includelangs=""
excludelangs=""
outputfile=""
verbose=0
cleanup=0

echo "Processing parameters..."
while [ $# -gt 1 ]; do
    case "$1" in
        -i) indexFiles="$indexFiles $2"; shift 2 ;;
        -l) includelangs="$2"; shift 2 ;;
        -e) excludelangs="$2"; shift 2 ;;
        -o) outputfile="$2"; shift 2 ;;
        -v) verbose=1; shift ;;
        -c) cleanup=1; shift ;;
        *) echo "Unknown parameter: $1"; shift ;;
    esac
done
texfile="$1"

if [ -n "$includelangs" ] && [ -n "$excludelangs" ]; then
    echo "ERROR: -l and -e cannot be used together"
    exit 1
fi

# Language filters are passed as TeX code prepended to \input of the document
pretex=""
[ -n "$includelangs" ] && pretex="\\makeatletter\\def\\ZUB@includelangs{$includelangs}\\makeatother"
[ -n "$excludelangs" ] && pretex="\\makeatletter\\def\\ZUB@excludelangs{$excludelangs}\\makeatother"

# 120 keeps each song on its own line: wide enough that TeX never splits a song
# path mid-word, narrow enough that a second song never fits beside one.
export max_print_line=120 error_line=254 half_error_line=238

# -shell-escape is needed for lyluatex to call lilypond
lualatex_cmd=(lualatex -shell-escape -interaction=nonstopmode -halt-on-error)
[ -n "$outputfile" ] && lualatex_cmd+=("--jobname=$outputfile")
if [ -n "$pretex" ]; then
    lualatex_cmd+=("${pretex}\\input{$texfile}")
else
    lualatex_cmd+=("$texfile")
fi

jobname="${outputfile:-$(basename "$texfile" .tex)}"

# $1: 1 = show lualatex output, 0 = silent (but show the log tail on failure)
run_lualatex() {
    if [ "$1" -eq 1 ]; then
        "${lualatex_cmd[@]}"
    elif ! "${lualatex_cmd[@]}" > /dev/null 2>&1; then
        echo "lualatex failed, end of $jobname.log:"
        tail -n 30 "$jobname.log"
        exit 1
    fi
}

# Warn before the long first pass; buildindex.sh re-checks and falls back.
if [ -n "$indexFiles" ] && ! locale -a 2>/dev/null | grep -Eiq '^cs_CZ(\.utf-?8)?$'; then
    echo "WARNING: no Czech locale (cs_CZ) found; song indexes will sort with the"
    echo "         system default locale. On Debian/Ubuntu: sudo locale-gen cs_CZ.UTF-8"
fi

echo "First iteration of lualatex..."
run_lualatex "$verbose"

if [ -z "$indexFiles" ]; then
    echo "No index files specified, skipping index building."
else
    for indexFile in $indexFiles; do
        echo "Building index: $indexFile..."
        if [ "$verbose" -eq 1 ]; then
            "$SCRIPT_DIR/buildindex.sh" "$indexFile"
        else
            "$SCRIPT_DIR/buildindex.sh" "$indexFile" > /dev/null 2>&1
        fi
    done

    # Intentionally quiet even with -v: its errors would just repeat the first pass
    echo "Second iteration of lualatex..."
    run_lualatex 0
fi

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
