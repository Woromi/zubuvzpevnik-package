#!/usr/bin/env python3
"""Report which paper sizes each song fits on, and measure it by typesetting.

The pap={} song key names the sizes a song has been checked on; a song without
one is not known to fit anything. Reading the flags is the default; --measure
typesets the whole database on one paper and says what really fits, and
--layout builds the books themselves and says whether the pages came out the
way somebody playing from them needs. Read-only unless --write is given.

Usage: scripts/checkpaper.py [options] [PATH ...]   (--help for the options)
Exit status: 0 = clean, 1 = a flag or a book disagrees with the measurement,
2 = nothing found.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from songfile import (collect_song_files, find_matching, input_name,  # noqa: E402
                      parse_song, strip_comments)

# Class -> the paper it typesets. Several classes can share a paper: the A5 ones
# share zubuvzpevnik/a5layout.cfg, so a song measures the same on either.
CLASS_PAPER = {"velkyzpevnik": "a4", "taborovyzpevnik": "a5", "malyzpevnik": "a5"}
# Paper -> the class --measure typesets it with.
PAPER_CLASS = {"a4": "velkyzpevnik", "a5": "taborovyzpevnik"}
# What every project passes; the probe has to match to measure the real layout.
CLASS_OPTIONS = "chorded, onesongcolumn, noshading"
# Classes whose book opens on a spread -- page 2 faces 3, 4 faces 5 -- so a song
# on two pages is playable without a page turn only when it starts on an even
# one. songs.sty already places it that way where it can; --layout says at what
# cost. See docs/tools.md.
SPREAD_CLASSES = {"taborovyzpevnik", "malyzpevnik"}
# pap={a5x2}: fits two facing pages of that paper rather than one. The same
# spelling is in checksongs.py's KNOWN_PAPERS and in feature/metadata.cfg. Only
# a paper whose class is two-sided can promise the two pages face each other,
# so a4 has no such mark and a song needing two A4 pages still fits nothing.
# --write never writes this one; see report_measured for why.
SPREAD_SUFFIX = "x2"
SPREAD_PAPERS = {CLASS_PAPER[cls] for cls in SPREAD_CLASSES}

DOCCLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([a-zA-Z]+)\}")
INPUT_RE = re.compile(r"\\input\{([^}]*)\}")
SONGS_ENV_RE = re.compile(r"\\begin\{songs\}")
# songs.sty writes one \songlink target per song into the raw index file; the
# page recorded just above it is where that song started. The target names the
# songs environment and the song's number within it, which restarts at 1 in
# each environment. See docs/tools.md.
SXD_LINK_RE = re.compile(r"^song(\d+)-(\d+)\.\d+$")

# Goes into the probe's preamble. A song line too wide for the column is broken
# like any other paragraph -- no overfull box, no warning, just a second line
# under the first -- so the only witness is \prevgraf, the line count of the
# paragraph songs.sty has just ended. The patch reports itself, so a songs.sty
# that no longer matches cannot pass for a clean measurement.
PROBE_PREAMBLE = r"""\makeatletter
\newwrite\zub@probe@wrap
\immediate\openout\zub@probe@wrap=\jobname.wrap\relax
\newcommand\zub@probe@line{%
  \ifnum\prevgraf>\@ne
    \immediate\write\zub@probe@wrap{%
      \thesongnum\space\ifSB@inchorus r\else\ifx\zub@replaying\@empty v\else\zub@replaying\fi\fi\space\the\inputlineno}%
  \fi}
\xpatchcmd{\SB@par}{\endgraf}{\endgraf\zub@probe@line}%
  {\immediate\write\zub@probe@wrap{ok}}%
  {\immediate\write\zub@probe@wrap{patch failed}}
