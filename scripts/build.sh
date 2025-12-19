#!/bin/sh

if [ $# -lt 1 ]; then
    echo "Usage: $0 [options] <texfile>"
    echo "  -i index : specify the name of index file you want to build"
    echo "  -v       : verbose output"
    echo "  -c       : cleanup build files and uninstall packages after build"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
indexFiles=""
verbose=0
cleanup=0

echo "Processing parameters..."
while [ $# -gt 1 ]; do
    case "$1" in
        -i) indexFiles="$indexFiles $2"; shift 2 ;;
        -v) verbose=1; shift ;;
        -c) cleanup=1; shift ;;
        *) echo "Unknown parameter: $1"; shift ;;
    esac
done

echo "Installing necessary packages..."
"$SCRIPT_DIR/install.sh"

# -shell-escape is needed for lyluatex to call external programs
echo "First iteration of lualatex..."
if [ "$verbose" -eq 1 ]; then
    lualatex -shell-escape "$1"
else
    lualatex -shell-escape "$1" > /dev/null 2>&1
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
    lualatex -shell-escape "$1" > /dev/null 2>&1
fi

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files, uninstalling packages..."
    "$SCRIPT_DIR/cleanup.sh"
fi
