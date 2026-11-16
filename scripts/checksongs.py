#!/usr/bin/env python3
"""Lint the song database for missing or suspicious metadata.

Read-only developer tool: it never edits files or affects the build.
Every check, and why it exists, is described in docs/tools.md.

Usage: scripts/checksongs.py [options] [PATH ...]   (--help for the options)
Exit status: 0 = clean, 1 = errors (or warnings with --strict), 2 = nothing found.
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from songfile import books_dir, songbook_root  # noqa: E402
from songfile import (collect_song_files, input_name, main_lang,  # noqa: E402
                      parse_song, print_json, song_langs, strip_comments)

# --- Text that will not reach the PDF as intended ---------------------------
# Open Sans has no arrow or accidental glyphs, and LuaLaTeX drops a missing
# character with only a log line, so the build stays green. See docs/tools.md.
UNRENDERABLE = {
    "♭": r"\flt",
    # songs.sty has no natural, so the math sign is the only one that renders
    "♮": r"$\natural$",
    "♯": r"\shrp",
}
ARROWS = range(0x2190, 0x2200)
# House style for a modulation; the space after the macro is swallowed by TeX.
ARROW_HINT = r"\rightarrow, as in key={Cm\rightarrow C}"
BROKEN_MACROS = {r"\textrightarrow": ARROW_HINT}

# \sharp / \flat render, but not like songs' own \shrp / \flt (songs.sty:2632).
PREFER_SONGS_ACCIDENTAL = {r"\flat": r"\flt", r"\sharp": r"\shrp"}

# `Bb` typesets as the literal letters, and checkkeys.py reads the b as quality.
ASCII_FLAT_KEY = re.compile(r"(?<![A-Za-z])([A-H])b")
ASCII_FLAT_CHORD = re.compile(r"\\\[([A-H])b")
ASCII_FLAT_BASS = re.compile(r"\\\[[^\]]*/([A-H])b")

# Written out, the C in N.C. is read as a note name and transposed with the rest.
SPELLED_NOCHORD = re.compile(r"\\\[\s*N\.?\s*C\.?\s*\]")

# --- B and H ------------------------------------------------------------------
# Czech and Slovak songs are read in German naming (lokalizace.cfg): B is B-flat,
# H is B-natural. An English B-flat there reads as B-double-flat, and an H in an
# English song is no note at all -- both silently wrong, so both are errors.
GERMAN_LANGS = {"czech", "slovak"}
CHORD_GROUP = re.compile(r"\\\[([^\]]*)\]")
GTAB_NAME = re.compile(r"\\gtab\{([^}]*)\}")
NOTE_B_FLAT = re.compile(r"(?:^|/)B(?:&|b|\\flt)")
NOTE_H = re.compile(r"(?:^|/)H")

# --- Chords inside a second voice ------------------------------------------------
# A chord belongs in front of the voices, ^{\multivoice{..}{..}}: inside one it is
# placed within that voice's box, and the chord reader it starts reads ahead.
MULTIVOICE = re.compile(r"\\multivoice\{([^{}]*)\}\{([^{}]*)\}")
CHORD_MARK = re.compile(r"\^|\\\[")

# --- Chord diagrams without finger numbers ---------------------------------
# \gtab{name}{[fret:]strings[:fingers]}. songs.sty reads one colon as fret:strings
# when the first field is a single character, else as strings:fingers.
GTAB_FULL = re.compile(r"\\gtab\{([^}]*)\}\{([^}]*)\}")


def has_fingers(fingering):
    fields = fingering.split(":")
    return len(fields) >= 3 or (len(fields) == 2 and len(fields[0]) > 1)


# --- What counts as a song key ---------------------------------------------
# This repo's keys plus the songs built-ins; anything else is a possible typo.
CUSTOM_KEYS = {"lang", "key", "tun", "tem", "met", "cap", "ori", "chr", "src", "pap", "tags"}
BUILTIN_KEYS = {"by", "cr", "li", "index", "ititle"}
KNOWN_KEYS = CUSTOM_KEYS | BUILTIN_KEYS

# Recommended by song kind: nudges, not errors. Situational keys are not nagged.
REQUIRED = ["by"]
RECOMMENDED_CHORDS = ["lang", "key", "tem", "tun"]
RECOMMENDED_TINWHISTLE = ["key", "tem"]  # instrumental: lang/tun not expected

# met={3/4} and cap={2}; see zubuvzpevnik/feature/metadata.cfg.
METER_VALUE = re.compile(r"\d+/\d+")
CAPO_VALUE = re.compile(r"\d+")
# A measure bar; the first one in a song shows met, or nothing without it.
MEASURE_BAR = re.compile(r"(?<!\\)\|")

# Recognised languages; anything else is flagged as a likely typo.
KNOWN_LANGS = {
    "czech", "slovak", "english", "german", "french", "spanish",
    "italian", "polish", "hungarian", "latin", "quenya", "hebrew", "japanese",
}

# Paper sizes pap={} may name; the same list drives scripts/checkpaper.py. The
# x2 suffix means two facing pages of that size, which only a two-sided book can
# promise, so a4 -- typeset by a one-sided class -- has no x2 spelling.
KNOWN_PAPERS = {"a4", "a5", "a5x2"}

# Fields shown (in this order) in --csv output and the completeness table.
ALL_FIELDS = ["by", "lang", "key", "tem", "met", "cap", "tun", "ori", "chr", "src", "pap"]


class Severity:
    ERROR = "error"
    WARN = "warn"


SYMBOL = {Severity.ERROR: "✗", Severity.WARN: "⚠"}  # ✗  ⚠

# code is stable for --json consumers; line is the first one, when there is one.
Issue = namedtuple("Issue", "severity code message line", defaults=(None,))


def check_rendering(info):
    """Flag text that will not reach the PDF as intended. Each distinct offender
    is reported once, with its first line and a count."""
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
        issues.append(Issue(Severity.ERROR, "no-glyph",
                            f"'{ch}' (U+{ord(ch):04X}) has no glyph in the songbook font "
                            f"and is dropped silently - use {hint}  [line {lineno}{times}]",
                            lineno))

    for macro, hint in BROKEN_MACROS.items():
        n = text.count(macro)
        if n:
            issues.append(Issue(Severity.ERROR, "no-glyph-macro",
                                f"{macro} resolves through the text font, which has no arrow, "
                                f"so it is dropped silently - use {hint}  [{n}x]"))

    for macro, better in PREFER_SONGS_ACCIDENTAL.items():
        # \flat must not also match \flattening etc., and \sharp not \sharps
        n = len(re.findall(re.escape(macro) + r"(?![a-zA-Z])", text))
        if n:
            issues.append(Issue(Severity.WARN, "math-accidental",
                                f"{macro} draws a different glyph than the chords do - "
                                f"use songs' {better}  [{n}x]"))

    key = info["keys"].get("key", "")
    if ASCII_FLAT_KEY.search(key):
        issues.append(Issue(Severity.WARN, "ascii-flat",
                            f"key={{{key}}} spells a flat as 'b' - use \\flt so it prints "
                            "as a flat sign"))
    roots = sorted(set(ASCII_FLAT_CHORD.findall(text)))
    basses = sorted(set(ASCII_FLAT_BASS.findall(text)))
    if roots or basses:
        spelled = ", ".join([f"\\[{r}b...]" for r in roots]
                            + [f"\\[.../{b}b]" for b in basses])
        issues.append(Issue(Severity.WARN, "ascii-flat",
                            f"chord spells a flat as 'b' ({spelled}) - use & so songs.sty "
                            "prints a flat sign"))
    n = len(SPELLED_NOCHORD.findall(text))
    if n:
        issues.append(Issue(Severity.WARN, "spelled-nochord",
                            "no-chord mark is spelled out - use \\[\\nochord], or the C is "
                            f"read as a note and transposed with the song  [{n}x]"))
    return issues


# --- Typo hints (--typos) ------------------------------------------------------
# A word the whole songbook uses once, one letter away from a word it uses
# often, is usually a slip: dětsví/dětství, zbávené/zbavené. A difference in the
# last two letters is an inflection far more often (smutný/smutně), so it is
# ignored, as is a different letter altogether. See docs/tools.md.
TYPO_MIN_LEN = 5
TYPO_TWIN_MIN = 4                 # uses of the likely-correct spelling
LYRIC_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")


def lyric_words(text):
    """The sung words of a comment-stripped song, lowercased."""
    text = re.sub(r"\\beginsong\{.*?\n\]", " ", text, count=1, flags=re.S)
    text = re.sub(r"\\\[[^\]]*\]", "", text)         # chords
    text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)       # macro names
    text = text.replace("^", "").replace("~", " ")
    return [w.lower() for w in LYRIC_WORD.findall(text)]


def _bare(ch):
    return unicodedata.normalize("NFD", ch)[0]


def _slip(rare, common):
    """True if the words differ the way a slip of the keyboard does: a diacritic
    alone (sťastná/šťastná), a doubled letter (neeed/need), or a lost or extra
    letter inside the word (dětsví/dětství). A different letter altogether
    (kopec/konec), or a change in the last two letters (smutný/smutně), is far
    more often another word or an inflection."""
    if abs(len(rare) - len(common)) > 1:
        return False
    i = 0
    while i < min(len(rare), len(common)) and rare[i] == common[i]:
        i += 1
    if len(rare) == len(common):
        return (i < len(rare) - 1 and _bare(rare[i]) == _bare(common[i])
                and rare[i + 1:] == common[i + 1:])
    longer, shorter = (rare, common) if len(rare) > len(common) else (common, rare)
    if longer[i + 1:] != shorter[i:]:
        return False
    doubled = (i > 0 and longer[i] == longer[i - 1]) or longer[i:i + 2] == longer[i] * 2
    return doubled or 0 < i < len(longer) - 2


def _english_unknown(words):
    """The words aspell does not know, or all of them if aspell is missing."""
    import shutil
    import subprocess
    if not shutil.which("aspell"):
        return set(words)
    out = subprocess.run(["aspell", "--lang=en", "list"], input="\n".join(words),
                         capture_output=True, text=True).stdout
    return set(out.split())


def typo_hints(parsed_all):
    """{path: [(rare word, likely spelling)]} across the whole songbook. In an
    English song a word the dictionary knows is no slip (grave/gave)."""
    from collections import Counter
    words = {f: lyric_words(info["text"]) for f, info in parsed_all if info["text"]}
    corpus = Counter(w for ws in words.values() for w in ws)
    common = [w for w, n in corpus.items() if n >= TYPO_TWIN_MIN]
    by_len = {}
    for w in common:
        by_len.setdefault(len(w), []).append(w)
    hints = {}
    for f, ws in words.items():
        for w in sorted(set(ws)):
            if len(w) < TYPO_MIN_LEN or corpus[w] > 1:
                continue
            twins = [c for n in (len(w) - 1, len(w), len(w) + 1)
                     for c in by_len.get(n, []) if _slip(w, c)]
            if twins:
                hints.setdefault(f, []).append((w, max(twins, key=corpus.get)))
    english = [f for f, info in parsed_all
               if main_lang(info["keys"]) == "english" and f in hints]
    unknown = _english_unknown(sorted({w for f in english for w, _ in hints[f]}))
    for f in english:
        hints[f] = [(w, c) for w, c in hints[f] if w in unknown]
        if not hints[f]:
            del hints[f]
    return hints


def check_naming(info):
    """B/H spelled for the song's naming, in chords, diagrams, key= and tun=."""
    issues = []
    text = info.get("text") or ""
    german = main_lang(info["keys"]) in GERMAN_LANGS
    wrong = NOTE_B_FLAT if german else NOTE_H
    fix = ("B-flat is plain B in Czech naming (B& reads as B-double-flat)" if german
           else "H is Czech naming; an English song writes B")
    found = {}                    # spelling -> [first line, count]
    for lineno, line in enumerate(text.splitlines(), 1):
        names = [c for g in CHORD_GROUP.findall(line) for c in g.split()]
        names += GTAB_NAME.findall(line)
        for name in names:
            if wrong.search(name):
                found.setdefault(name, [lineno, 0])[1] += 1
    for name, (lineno, count) in sorted(found.items()):
        times = "" if count == 1 else f", {count}x"
        issues.append(Issue(Severity.ERROR, "note-naming",
                            f"chord {name}: {fix}  [line {lineno}{times}]", lineno))
    key = info["keys"].get("key", "")
    if key and wrong.search(key.strip()):
        issues.append(Issue(Severity.ERROR, "note-naming", f"key={{{key}}}: {fix}"))
    tun = info["keys"].get("tun", "").split()
    if german:
        flats = [t for t in tun if "\\flt" in t or "\\shrp" in t]
        if any(NOTE_B_FLAT.match(t) for t in tun):
            issues.append(Issue(Severity.ERROR, "note-naming", f"tun: {fix}"))
        elif "B" in tun and not flats:
            # among natural strings a bare B is meant as B-natural
            issues.append(Issue(Severity.ERROR, "note-naming",
                                "tun: a B-natural string is H in Czech naming "
                                "(B reads as B-flat)"))
    elif "H" in tun:
        issues.append(Issue(Severity.ERROR, "note-naming", f"tun: {fix}"))
    return issues