\AtEndDocument{\immediate\closeout\zub@probe@wrap}
\makeatother
"""

# Prepended to a project the way build.sh prepends its language filter. A book
# with a cover restarts the page counter at the first song, so the printed page
# number does not say which side of a sheet a song is on; this records the
# counter of every sheet as it ships, in order, which pins the two together.
# \pagenumbering keeps its reset but loses its style, so the page a song writes
# into the index file is a number even in a book whose front matter counts in
# letters or roman numerals. Neither touches the page the songs are set on.
PROJECT_PREAMBLE = (
    r"\makeatletter\newwrite\zub@probe@pages"
    r"\immediate\openout\zub@probe@pages=\jobname.pagemap\relax"
    r"\AddToHook{shipout/before}{\immediate\write\zub@probe@pages{\the\c@page}}"
    r"\AtBeginDocument{\gdef\thepage{\the\c@page}"
    r"\renewcommand\pagenumbering[1]{\global\c@page\@ne\gdef\thepage{\the\c@page}}}"
    r"\makeatother")


def declared(info):
    """Paper sizes a parsed song claims to fit, lowercased, in written order.

    Every song spells the key out, so an empty list -- from pap={} or from no
    key at all -- means the song is not known to fit anything, and the build
    says so on every paper."""
    return [p.strip().lower() for p in info["keys"].get("pap", "").split(",") if p.strip()]


def claim(papers, paper):
    """Pages a pap key claims on one paper: 1, 2 facing ones, or 0 for none."""
    if paper in papers:
        return 1
    if paper + SPREAD_SUFFIX in papers:
        return 2
    return 0


def fits(paper, pages, broken):
    """How much room the measurement leaves a song on one paper: 1 page, 2
    facing ones, or 0 for no fit at all. A line too wide for the column is not a
    fit however few pages the song takes."""
    if broken or pages > 2 or (pages == 2 and paper not in SPREAD_PAPERS):
        return 0
    return pages


def entry(paper, room):
    """How a pap key spells that much room, or None for a song that fits
    neither one page of this paper nor a spread of two."""
    return {1: paper, 2: paper + SPREAD_SUFFIX}.get(room)


def by_input_name(parsed, repo_root):
    """Parsed songs keyed by the name a project \\input{}s them under."""
    return {name: info for f, info in parsed if (name := input_name(f, repo_root))}


def project_files(repo_root):
    """Every project .tex, as (path, class, paper, [[song input names] per songs
    environment]). A project may open several -- one per album in the Ayreon
    book -- and songs.sty numbers the songs of each from 1 again, so the index
    file only says which page a song is on once the environments are told
    apart."""
    out = []
    for tex in sorted((repo_root / "projects").rglob("*.tex")):
        text = strip_comments(tex.read_text(encoding="utf-8", errors="replace"))
        m = DOCCLASS_RE.search(text)
        if not m:
            continue
        groups = [[s.strip().removesuffix(".tex")
                   for s in INPUT_RE.findall(chunk.split("\\end{songs}")[0])]
                  for chunk in SONGS_ENV_RE.split(text)[1:]]
        out.append((tex, m.group(1), CLASS_PAPER.get(m.group(1)), groups))
    return out


# --- Measuring ---------------------------------------------------------------

def write_probe(builddir, paper, names):
    """A songbook of every song, on the given paper, with nothing else on the
    pages: \\pagestyle{empty} is what makes a spilled-over page distinguishable
    from a blank one that the forced between-song break left behind."""
    body = "\n".join(f"    \\input{{{n}}}" for n in names)
    (builddir / "paperprobe.tex").write_text(
        f"\\documentclass[{CLASS_OPTIONS}]{{{PAPER_CLASS[paper]}}}\n"
        f"{PROBE_PREAMBLE}"
        "\\title{Paper probe}\n\\author{checkpaper.py}\n"
        "\\begin{document}\n\\pagestyle{empty}\n"
        f"\\begin{{songs}}{{obsah}}\n{body}\n\\end{{songs}}\n"
        "\\end{document}\n", encoding="utf-8")


def read_sxd(path):
    """(environment, ordinal) -> starting page, from songs.sty's raw index."""
    starts = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        m = SXD_LINK_RE.match(line.strip())
        if m and i and lines[i - 1].strip().isdigit():
            starts[int(m.group(1)), int(m.group(2))] = int(lines[i - 1].strip())
    return starts


def read_wraps(path):
    """Ordinal -> [(part, line)] for every song line the probe had to break.

    A chorus (or a numbered-part type like the pre-chorus) is replayed at each
    \\insertchorus and re-read from its own stored source, so it reports its
    lines once per printing and numbers them from the start of the part;
    identical records are therefore one broken line."""
    if not path.exists():
        raise RuntimeError("the probe wrote no line report; see PROBE_PREAMBLE")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "ok":
        raise RuntimeError("the probe could not patch songs.sty's \\SB@par, so no "
                           "line ever got checked for width; see PROBE_PREAMBLE")
    out = {}
    for line in lines[1:]:
        fields = line.split()
        if len(fields) == 3 and fields[0].isdigit() and fields[2].isdigit():
            out.setdefault(int(fields[0]), set()).add((fields[1], int(fields[2])))
    return {ordinal: sorted(found) for ordinal, found in out.items()}


