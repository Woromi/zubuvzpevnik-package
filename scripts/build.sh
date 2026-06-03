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
    echo "  -c            : cleanup build files and uninstall packages after build"
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

if [ -n "$includelangs" ] && [ -n "$excludelangs" ]; then
    echo "ERROR: -l and -e cannot be used together"
    exit 1
fi

# Build pretex string
pretex=""
[ -n "$includelangs" ] && pretex="${pretex}\\def\\ZUB@includelangs{$includelangs}"
[ -n "$excludelangs" ] && pretex="${pretex}\\def\\ZUB@excludelangs{$excludelangs}"

# Build lualatex command
lualatex_cmd="lualatex -shell-escape"
[ -n "$pretex" ] && lualatex_cmd="$lualatex_cmd -usepretex='$pretex'"
[ -n "$outputfile" ] && lualatex_cmd="$lualatex_cmd -jobname='$outputfile'"
lualatex_cmd="$lualatex_cmd '$1'"

echo "Installing necessary packages..."
"$SCRIPT_DIR/install.sh"

echo "First iteration of lualatex..."
if [ "$verbose" -eq 1 ]; then
    eval "$lualatex_cmd"
else
    eval "$lualatex_cmd" > /dev/null 2>&1
fi

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

    echo "Second iteration of lualatex..."
    eval "$lualatex_cmd" > /dev/null 2>&1
fi

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
