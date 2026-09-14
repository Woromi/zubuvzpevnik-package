#!/usr/bin/env python3
"""Report which paper sizes each song fits on, and measure it by typesetting.

The pap={} song key names the sizes a song has been checked on; a song without
one counts as A4 only, which is where every song started. Reading the flags is
the default; --measure typesets the whole database on one paper and says which
songs really fit a single page. Read-only unless --write is given.

Usage: scripts/checkpaper.py [options] [PATH ...]   (--help for the options)
Exit status: 0 = clean, 1 = a flag disagrees with the measurement, 2 = nothing found.
"""

# TODO: Not only it should check if it fits the page, but it should also check if all lines fit on one line (no auto line break)

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checksongs import (collect_song_files, find_matching, input_name,  # noqa: E402
                        parse_song, strip_comments)

# Paper -> the document class that typesets it. Add a row when a class is added.
PAPER_CLASS = {"a4": "velkyzpevnik", "a5": "taborovyzpevnik"}
CLASS_PAPER = {cls: paper for paper, cls in PAPER_CLASS.items()}
# What every project passes; the probe has to match to measure the real layout.
CLASS_OPTIONS = "chorded, onesongcolumn, noshading"

DOCCLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([a-zA-Z]+)\}")
INPUT_RE = re.compile(r"\\input\{([^}]*)\}")
# songs.sty writes one \songlink target per song into the raw index file; the
# page recorded just above it is where that song started. See docs/tools.md.
SXD_LINK_RE = re.compile(r"^song\d+-(\d+)\.\d+$")


def declared(info):
    """Paper sizes a parsed song claims to fit, lowercased, in written order.

    Every song spells the key out, so an empty list -- from pap={} or from no
    key at all -- means the song is not known to fit anything, and the build
    says so on every paper."""
    return [p.strip().lower() for p in info["keys"].get("pap", "").split(",") if p.strip()]


def project_files(repo_root):
    """Every project .tex, as (path, paper, [song input names])."""
    out = []
    for tex in sorted((repo_root / "projects").rglob("*.tex")):
        text = strip_comments(tex.read_text(encoding="utf-8", errors="replace"))
        m = DOCCLASS_RE.search(text)
        if not m:
            continue
        songs = [s.strip().removesuffix(".tex") for s in INPUT_RE.findall(text)]
        out.append((tex, CLASS_PAPER.get(m.group(1)), songs))
    return out


# --- Measuring ---------------------------------------------------------------

def write_probe(builddir, paper, names):
    """A songbook of every song, on the given paper, with nothing else on the
    pages: \\pagestyle{empty} is what makes a spilled-over page distinguishable
    from a blank one that the forced between-song break left behind."""
    body = "\n".join(f"    \\input{{{n}}}" for n in names)
    (builddir / "paperprobe.tex").write_text(
        f"\\documentclass[{CLASS_OPTIONS}]{{{PAPER_CLASS[paper]}}}\n"
        "\\title{Paper probe}\n\\author{checkpaper.py}\n"
        "\\begin{document}\n\\pagestyle{empty}\n"
        f"\\begin{{songs}}{{obsah}}\n{body}\n\\end{{songs}}\n"
        "\\end{document}\n", encoding="utf-8")


def read_sxd(path):
    """Ordinal -> starting page, from songs.sty's raw index data file."""
    starts = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        m = SXD_LINK_RE.match(line.strip())
        if m and i and lines[i - 1].strip().isdigit():
            starts[int(m.group(1))] = int(lines[i - 1].strip())
    return starts


def nonempty_pages(pdf):
    """Which 1-based pages carry any text. \\pagestyle{empty} means a page the
    between-song page break left over is genuinely empty."""
    out = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"pdftotext failed on {pdf}: {out.stderr.strip()}")
    return [bool(page.strip()) for page in out.stdout.split("\f")[:-1]]