def nonempty_pages(pdf):
    """Which 1-based pages carry any text. \\pagestyle{empty} means a page the
    between-song page break left over is genuinely empty."""
    out = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"pdftotext failed on {pdf}: {out.stderr.strip()}")
    return [bool(page.strip()) for page in out.stdout.split("\f")[:-1]]


def song_spans(files, repo_root):
    """(input name, first ordinal, ordinal after it) per file, in build order.
    A file may hold more than one \\beginsong, so the ordinals walk per file."""
    spans, ordinal = [], 1
    for f in files:
        n = max(1, parse_song(f)["n_begin"])
        spans.append((input_name(f, repo_root), ordinal, ordinal + n))
        ordinal += n
    return spans


def run_lualatex(builddir, env, args, job, verbose):
    """Run one LuaLaTeX pass and insist on a PDF; returns its path."""
    run = subprocess.run(["lualatex", "-shell-escape", "-interaction=nonstopmode"] + args,
                         cwd=builddir, env=env, capture_output=True, text=True)
    log, pdf = builddir / f"{job}.log", builddir / f"{job}.pdf"
    if not pdf.exists():
        tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:]) \
            if log.exists() else run.stdout[-2000:]
        raise RuntimeError(f"lualatex produced no PDF:\n{tail}")
    if verbose:
        for line in log.read_text(errors="replace").splitlines():
            if line.startswith("!"):
                print(f"  lualatex: {line}", file=sys.stderr)
    return pdf


def build_env(repo_root, builddir, extra=None):
    """A build directory that shares the repo's LilyPond cache and images, and
    the environment to typeset in it. Sharing tmp-ly is what makes a re-measure
    cost no lilypond runs -- it is the cache the project builds fill, under the
    build/ directory they write to."""
    cache = repo_root / "build" / "tmp-ly"
    cache.mkdir(parents=True, exist_ok=True)
    (builddir / "tmp-ly").symlink_to(cache)
    if (repo_root / "img").is_dir():
        (builddir / "img").symlink_to(repo_root / "img")
    env = dict(os.environ)
    env["TEXINPUTS"] = os.pathsep.join(
        [".", *(str(p) for p in extra or []), str(repo_root / "zubuvzpevnik"),
         str(repo_root / "songs" / "chords"),
         str(repo_root / "songs" / "tinwhistle"), env.get("TEXINPUTS", "")])
    env["max_print_line"] = "120"
    return env


def measure(repo_root, paper, files, keep=False, verbose=False):
    """Typeset every song on `paper`; return {input name: pages it occupies} and
    {input name: the lines that had to be broken to fit the column}."""
    spans = song_spans(files, repo_root)
    if any(name is None for name, _, _ in spans):
        raise RuntimeError("--measure only handles songs under songs/chords or songs/tinwhistle")

    builddir = Path(tempfile.mkdtemp(prefix="checkpaper-"))
    try:
        env = build_env(repo_root, builddir)
        write_probe(builddir, paper, [name for name, _, _ in spans])
        print(f"Typesetting {len(spans)} songs on {paper}...", file=sys.stderr)
        pdf = run_lualatex(builddir, env, ["paperprobe.tex"], "paperprobe", verbose)

        starts = read_sxd(builddir / "obsah.sxd")
        filled = nonempty_pages(pdf)
        broken = read_wraps(builddir / "paperprobe.wrap")

        pages, wraps, total = {}, {}, len(filled)
        for i, (name, first, nxt) in enumerate(spans):
            if (1, first) not in starts:
                continue                      # song never reached the PDF
            start = starts[1, first]          # the probe opens one songs environment
            end = starts.get((1, nxt), total + 1) if i + 1 < len(spans) else total + 1
            # Trailing blanks belong to the forced break, not to the song.
            pages[name] = sum(1 for p in range(start, end) if filled[p - 1])
            wraps[name] = sorted({w for o in range(first, nxt) for w in broken.get(o, ())})
        return pages, wraps
    finally:
        if keep:
            print(f"Probe kept in {builddir}", file=sys.stderr)
        else:
            shutil.rmtree(builddir, ignore_errors=True)