def check_multivoice(info):
    """A chord inside either voice of \\multivoice; it goes right before it."""
    issues = []
    for lineno, line in enumerate((info.get("text") or "").splitlines(), 1):
        for m in MULTIVOICE.finditer(line):
            if CHORD_MARK.search(m.group(1) + m.group(2)):
                issues.append(Issue(Severity.ERROR, "chord-in-multivoice",
                                    f"chord inside {m.group(0)} - put it before: "
                                    f"^{{\\multivoice{{..}}{{..}}}}  [line {lineno}]", lineno))
    return issues


def check_fingers(info):
    """Chord diagrams drawn without finger numbers, once per song."""
    bare = [name for name, fing in GTAB_FULL.findall(info.get("text") or "")
            if not has_fingers(fing)]
    if not bare:
        return []
    return [Issue(Severity.WARN, "gtab-no-fingers", "chord diagram without finger numbers: "
             + ", ".join(dict.fromkeys(bare))
             + "  (add them after a colon: \\gtab{Am}{X02210:002310})")]


def song_kind(path):
    return "tinwhistle" if "tinwhistle" in path.parts else "chords"


def check_song(path, info):
    """Return the list of Issues for one parsed song."""
    issues = []
    if info["error"]:
        issues.append(Issue(Severity.ERROR, "parse", info["error"]))
        return issues
    if info["n_begin"] != 1:
        issues.append(Issue(Severity.WARN, "song-count",
                            f"{info['n_begin']} \\beginsong in file (expected 1)"))
    if info["n_end"] != info["n_begin"]:
        issues.append(Issue(Severity.ERROR, "unbalanced-song",
                            f"{info['n_begin']} \\beginsong but {info['n_end']} \\endsong"))
    if not info["title"]:
        issues.append(Issue(Severity.ERROR, "empty-title", "empty title"))

    keys = info["keys"]
    for req in REQUIRED:
        if req not in keys or not keys[req]:
            issues.append(Issue(Severity.ERROR, "missing-required", f"missing required key '{req}'"))

    recommended = RECOMMENDED_TINWHISTLE if song_kind(path) == "tinwhistle" else RECOMMENDED_CHORDS
    missing = [k for k in recommended if k not in keys or not keys[k]]
    if missing:
        issues.append(Issue(Severity.WARN, "missing-recommended",
                            "missing recommended: " + ", ".join(missing)))

    unknown = sorted(k for k in keys if k not in KNOWN_KEYS)
    if unknown:
        issues.append(Issue(Severity.WARN, "unknown-key", "unknown key (typo?): " + ", ".join(unknown)))

    for lang in song_langs(keys):
        if lang not in KNOWN_LANGS:
            issues.append(Issue(Severity.WARN, "unknown-lang",
                                f"unusual language '{lang}' (typo? add to KNOWN_LANGS if intended)"))

    # A paper the classes do not name can never match, so the song silently
    # counts as fitting nothing; see checkpaper.py.
    bad_paper = [p for p in (q.strip() for q in keys.get("pap", "").split(","))
                 if p and p.lower() not in KNOWN_PAPERS]
    if bad_paper:
        issues.append(Issue(Severity.WARN, "unknown-paper",
                            "unknown paper in pap: " + ", ".join(bad_paper)
                            + " (known: " + ", ".join(sorted(KNOWN_PAPERS)) + ")"))

    met = keys.get("met", "").strip()
    if "met" in keys and not METER_VALUE.fullmatch(met):
        issues.append(Issue(Severity.ERROR, "bad-meter", f"met={{{met}}} is not a meter like met={{3/4}}"))
    cap = keys.get("cap", "").strip()
    if "cap" in keys and not CAPO_VALUE.fullmatch(cap):
        issues.append(Issue(Severity.ERROR, "bad-capo", f"cap={{{cap}}} is not a fret number like cap={{2}}"))
    # A song whose meter changes states each one with \meter in the body.
    if ("met" not in keys and "\\meter{" not in info["text"]
            and song_kind(path) != "tinwhistle" and MEASURE_BAR.search(info["text"])):
        issues.append(Issue(Severity.WARN, "bars-without-meter",
                            "measure bars but no met: the first bar shows no meter"))

    issues.extend(check_rendering(info))
    issues.extend(check_naming(info))
    issues.extend(check_multivoice(info))
    issues.extend(check_fingers(info))
    return issues


