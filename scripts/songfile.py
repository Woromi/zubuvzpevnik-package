"""Reading a song .tex file: comments, braces, the \\beginsong prelude.

No policy lives here -- only what all three tools under scripts/ need to
read the song database the same way. See docs/tools.md.
"""

import sys
from pathlib import Path


def song_langs(keys):
    """lang={czech, quenya} -> ["czech", "quenya"]: the first is the song's
    language, the rest only tag it (lokalizace.cfg)."""
    return [lang.strip() for lang in keys.get("lang", "").split(",") if lang.strip()]


def main_lang(keys):
    """The language that decides grammar, chord naming and book filtering."""
    langs = song_langs(keys)
    return langs[0] if langs else ""


def strip_comments(text):
    """Blank out TeX line comments, keeping newlines so line numbers survive."""
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
    """Parse a `[key={val}, ...]` prelude body into a dict. Brace-aware, so
    values may hold commas, brackets and macros; last value wins on duplicates."""
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


# ---- Where things are ----
# The package (this repo) and the songbook it serves live apart: the songbook has the package
# as a submodule at <songbook>/zubuvzpevnik, and the app bundles a copy of its own. The tools
# take the songbook from --songbook, else the nearest folder with songs/chords above the
# package or above the working directory.

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def songbook_root(explicit=None):
    """The songbook checkout: `explicit` (from --songbook), else the nearest folder above this
    package or above the working directory that has songs/chords. Exits with a hint when there
    is none."""
    if explicit:
        root = Path(explicit).resolve()
        if not (root / "songs" / "chords").is_dir():
            sys.exit(f"{root} has no songs/chords: --songbook has to name the songbook checkout")
        return root
    for start in (PACKAGE_DIR, Path.cwd().resolve()):
        for candidate in (start, *start.parents):
            if (candidate / "songs" / "chords").is_dir():
                return candidate
    sys.exit("No songbook found above the package or the working directory: pass --songbook DIR")