def page_offset(pagemap):
    """Sheet number minus printed page number, over the last run of pages the
    counter numbered without restarting -- the run every song is in. The books
    with a cover restart at 1 for the first song, so the printed number on its
    own does not say which side of a sheet the song is on."""
    i = len(pagemap) - 1
    while i > 0 and pagemap[i - 1] == pagemap[i] - 1:
        i -= 1
    return i + 1 - pagemap[i]


def build_project(repo_root, tex, keep=False, verbose=False):
    """Typeset one project as its own build.sh does, and read the book back as
    ({(songs environment, ordinal): page the song starts on}, sheet offset,
    sheets shipped).

    One pass, with no index files to read, so the indexes come out empty. That
    moves no song: the hardback puts its indexes last, and the camp booklet
    holds its front matter to the two pages the class checks for itself."""
    builddir = Path(tempfile.mkdtemp(prefix="checkpaper-"))
    try:
        env = build_env(repo_root, builddir, extra=[tex.parent])
        job = tex.stem
        print(f"Typesetting {os.path.relpath(tex, repo_root)}...", file=sys.stderr)
        run_lualatex(builddir, env,
                     [f"--jobname={job}", PROJECT_PREAMBLE + f"\\input{{{tex}}}"],
                     job, verbose)

        sheets = builddir / f"{job}.pagemap"
        pagemap = [int(n) for n in sheets.read_text().split() if n.isdigit()] \
            if sheets.exists() else []
        if not pagemap:
            raise RuntimeError(f"{job} recorded no sheet, so nothing says which "
                               "page a song is on; see PROJECT_PREAMBLE")
        starts = {}
        for sxd in sorted(builddir.glob("*.sxd")):
            starts.update(read_sxd(sxd))
        return starts, page_offset(pagemap), len(pagemap)
    finally:
        if keep:
            print(f"Build kept in {builddir}", file=sys.stderr)
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


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def wrap_note(broken, limit=3):
    """Where the lines that had to be broken are. A chorus or a starred part type
    (prechorus) is read back from its own stored source, so its lines count
    from the start of it."""
    names = {"r": "chorus line", "v": "line"}
    where = [f"{names.get(part, part + ' line')} {n}" for part, n in broken[:limit]]
    if len(broken) > limit:
        where.append(f"and {len(broken) - limit} more")
    return ", ".join(where)


def measured_as(n, broken):
    """What the measurement found, as the report puts it."""
    if not broken:
        return plural(n, "page")
    return f"{plural(n, 'page')}, {plural(len(broken), 'line')} too wide: {wrap_note(broken)}"


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
    by_name = by_input_name(parsed, repo_root)
    print("\nProjects:")
    unchecked = 0
    for tex, _, paper, groups in project_files(repo_root):
        rel = os.path.relpath(tex, repo_root)
        songs = [s for group in groups for s in group]
        if paper is None:
            print(f"  {rel}: unknown class, skipped")
            continue
        missing = [s for s in songs
                   if s in by_name and not claim(declared(by_name[s]), paper)]
        unknown = [s for s in songs if s not in by_name]
        note = f"{len(songs)} songs, {len(songs) - len(missing) - len(unknown)} marked {paper}"
        print(f"  {rel} [{paper}]: {note}")
        for s in missing:
            print(f"      ⚠ {s} is not marked as fitting {paper}")
        for s in unknown:
            print(f"      ⚠ {s} was not scanned")
        unchecked += len(missing)
    return unchecked