def referenced_inputs(repo_root):
    """Set of \\input{...} targets across all project .tex files. Comments are
    stripped first: a song parked behind a `%` is in no songbook."""
    refs = set()
    proj = books_dir(repo_root)
    if not proj.is_dir():
        return refs
    pat = re.compile(r"\\input\{([^}]*)\}")
    for tex in proj.rglob("*.tex"):
        text = strip_comments(tex.read_text(encoding="utf-8", errors="replace"))
        for m in pat.finditer(text):
            refs.add(m.group(1).strip().removesuffix(".tex"))
    return refs


def emit_csv(parsed, repo_root):
    """All metadata as CSV, one row per song."""
    w = csv.writer(sys.stdout)
    w.writerow(["file", "title", "kind"] + ALL_FIELDS)
    for f, info in parsed:
        w.writerow([os.path.relpath(f, repo_root), info["title"] or "", song_kind(f)]
                   + [info["keys"].get(k, "") for k in ALL_FIELDS])


def main():
    ap = argparse.ArgumentParser(description="Lint song metadata.", add_help=True)
    ap.add_argument("paths", nargs="*", help="files/dirs to scan (default: songs/)")
    ap.add_argument("--all", action="store_true", help="also list clean songs")
    ap.add_argument("--missing", help="only report songs missing these field(s), comma-separated")
    ap.add_argument("--no-orphans", action="store_true", help="skip the unreferenced-song check")
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--csv", action="store_true", help="emit CSV of all metadata instead of a report")
    out.add_argument("--json", action="store_true",
                     help="emit the report as JSON (see docs/tools.md#machine-readable-output)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    ap.add_argument("--typos", action="store_true",
                    help="also hint at likely lyric typos (a heuristic; see docs/tools.md)")
    ap.add_argument("--songbook", metavar="DIR",
                    help="the songbook checkout (default: the one this package sits in, "
                         "or the one around the working directory)")
    args = ap.parse_args()

    repo_root = songbook_root(args.songbook)
    scan = args.paths if args.paths else [repo_root / "songs"]
    files = collect_song_files(scan)
    if not files:
        print("No .tex song files found.", file=sys.stderr)
        return 2

    parsed = [(f, parse_song(f)) for f in files]

    if args.csv:
        emit_csv(parsed, repo_root)
        return 0

    missing_filter = None
    if args.missing:
        missing_filter = [s.strip() for s in args.missing.split(",") if s.strip()]

    if missing_filter is not None:
        rows = []
        for f, info in parsed:
            miss = [k for k in missing_filter if not info["keys"].get(k)]
            if miss:
                rows.append((os.path.relpath(f, repo_root), info, miss))
        if args.json:
            print_json({"tool": "checksongs",
                        "songs": [{"file": rel, "title": info["title"], "missing": miss}
                                  for rel, info, miss in rows]})
            return 0
        for rel, _, miss in rows:
            print(f"{rel}\n  ⚠ missing: {', '.join(miss)}")
        return 0

    typos = {}
    if args.typos:
        # The comparison needs the whole songbook, not just the paths scanned.
        everything = [(f, parse_song(f)) for f in collect_song_files([repo_root / "songs"])]
        typos = typo_hints(everything)

    n_err = n_warn = n_clean = 0
    field_present = {k: 0 for k in ALL_FIELDS}
    reported = []                 # (relative path, info, issues), errors first

    for f, info in parsed:
        rel = os.path.relpath(f, repo_root)
        for k in ALL_FIELDS:
            if info["keys"].get(k):
                field_present[k] += 1

        issues = check_song(f, info)
        issues += [Issue(Severity.WARN, "typo", f"'{w}' is used nowhere else - typo for '{c}'?")
                   for w, c in typos.get(f, [])]
        errs = [i for i in issues if i.severity == Severity.ERROR]
        warns = [i for i in issues if i.severity == Severity.WARN]
        n_err += len(errs)
        n_warn += len(warns)
        if not issues:
            n_clean += 1
        if issues or args.all:
            reported.append((rel, info, errs + warns))

    # Orphan songs: present in songs/ but \input by no project.
    orphans = []
    if not args.no_orphans:
        refs = referenced_inputs(repo_root)
        for f, _ in parsed:
            name = input_name(f, repo_root)
            if name is not None and name not in refs:
                orphans.append(name)
    orphans.sort()
    total = len(parsed)
    status = 1 if n_err or (args.strict and (n_warn or orphans)) else 0

    if args.json:
        print_json({
            "tool": "checksongs",
            "songs": [{"file": rel, "title": info["title"],
                       "issues": [i._asdict() for i in issues]}
                      for rel, info, issues in reported],
            "orphans": None if args.no_orphans else orphans,
            "summary": {"scanned": total, "clean": n_clean, "errors": n_err,
                        "warnings": n_warn,
                        "orphans": None if args.no_orphans else len(orphans)},
            "fields": field_present,
        })
        return status

    for rel, _, issues in reported:
        if not issues:
            print(f"{rel}\n  ✓ ok")
            continue
        print(rel)
        for i in issues:
            print(f"  {SYMBOL[i.severity]} {i.message}")

    if orphans:
        print("\nNot referenced by any project (won't appear in any songbook):")
        for name in orphans:
            print(f"  ⚠ {name}")

    # Summary
    print(f"\n{'='*48}")
    print(f"Scanned {total} songs: {n_clean} clean, {n_err} error(s), {n_warn} warning(s)"
          + (f", {len(orphans)} orphan(s)" if not args.no_orphans else ""))
    print("Field completeness:")
    for k in ALL_FIELDS:
        have = field_present[k]
        pct = 100 * have / total if total else 0
        bar = "#" * round(pct / 5)
        print(f"  {k:<5} {have:>3}/{total}  {pct:5.1f}%  {bar}")

    return status


if __name__ == "__main__":
    sys.exit(main())
