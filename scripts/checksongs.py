#!/usr/bin/env python3
"""Lint the song database for missing or suspicious metadata.

Scans the \\beginsong[...] preludes under songs/ and reports songs that are
missing recommended metadata (tempo, key, tuning, language, ...), use an
unknown song key (likely a typo), carry an unusual language, or look
structurally broken. It also lists songs that no project \\input{}s, since
those silently never appear in any songbook.

This is a developer convenience tool, not part of the build: nothing here
edits files or affects the produced PDFs.

Usage:
    scripts/checksongs.py [options] [PATH ...]

    PATH        Files or directories to scan (default: the songs/ dir).
    --all       Also list songs that have no issues.
    --missing FIELD[,FIELD...]
                Only report songs missing the given field(s), e.g. "tem,key".
    --no-orphans  Skip the "not referenced by any project" check.
    --csv       Emit one CSV row per song (all metadata) instead of a report.
    --strict    Exit non-zero if any warning (not just error) is found.

Exit status: 0 = clean, 1 = errors found (or warnings with --strict).
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

# --- Text that will not reach the PDF as intended ---------------------------
# The books set text in Open Sans, which has no arrows (U+2190-21FF) and no
# musical accidentals (U+266D-266F). LuaLaTeX does not fail on those: it logs
# "Missing character" and drops them, so they vanish from the PDF without the
# build ever going red. Verified by rendering each form and reading the glyph
# back out of the PDF -- \rightarrow and $\rightarrow$ both draw an arrow (they
# resolve through the math font), while \textrightarrow asks the text font and
# so drops exactly like the bare character.
UNRENDERABLE = {
    "♭": r"\flt",
    "♮": r"\natural",
    "♯": r"\shrp",
}
ARROWS = range(0x2190, 0x2200)
# House style for a song that modulates: no spaces around the arrow, as in
# key={Cm\rightarrow C}. The space after the macro is TeX's control-word
# delimiter and is swallowed, so it prints tight on both sides.
ARROW_HINT = r"\rightarrow, as in key={Cm\rightarrow C}"
BROKEN_MACROS = {r"\textrightarrow": ARROW_HINT}

# songs.sty draws chord accidentals with its own \shrp / \flt (songs.sty:2632).
# The math-mode \sharp / \flat render fine but draw a different glyph, so mixing
# them makes the prelude's accidentals disagree with the printed chords.
PREFER_SONGS_ACCIDENTAL = {r"\flat": r"\flt", r"\sharp": r"\shrp"}

# `Bb`/`Eb` spelling typesets as the literal letters instead of a flat sign. It
# is legible but inconsistent with the rest of the book, and checkkeys.py reads
# the `b` as part of the chord quality rather than as an accidental.
ASCII_FLAT_KEY = re.compile(r"(?<![A-Za-z])([A-H])b")
ASCII_FLAT_CHORD = re.compile(r"\\\[([A-H])b")

# --- What counts as a song key ---------------------------------------------
# Custom keys defined by this repo (zubuvzpevnik/feature/metadata.cfg and
# lokalizace.cfg) plus the songs-package built-ins. Anything else in a
# \beginsong prelude is flagged as a possible typo.
CUSTOM_KEYS = {"lang", "key", "tun", "tem", "ori", "chr", "src"}
BUILTIN_KEYS = {"by", "cr", "li", "index", "ititle"}
KNOWN_KEYS = CUSTOM_KEYS | BUILTIN_KEYS

# Recommended metadata, by song kind. Missing ones are warned about; the
# README treats everything except `by` as optional, so these are nudges, not
# errors. ori/chr/src/cr/li/ititle are situational and never nagged about.
REQUIRED = ["by"]
RECOMMENDED_CHORDS = ["lang", "key", "tem", "tun"]
RECOMMENDED_TINWHISTLE = ["key", "tem"]  # instrumental: lang/tun not expected

# Languages we recognise. A lang= value outside this set is flagged as a
# likely typo. Add new languages here when you genuinely introduce one.
KNOWN_LANGS = {
    "czech", "slovak", "english", "german", "french", "spanish",
    "italian", "polish", "hungarian", "latin", "quenya",
}

# Fields shown (in this order) in --csv output and the completeness table.
ALL_FIELDS = ["by", "lang", "key", "tem", "tun", "ori", "chr", "src"]


class Severity:
    ERROR = "error"
    WARN = "warn"


SYMBOL = {Severity.ERROR: "✗", Severity.WARN: "⚠"}  # ✗  ⚠


def strip_comments(text):
    """Blank out TeX line comments so commented-out metadata, braces, and
    \\beginsong/\\endsong inside comments are never parsed as real. A `%`
    starts a comment unless escaped as `\\%`; the rest of the line is dropped
    (the newline is kept so line structure is preserved)."""
    out = []
    for line in text.splitlines(keepends=True):
        i, cut = 0, None
        while i < len(line):
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c == "%":
                cut = i
                break
            i += 1
        if cut is None:
            out.append(line)
        else:
            tail = "\n" if line.endswith("\n") else ""
            out.append(line[:cut] + tail)
    return "".join(out)


def find_matching(text, open_pos, open_ch, close_ch):
    """Return index of the close char matching the opener at open_pos.

    Respects nesting of the same open/close pair. Returns -1 if unbalanced.
    """
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":  # skip escaped char (e.g. \{ \} \[ )
            i += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_brace_aware(text, start, target):
    """Index of the first `target` char at/after `start` that is not nested
    inside a {...} group (and not backslash-escaped). -1 if none."""
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif c == target and depth == 0:
            return i
        i += 1
    return -1


def parse_prelude(block):
    """Parse a `[key={val}, ...]` prelude body into a dict of key -> value.

    Brace-aware so values may contain commas, brackets, and TeX macros.
    Bare (unbraced) values are accepted too. Order is not preserved beyond
    insertion; the last value wins on duplicate keys.
    """
    keys = {}
    i, n = 0, len(block)
    while i < n:
        c = block[i]
        if c in " \t\r\n,":
            i += 1
            continue
        # read key name
        j = i
        while j < n and (block[j].isalpha() or block[j].isdigit()):
            j += 1
        name = block[i:j]
        # skip spaces, expect '='
        k = j
        while k < n and block[k] in " \t\r\n":
            k += 1
        if k >= n or block[k] != "=":
            # not a key=value form; skip to next comma to stay in sync
            nxt = find_brace_aware(block, i, ",")
            if nxt == -1:
                break
            i = nxt + 1
            continue
        k += 1
        while k < n and block[k] in " \t\r\n":
            k += 1
        if k < n and block[k] == "{":
            end = find_matching(block, k, "{", "}")
            if end == -1:
                value = block[k + 1:].strip()
                i = n
            else:
                value = block[k + 1:end].strip()
                i = end + 1
        else:
            nxt = find_brace_aware(block, k, ",")
            if nxt == -1:
                value = block[k:].strip()
                i = n
            else:
                value = block[k:nxt].strip()
                i = nxt
        if name:
            keys[name] = value
    return keys


def parse_song(path):
    """Parse one song .tex file.

    Returns a dict with: title, keys (dict), n_begin, n_end, error (str|None).
    """
    text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    info = {"title": None, "keys": {}, "n_begin": text.count("\\beginsong"),
            "n_end": text.count("\\endsong"), "error": None, "text": text}

    pos = text.find("\\beginsong")
    if pos == -1:
        info["error"] = "no \\beginsong"
        return info

    # Title: the {...} immediately after \beginsong.
    brace = text.find("{", pos)
    if brace == -1:
        info["error"] = "\\beginsong without title"
        return info
    tend = find_matching(text, brace, "{", "}")
    if tend == -1:
        info["error"] = "unbalanced braces in title"
        return info
    info["title"] = text[brace + 1:tend].strip()

    # Optional prelude [...] right after the title.
    rest_start = tend + 1
    m = rest_start
    n = len(text)
    while m < n and text[m] in " \t\r\n":
        m += 1
    if m < n and text[m] == "[":
        bend = find_matching(text, m, "[", "]")
        if bend == -1:
            info["error"] = "unbalanced [...] prelude"
            return info
        info["keys"] = parse_prelude(text[m + 1:bend])
    return info


def check_rendering(info):
    """Flag text that will not reach the PDF as intended.

    Each distinct offender is reported once, with the first line it appears on
    and how many times, so a song that uses a bad character throughout gives one
    line of output rather than dozens."""
    issues = []
    text = info.get("text") or ""

    bad = {}                      # char -> [first line, count, hint]
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line:
            hint = UNRENDERABLE.get(ch)
            if hint is None and ord(ch) in ARROWS:
                hint = ARROW_HINT
            if hint is None:
                continue
            if ch in bad:
                bad[ch][1] += 1
            else:
                bad[ch] = [lineno, 1, hint]
    for ch, (lineno, count, hint) in sorted(bad.items()):
        times = "" if count == 1 else f", {count}x"
        issues.append((Severity.ERROR,
                       f"'{ch}' (U+{ord(ch):04X}) has no glyph in the songbook font "
                       f"and is dropped silently - use {hint}  [line {lineno}{times}]"))

    for macro, hint in BROKEN_MACROS.items():
        n = text.count(macro)
        if n:
            issues.append((Severity.ERROR,
                           f"{macro} resolves through the text font, which has no arrow, "
                           f"so it is dropped silently - use {hint}  [{n}x]"))

    for macro, better in PREFER_SONGS_ACCIDENTAL.items():
        # \flat must not also match \flattening etc., and \sharp not \sharps
        n = len(re.findall(re.escape(macro) + r"(?![a-zA-Z])", text))
        if n:
            issues.append((Severity.WARN,
                           f"{macro} draws a different glyph than the chords do - "
                           f"use songs' {better}  [{n}x]"))

    key = info["keys"].get("key", "")
    if ASCII_FLAT_KEY.search(key):
        issues.append((Severity.WARN,
                       f"key={{{key}}} spells a flat as 'b' - use \\flat so it prints as a flat sign"))
    roots = sorted(set(ASCII_FLAT_CHORD.findall(text)))
    if roots:
        spelled = ", ".join(f"\\[{r}b...]" for r in roots)
        issues.append((Severity.WARN,
                       f"chord spells a flat as 'b' ({spelled}) - use & so songs.sty "
                       "prints a flat sign"))
    return issues


def song_kind(path):
    return "tinwhistle" if "tinwhistle" in path.parts else "chords"


def check_song(path, info):
    """Return a list of (severity, message) issues for one parsed song."""
    issues = []
    if info["error"]:
        issues.append((Severity.ERROR, info["error"]))
        return issues
    if info["n_begin"] != 1:
        issues.append((Severity.WARN, f"{info['n_begin']} \\beginsong in file (expected 1)"))
    if info["n_end"] != info["n_begin"]:
        issues.append((Severity.ERROR, f"{info['n_begin']} \\beginsong but {info['n_end']} \\endsong"))
    if not info["title"]:
        issues.append((Severity.ERROR, "empty title"))

    keys = info["keys"]
    for req in REQUIRED:
        if req not in keys or not keys[req]:
            issues.append((Severity.ERROR, f"missing required key '{req}'"))

    recommended = RECOMMENDED_TINWHISTLE if song_kind(path) == "tinwhistle" else RECOMMENDED_CHORDS
    missing = [k for k in recommended if k not in keys or not keys[k]]
    if missing:
        issues.append((Severity.WARN, "missing recommended: " + ", ".join(missing)))

    unknown = sorted(k for k in keys if k not in KNOWN_KEYS)
    if unknown:
        issues.append((Severity.WARN, "unknown key (typo?): " + ", ".join(unknown)))

    lang = keys.get("lang", "").strip()
    if lang and lang not in KNOWN_LANGS:
        issues.append((Severity.WARN, f"unusual language '{lang}' (typo? add to KNOWN_LANGS if intended)"))

    issues.extend(check_rendering(info))
    return issues


def collect_song_files(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.tex")))
        elif p.suffix == ".tex":
            files.append(p)
    # de-dup, keep order
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def referenced_inputs(repo_root):
    """Set of \\input{...} targets across all project .tex files (the part
    after Artist/, i.e. how songs are referenced)."""
    refs = set()
    proj = repo_root / "projects"
    if not proj.is_dir():
        return refs
    import re
    pat = re.compile(r"\\input\{([^}]*)\}")
    for tex in proj.rglob("*.tex"):
        for m in pat.finditer(tex.read_text(encoding="utf-8", errors="replace")):
            refs.add(m.group(1).strip().removesuffix(".tex"))
    return refs


def input_name(path, repo_root):
    """How `path` would be referenced in an \\input{}: the path relative to
    songs/chords or songs/tinwhistle, without .tex. Returns None if outside."""
    for base in ("songs/chords", "songs/tinwhistle"):
        root = repo_root / base
        try:
            rel = path.relative_to(root)
            return str(rel.with_suffix(""))
        except ValueError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description="Lint song metadata.", add_help=True)
    ap.add_argument("paths", nargs="*", help="files/dirs to scan (default: songs/)")
    ap.add_argument("--all", action="store_true", help="also list clean songs")
    ap.add_argument("--missing", help="only report songs missing these field(s), comma-separated")
    ap.add_argument("--no-orphans", action="store_true", help="skip the unreferenced-song check")
    ap.add_argument("--csv", action="store_true", help="emit CSV of all metadata instead of a report")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    scan = args.paths if args.paths else [repo_root / "songs"]
    files = collect_song_files(scan)
    if not files:
        print("No .tex song files found.", file=sys.stderr)
        return 2

    parsed = [(f, parse_song(f)) for f in files]

    if args.csv:
        w = csv.writer(sys.stdout)
        w.writerow(["file", "title", "kind"] + ALL_FIELDS)
        for f, info in parsed:
            rel = os.path.relpath(f, repo_root)
            row = [rel, info["title"] or "", song_kind(f)]
            row += [info["keys"].get(k, "") for k in ALL_FIELDS]
            w.writerow(row)
        return 0

    missing_filter = None
    if args.missing:
        missing_filter = [s.strip() for s in args.missing.split(",") if s.strip()]

    n_err = n_warn = n_clean = 0
    field_present = {k: 0 for k in ALL_FIELDS}

    for f, info in parsed:
        for k in ALL_FIELDS:
            if info["keys"].get(k):
                field_present[k] += 1

        if missing_filter is not None:
            miss = [k for k in missing_filter if not info["keys"].get(k)]
            if miss:
                rel = os.path.relpath(f, repo_root)
                print(f"{rel}\n  ⚠ missing: {', '.join(miss)}")
            continue

        issues = check_song(f, info)
        errs = [i for i in issues if i[0] == Severity.ERROR]
        warns = [i for i in issues if i[0] == Severity.WARN]
        n_err += len(errs)
        n_warn += len(warns)
        if not issues:
            n_clean += 1
            if args.all:
                rel = os.path.relpath(f, repo_root)
                print(f"{rel}\n  ✓ ok")
            continue
        rel = os.path.relpath(f, repo_root)
        print(rel)
        for sev, msg in errs + warns:
            print(f"  {SYMBOL[sev]} {msg}")

    if missing_filter is not None:
        return 0

    # Orphan songs: present in songs/ but \input by no project.
    orphans = []
    if not args.no_orphans:
        refs = referenced_inputs(repo_root)
        for f, _ in parsed:
            name = input_name(f, repo_root)
            if name is not None and name not in refs:
                orphans.append(name)
    if orphans:
        print("\nNot referenced by any project (won't appear in any songbook):")
        for name in sorted(orphans):
            print(f"  ⚠ {name}")

    # Summary
    total = len(parsed)
    print(f"\n{'='*48}")
    print(f"Scanned {total} songs: {n_clean} clean, {n_err} error(s), {n_warn} warning(s)"
          + (f", {len(orphans)} orphan(s)" if not args.no_orphans else ""))
    print("Field completeness:")
    for k in ALL_FIELDS:
        have = field_present[k]
        pct = 100 * have / total if total else 0
        bar = "#" * round(pct / 5)
        print(f"  {k:<5} {have:>3}/{total}  {pct:5.1f}%  {bar}")

    if n_err or (args.strict and (n_warn or orphans)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