def report_measured(parsed, repo_root, paper, pages, wraps, write):
    """Measured room against the flags. A song fits a paper when it takes one
    page of it, or two facing ones, and no line of it had to be broken.

    The spread mark is only ever *offered*: a song measuring two pages may be
    one meant to open across a spread, or one nobody has tightened onto a page
    yet, and only a person knows which. So --write records `paper` or nothing,
    and pap={<paper>x2} stays something a human writes."""
    print(f"\nMeasured on {paper} ({PAPER_CLASS[paper]}):")
    changes, offers, missing = [], [], []
    for f, info in sorted(parsed, key=lambda r: str(r[0])):
        name = input_name(f, repo_root)
        if pages.get(name) is None:
            missing.append((f, info))
            continue
        n, broken = pages[name], wraps.get(name, [])
        claimed, found = claim(declared(info), paper), fits(paper, n, broken)
        if claimed == found:
            continue
        if found == 2 and claimed == 0:
            offers.append((f, info, n, broken))
        else:
            changes.append((f, info, claimed, found, n, broken))

    add = [c for c in changes if c[2] == 0]
    drop = [c for c in changes if c[3] != 1]
    tighter = [c for c in changes if c[2] == 2 and c[3] == 1]
    for label, rows, sign in (
            (f"Fits one {paper} page but is not marked for it", add, "+"),
            (f"Marked for {paper} but no longer fits it", drop, "-"),
            (f"Marked for two {paper} pages but now fits one", tighter, "~")):
        if not rows:
            continue
        print(f"\n  {label} ({len(rows)}):")
        for f, _, claimed, found, n, broken in rows:
            # The right-hand side is what --write would leave behind, so a song
            # that turns out to need a spread reads as one losing its mark.
            was, now = entry(paper, claimed) or "-", paper if found == 1 else "-"
            spread = f"; pap={{{paper}{SPREAD_SUFFIX}}} by hand if the spread is meant"
            print(f"    {sign} {os.path.relpath(f, repo_root)}  {was} -> {now}  "
                  f"({measured_as(n, broken)}){spread if found == 2 else ''}")
    if offers:
        print(f"\n  Fits two facing {paper} pages but is marked for neither ({len(offers)}), "
              "and left alone:")
        print(f"    write pap={{{paper}{SPREAD_SUFFIX}}} in the ones meant to open across a "
              "spread. No measurement")
        print("    can tell those from songs nobody has tightened onto one page yet.")
        for f, _, n, broken in offers:
            print(f"      {os.path.relpath(f, repo_root)}  ({measured_as(n, broken)})")
    if missing:
        print(f"\n  Not measured ({len(missing)}): " +
              ", ".join(os.path.relpath(f, repo_root) for f, _ in missing))

    room = [fits(paper, n, wraps.get(name)) for name, n in pages.items()]
    wide = sum(1 for name in pages if wraps.get(name))
    spread_note = (f" and {room.count(2)} fit two facing ones"
                   if paper in SPREAD_PAPERS else "")
    print(f"\n{'=' * 60}")
    print(f"{room.count(1)}/{len(pages)} songs fit one {paper} page{spread_note}; "
          f"{len(add)} to add, {len(drop)} to remove, {len(tighter)} to tighten"
          + (f", {len(offers)} to look at by hand." if offers else "."))
    if wide:
        print(f"{plural(wide, 'song')} have a line too wide for {paper}, which is "
              "what stops them fitting it.")

    if write:
        for f, info, _, found, _, _ in changes:
            others = [p for p in declared(info) if p not in (paper, paper + SPREAD_SUFFIX)]
            set_pap(f, sorted(others + ([paper] if found == 1 else [])))
        print(f"Wrote the pap key in {len(changes)} file(s).")
    return len(changes)


