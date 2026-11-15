#!/usr/bin/env python3
"""Check that a book prints its songs in the order its title index lists them.

Read-only developer tool. The index is sorted by songidx.lua (Czech collation,
English articles rotated to the end), so the check sorts the project's songs
with that very script rather than guessing at its rules. See docs/tools.md.

Usage: scripts/checkorder.py [--json] PROJECT.tex ...
Exit status: 0 = in order, 1 = out of order, 2 = no songs found.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from songfile import (main_lang, parse_song, print_json, songbook_root,  # noqa: E402
                      strip_comments)

REPO = songbook_root()  # the projects named lie inside it
SONG_DIRS = [REPO / "songs" / "chords", REPO / "songs" / "tinwhistle"]
INPUT = re.compile(r"\\input\{([^}]+)\}")
# "% checkorder: ok" after a song's \input accepts it coming before the song
# the index would put first -- a deliberate exception such as Day Six, Day Seven.
ACCEPTED = re.compile(r"\\input\{([^}]+)\}\s*%.*checkorder:\s*ok")
ENTRY = re.compile(r"\\idxentry\{.*?\}\{\\songlink\{[^}]*\}\{(\d+)\}\}")


def czech_locale():
    """The Czech locale buildindex.sh would use, or None."""
    names = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.split()
    for cand in ("cs_CZ.utf8", "cs_CZ.UTF-8", "cs_CZ"):
        for name in names:
            if name.lower() == cand.lower():
                return name
    return None


def book_songs(project):
    """(title, lang, input name, accepted) of every song the project inputs,
    in book order."""
    raw = project.read_text(encoding="utf-8")
    accepted = set(ACCEPTED.findall(raw))
    text = strip_comments(raw)
    songs = []
    for name in INPUT.findall(text):
        path = next((d / f"{name}.tex" for d in SONG_DIRS
                     if (d / f"{name}.tex").exists()), None)
        if path is None:
            continue                      # an \input that is not a song
        info = parse_song(path)
        if info["title"]:
            songs.append((info["title"], main_lang(info["keys"]), name,
                          name in accepted))
    return songs


def index_order(songs):
    """Book positions of the songs in the order songidx.lua sorts them."""
    with tempfile.TemporaryDirectory() as tmp:
        sxd, sbx = Path(tmp) / "order.sxd", Path(tmp) / "order.sbx"
        lines = ["TITLE INDEX DATA FILE"]
        for pos, (title, lang, *_) in enumerate(songs, 1):
            lines += [f"%lang {lang or 'english'}", title, str(pos), f"song1-{pos}.1"]
        sxd.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = ["texlua", str(Path(__file__).resolve().parent / "songidx.lua")]
        loc = czech_locale()
        if loc:
            cmd += ["-l", loc]
        else:
            print("warning: no Czech locale; sorting with the system default",
                  file=sys.stderr)
        subprocess.run(cmd + [str(sxd), str(sbx)], check=True, capture_output=True)
        return [int(p) for p in ENTRY.findall(sbx.read_text(encoding="utf-8"))]


def main():
    ap = argparse.ArgumentParser(description="Check a book's song order against its index.")
    ap.add_argument("projects", nargs="*", type=Path, metavar="PROJECT.tex")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON (see docs/tools.md#machine-readable-output)")
    args = ap.parse_args()
    if not args.projects:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    status, report = 0, []
    for project in args.projects:
        record = {"file": str(project), "songs": 0, "in_order": None,
                  "out_of_order": [], "error": None}
        report.append(record)
        if not project.is_file():
            record["error"] = "no such file"
            print(f"{project}: no such file", file=sys.stderr)
            status = max(status, 2)
            continue
        songs = book_songs(project)
        if not songs:
            record["error"] = "no songs found"
            print(f"{project}: no songs found", file=sys.stderr)
            status = max(status, 2)
            continue
        order = index_order(songs)
        # a pair is excused when the song the book puts first carries the mark
        wrong = [(a, b) for a, b in zip(order, order[1:])
                 if b < a and not songs[b - 1][3]]
        record["songs"], record["in_order"] = len(songs), not wrong
        # the index lists the song at book position a first, b next
        record["out_of_order"] = [
            {"first": {"title": songs[a - 1][0], "input": songs[a - 1][2]},
             "second": {"title": songs[b - 1][0], "input": songs[b - 1][2]}}
            for a, b in wrong]
        if wrong:
            status = max(status, 1)
        if args.json:
            continue
        if not wrong:
            print(f"{project}: {len(songs)} songs, in index order")
            continue
        print(f"{project}: out of index order")
        for pair in record["out_of_order"]:
            first, second = pair["first"], pair["second"]
            print(f"  '{first['title']}' ({first['input']}) sorts before '{second['title']}' "
                  f"({second['input']}), but the book has it after")
    if args.json:
        print_json({"tool": "checkorder", "projects": report})
    return status


if __name__ == "__main__":
    sys.exit(main())