def measure(repo_root, paper, files, keep=False, verbose=False):
    """Typeset every song on `paper`; return {input name: pages it occupies}."""
    names = [input_name(f, repo_root) for f in files]
    if any(n is None for n in names):
        raise RuntimeError("--measure only handles songs under songs/chords or songs/tinwhistle")

    builddir = Path(tempfile.mkdtemp(prefix="checkpaper-"))
    try:
        # Share the repo's LilyPond cache: a re-measure then costs no lilypond runs.
        (repo_root / "tmp-ly").mkdir(exist_ok=True)
        (builddir / "tmp-ly").symlink_to(repo_root / "tmp-ly")
        if (repo_root / "img").is_dir():
            (builddir / "img").symlink_to(repo_root / "img")
        write_probe(builddir, paper, names)

        env = dict(os.environ)
        env["TEXINPUTS"] = os.pathsep.join(
            [".", str(repo_root / "zubuvzpevnik"), str(repo_root / "songs" / "chords"),
             str(repo_root / "songs" / "tinwhistle"), env.get("TEXINPUTS", "")])
        env["max_print_line"] = "120"
        print(f"Typesetting {len(names)} songs on {paper}...", file=sys.stderr)
        run = subprocess.run(
            ["lualatex", "-shell-escape", "-interaction=nonstopmode", "paperprobe.tex"],
            cwd=builddir, env=env, capture_output=True, text=True)
        log = (builddir / "paperprobe.log")
        if not (builddir / "paperprobe.pdf").exists():
            tail = "\n".join((log.read_text(errors="replace").splitlines())[-25:]) if log.exists() else run.stdout[-2000:]
            raise RuntimeError(f"lualatex produced no PDF:\n{tail}")
        if verbose:
            for line in log.read_text(errors="replace").splitlines():
                if line.startswith("!"):
                    print(f"  lualatex: {line}", file=sys.stderr)

        starts = read_sxd(builddir / "obsah.sxd")
        filled = nonempty_pages(builddir / "paperprobe.pdf")

        # A file may hold more than one \beginsong, so walk ordinals per file.
        pages, ordinal = {}, 1
        spans = []
        for f, name in zip(files, names):
            n = max(1, parse_song(f)["n_begin"])
            spans.append((name, ordinal, ordinal + n))
            ordinal += n
        total = len(filled)
        for i, (name, first, nxt) in enumerate(spans):
            if first not in starts:
                continue                      # song never reached the PDF
            start = starts[first]
            end = starts.get(nxt, total + 1) if i + 1 < len(spans) else total + 1
            # Trailing blanks belong to the forced break, not to the song.
            pages[name] = sum(1 for p in range(start, end) if filled[p - 1])
        return pages
    finally:
        if keep:
            print(f"Probe kept in {builddir}", file=sys.stderr)
        else:
            shutil.rmtree(builddir, ignore_errors=True)


# --- Writing the key back ----------------------------------------------------

def set_pap(path, papers):
    """Write pap={...} into a song's prelude, matching the file's own layout.

    An empty list takes the key back out: a song that fits nothing says so by
    having no pap key, so there is no second spelling of the same answer."""
    text = path.read_text(encoding="utf-8")
    value = ",".join(papers)
    pos = text.find("\\beginsong")
    brace = text.find("{", pos)
    tend = find_matching(text, brace, "{", "}")
    m = tend + 1
    while m < len(text) and text[m] in " \t\r\n":
        m += 1

    if m >= len(text) or text[m] != "[":          # no prelude to put it in
        if not papers:
            return
        new = text[:tend + 1] + f"[pap={{{value}}}]" + text[tend + 1:]
        path.write_text(new, encoding="utf-8")
        return

    bend = find_matching(text, m, "[", "]")
    body = text[m + 1:bend]
    existing = re.search(r"pap\s*=\s*\{[^}]*\}", body)

    if not papers:
        if not existing:
            return
        # Take the whole entry with it: its own line, or its share of the
        # separators in a one-line prelude.
        body, cut = re.subn(r"\n[ \t]*pap\s*=\s*\{[^}]*\}[ \t]*,?", "", body, count=1)
        if not cut:
            body = re.sub(r",?[ \t]*pap\s*=\s*\{[^}]*\}[ \t]*,?[ \t]*", "", body, count=1)
        # If the key was all the prelude held, the brackets go too.
        new = text[:m] + text[bend + 1:] if not body.strip() else text[:m + 1] + body + text[bend:]
    elif existing:
        new = text[:m + 1] + body[:existing.start()] + f"pap={{{value}}}" + body[existing.end():] + text[bend:]
    else:
        if "\n" in body:
            # One key per line: indent like the first key, since the last line
            # may be the closing brace of a multi-line value such as chr={}.
            indent = re.findall(r"\n([ \t]*)\S", body)
            pad = indent[0] if indent else "    "
            body = body.rstrip().rstrip(",") + f",\n{pad}pap={{{value}}},\n"
        else:
            body = body.rstrip().rstrip(",") + f", pap={{{value}}}"
        new = text[:m + 1] + body + text[bend:]
    path.write_text(new, encoding="utf-8")


# --- Reports -----------------------------------------------------------------

def bar(n, total):
    return "#" * round(20 * n / total) if total else ""


def report_flags(parsed, repo_root, summary_only):
    groups = {}
    for f, info in parsed:
        groups.setdefault(",".join(declared(info)) or "(none)", []).append((f, info))
    total = len(parsed)

    if not summary_only:
        for papers in sorted(groups):
            rows = groups[papers]
            print(f"\n{papers}  ({len(rows)} songs)")
            width = max(len(os.path.relpath(f, repo_root)) for f, _ in rows)
            for f, info in sorted(rows, key=lambda r: str(r[0])):
                rel = os.path.relpath(f, repo_root)
                print(f"  {rel:<{width}}  {info['title'] or ''}")

    print(f"\n{'=' * 60}")
    print(f"{total} songs by declared paper fit:")
    for papers in sorted(groups):
        n = len(groups[papers])
        print(f"  {papers:<12} {n:>3}  {100 * n / total:5.1f}%  {bar(n, total)}")
    per_paper = {}
    for f, info in parsed:
        for p in declared(info):
            per_paper[p] = per_paper.get(p, 0) + 1
    print("Songs fitting each paper:")
    for p in sorted(per_paper):
        print(f"  {p:<12} {per_paper[p]:>3}  {100 * per_paper[p] / total:5.1f}%  {bar(per_paper[p], total)}")


