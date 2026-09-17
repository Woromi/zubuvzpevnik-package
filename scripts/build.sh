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
    echo "  -c            : cleanup build files in the output directory after build"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
indexFiles=""
includelangs=""
excludelangs=""
outputfile=""
verbose=0
cleanup=0

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

# A LuaLaTeX log is ~2000 lines of which a handful are worth reading. Blocks
# that open with one of these and run to the next blank line are surfaced; the
# log hard-wraps them mid-word at max_print_line, so they are glued back
# together. Font shape substitutions are on every build for a reason the repo
# already knows about, so they are counted, not printed. -v prints the whole log
# instead. See docs/building.md.
report_log() {
    [ -f "$1" ] || return 0
    awk '
        function flush(   i, out) {
            if (nblk) {
                if (quiet) hidden++
                # An error block is message plus TeX context lines, which are
                # separate lines rather than one wrapped sentence.
                else if (iserr) { for (i = 1; i <= nblk; i++) print "  " blk[i] }
                else {
                    out = ""
                    for (i = 1; i <= nblk; i++) out = out blk[i]
                    print "  " out
                }
            }
            nblk = 0; inblk = 0; quiet = 0; iserr = 0
        }
        /^[[:space:]]*$/ { flush(); next }
        /^Missing character:/ { flush(); miss[$0]++; next }
        /^(! |LaTeX Warning|LaTeX Font Warning|(Package|Class|Module) [A-Za-z@]+ (Warning|Error|warning))/ {
            flush()
            inblk = 1
            iserr = /^! /
            quiet = /^LaTeX Font Warning/
        }
        inblk {
            line = $0
            if (!iserr) sub(/^\([A-Za-z@]+\)[ ]*/, " ", line)
            blk[++nblk] = line
        }
        END {
            flush()
            for (m in miss) print "  " m " [" miss[m] "x]"
            if (hidden) printf "  (%d routine font notice(s) hidden; -v shows the whole log)\n", hidden
        }
    ' "$1"
}

# $1: 1 = show lualatex output, 0 = silent (but show the log tail on failure)
run_lualatex() {
    if [ "$1" -eq 1 ]; then
        "${lualatex_cmd[@]}"
    elif ! "${lualatex_cmd[@]}" > /dev/null 2>&1; then
        echo "lualatex failed:"
        # The error is usually far above the tail, which is a geometry dump.
        found=$(report_log "$jobname.log")
        if [ -n "$found" ]; then
            printf '%s\n' "$found"
        else
            echo "  nothing matched; end of $jobname.log:"
            tail -n 30 "$jobname.log"
        fi
        exit 1
    fi
}

# Warn before the long first pass; buildindex.sh re-checks and falls back.
if [ -n "$indexFiles" ] && ! locale -a 2>/dev/null | grep -Eiq '^cs_CZ(\.utf-?8)?$'; then
    echo "WARNING: no Czech locale (cs_CZ) found; song indexes will sort with the"
    echo "         system default locale. On Debian/Ubuntu: sudo locale-gen cs_CZ.UTF-8"
fi

echo "Building songbook: $jobname..."
run_lualatex "$verbose"

if [ -z "$indexFiles" ]; then
    [ "$verbose" -eq 1 ] && echo "No index files specified, skipping index building."
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
    echo "Rebuilding songbook with the indexes..."
    run_lualatex 0
fi

# -v already showed everything; otherwise this is the only sight of a warning.
[ "$verbose" -eq 1 ] || report_log "$jobname.log"
pages=$(pdfinfo "$jobname.pdf" 2>/dev/null | awk '/^Pages:/{print $2}')
echo "Finished: $jobname.pdf${pages:+ ($pages pages)}"

if [ "$cleanup" -eq 1 ]; then
    echo "Cleaning build files..."
    "$SCRIPT_DIR/cleanup.sh" .
fi