def report_layout(parsed, repo_root, measured, keep=False, verbose=False):
    """Build each project and check the pages its songs really landed on.

    Two things somebody playing from the book notices and a page count does not:
    a song on two pages that a page turn falls between, and a blank page left
    in the middle of the book to keep one from doing so."""
    by_name = by_input_name(parsed, repo_root)
    print("\nBook layout:")
    problems = 0
    for tex, cls, paper, groups in project_files(repo_root):
        rel = os.path.relpath(tex, repo_root)
        if paper is None:
            print(f"  {rel}: unknown class, skipped")
            continue
        pages = measured[paper][0]
        starts, offset, sheets = build_project(repo_root, tex, keep, verbose)
        spread = cls in SPREAD_CLASSES

        # The keys songs.sty hands out, in the order the project inputs them.
        order = []
        for env, group in enumerate(groups, 1):
            ordinal = 1
            for name in group:
                order.append((name, (env, ordinal)))
                ordinal += max(1, by_name[name]["n_begin"]) if name in by_name else 1

        notes, used, on_spread, longer = [], [], 0, 0
        for i, (name, key) in enumerate(order):
            start, n = starts.get(key), pages.get(name)
            if start is None or n is None:
                notes.append(f"· {name} was not measured, so its pages are unknown")
                continue
            used += [start, start + n - 1]
            # Where the next song of the same environment begins; anything
            # between two environments is a section page, not a song's doing.
            after = order[i + 1] if i + 1 < len(order) else None
            nxt = starts.get(after[1]) if after and after[1][0] == key[0] else None
            nxt = start + n if nxt is None else nxt
            if n == 2:
                on_spread += 1
                if not spread:
                    notes.append(f"· {name} takes 2 pages, and this book is not "
                                 "two-sided, so it cannot lay them side by side")
                elif (start + offset) % 2:
                    notes.append(f"⚠ {name} takes pages {start} and {start + 1}, "
                                 "which a page turn falls between")
                    problems += 1
            elif n > 2:
                longer += 1
                notes.append(f"· {name} takes {n} pages, so no ordering of the "
                             "book can spare it a page turn")
            if nxt < start + n:
                notes.append(f"⚠ {name} was measured at {plural(n, 'page')} but the "
                             f"book gives it {plural(nxt - start, 'page')}")
                problems += 1
            for blank in range(start + n, nxt):
                notes.append(f"⚠ page {blank} is blank, before {after[0]}")
                problems += 1

        where = f"pages {min(used)}-{max(used)} of {sheets}" if used else "no pages"
        pair = "on a spread" if spread else "on two pages"
        counts = "".join([f", {on_spread} {pair}" if on_spread else "",
                          f", {longer} over two pages" if longer else ""])
        print(f"  {rel} [{paper}{', spreads' if spread else ''}]: "
              f"{len(order)} songs on {where}{counts}")
        for note in notes:
            print(f"      {note}")
        if not notes:
            print("      ✓ no page turn inside a song, no blank page between them")
    return problems


def main():
    ap = argparse.ArgumentParser(description="Report song paper fit.")
    ap.add_argument("paths", nargs="*", help="files/dirs to scan (default: songs/)")
    ap.add_argument("--summary", action="store_true", help="counts only, no song lists")
    ap.add_argument("--measure", metavar="PAPER", choices=sorted(PAPER_CLASS),
                    help="typeset every song on PAPER and compare with the flags")
    ap.add_argument("--layout", action="store_true",
                    help="build every project and check where its songs landed")
    ap.add_argument("--write", action="store_true",
                    help="with --measure: write the measured result into the songs")
    ap.add_argument("--keep", action="store_true", help="keep the probe builds")
    ap.add_argument("-v", "--verbose", action="store_true", help="show lualatex errors")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any disagreement")
    args = ap.parse_args()

    if args.write and not args.measure:
        ap.error("--write only makes sense with --measure")
    if args.layout and args.paths:
        ap.error("--layout measures whole books, so it takes no paths")

    repo_root = Path(__file__).resolve().parent.parent
    scan = args.paths if args.paths else [repo_root / "songs"]
    # Resolved, so input_name() works whether the caller typed a relative path.
    files = [f.resolve() for f in collect_song_files(scan)]
    if not files:
        print("No .tex song files found.", file=sys.stderr)
        return 2
    parsed = [(f, parse_song(f)) for f in files]

    if args.measure or args.layout:
        # A book needs the page count of every song it holds, so --layout
        # measures each paper its projects are typeset on.
        papers = {args.measure} if args.measure else set()
        if args.layout:
            papers |= {p for _, _, p, _ in project_files(repo_root) if p}
        measured = {p: measure(repo_root, p, files, keep=args.keep, verbose=args.verbose)
                    for p in sorted(papers)}
        disagreements = problems = 0
        if args.measure:
            pages, wraps = measured[args.measure]
            disagreements = report_measured(parsed, repo_root, args.measure,
                                            pages, wraps, args.write)
            if args.write:
                disagreements = 0
        if args.layout:
            problems = report_layout(parsed, repo_root, measured, args.keep, args.verbose)
        return 1 if (args.strict and (disagreements or problems)) else 0

    report_flags(parsed, repo_root, args.summary)
    unchecked = report_projects(parsed, repo_root)
    return 1 if (args.strict and unchecked) else 0


if __name__ == "__main__":
    sys.exit(main())