def report_projects(parsed, repo_root):
    """Each project against the paper its class typesets: a song built into a
    book it is not marked for is one nobody has checked at that size."""
    by_name = {}
    for f, info in parsed:
        name = input_name(f, repo_root)
        if name:
            by_name[name] = info
    print("\nProjects:")
    unchecked = 0
    for tex, paper, songs in project_files(repo_root):
        rel = os.path.relpath(tex, repo_root)
        if paper is None:
            print(f"  {rel}: unknown class, skipped")
            continue
        missing = [s for s in songs if s in by_name and paper not in declared(by_name[s])]
        unknown = [s for s in songs if s not in by_name]
        note = f"{len(songs)} songs, {len(songs) - len(missing) - len(unknown)} marked {paper}"
        print(f"  {rel} [{paper}]: {note}")
        for s in missing:
            print(f"      ⚠ {s} is not marked as fitting {paper}")
        for s in unknown:
            print(f"      ⚠ {s} was not scanned")
        unchecked += len(missing)
    return unchecked


def report_measured(parsed, repo_root, paper, pages, write):
    """Measured page counts against the flags. One page = fits."""
    print(f"\nMeasured on {paper} ({PAPER_CLASS[paper]}):")
    add, drop, missing = [], [], []
    for f, info in sorted(parsed, key=lambda r: str(r[0])):
        name = input_name(f, repo_root)
        n = pages.get(name)
        papers = declared(info)
        if n is None:
            missing.append((f, info))
            continue
        fits, flagged = n == 1, paper in papers
        if fits and not flagged:
            add.append((f, info, n))
        elif not fits and flagged:
            drop.append((f, info, n))

    for label, rows, verb in (
            (f"Fits on one {paper} page but is not marked {paper}", add, "add"),
            (f"Marked {paper} but needs more than one page", drop, "remove")):
        if not rows:
            continue
        print(f"\n  {label} ({len(rows)}):")
        for f, info, n in rows:
            rel = os.path.relpath(f, repo_root)
            print(f"    {'+' if verb == 'add' else '-'} {rel}  ({n} page{'s' if n != 1 else ''})")
    if missing:
        print(f"\n  Not measured ({len(missing)}): " +
              ", ".join(os.path.relpath(f, repo_root) for f, _ in missing))

    fitting = sum(1 for n in pages.values() if n == 1)
    print(f"\n{'=' * 60}")
    print(f"{fitting}/{len(pages)} songs fit a single {paper} page; "
          f"{len(add)} to add, {len(drop)} to remove.")

    if write:
        for f, info, _ in add:
            set_pap(f, sorted(set(declared(info)) | {paper}))
        for f, info, _ in drop:
            set_pap(f, [p for p in declared(info) if p != paper])
        print(f"Wrote the pap key in {len(add) + len(drop)} file(s).")
    return len(add) + len(drop)


def main():
    ap = argparse.ArgumentParser(description="Report song paper fit.")
    ap.add_argument("paths", nargs="*", help="files/dirs to scan (default: songs/)")
    ap.add_argument("--summary", action="store_true", help="counts only, no song lists")
    ap.add_argument("--measure", metavar="PAPER", choices=sorted(PAPER_CLASS),
                    help="typeset every song on PAPER and compare with the flags")
    ap.add_argument("--write", action="store_true",
                    help="with --measure: write the measured result into the songs")
    ap.add_argument("--keep", action="store_true", help="with --measure: keep the probe build")
    ap.add_argument("-v", "--verbose", action="store_true", help="show lualatex errors")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any disagreement")
    args = ap.parse_args()

    if args.write and not args.measure:
        ap.error("--write only makes sense with --measure")

    repo_root = Path(__file__).resolve().parent.parent
    scan = args.paths if args.paths else [repo_root / "songs"]
    # Resolved, so input_name() works whether the caller typed a relative path.
    files = [f.resolve() for f in collect_song_files(scan)]
    if not files:
        print("No .tex song files found.", file=sys.stderr)
        return 2
    parsed = [(f, parse_song(f)) for f in files]

    if args.measure:
        pages = measure(repo_root, args.measure, files, keep=args.keep, verbose=args.verbose)
        disagreements = report_measured(parsed, repo_root, args.measure, pages, args.write)
        return 1 if (args.strict and disagreements and not args.write) else 0

    report_flags(parsed, repo_root, args.summary)
    unchecked = report_projects(parsed, repo_root)
    return 1 if (args.strict and unchecked) else 0


if __name__ == "__main__":
    sys.exit(main())
