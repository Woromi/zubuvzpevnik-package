# Building and releasing

> **Where this lives.** The package, these scripts and docs are the [zubuvzpevnik-package](https://github.com/Woromi/zubuvzpevnik-package) repository. A songbook checkout (ZubuvZpevnik) has it as a submodule at `zubuvzpevnik/`, so from the songbook the commands below are `zubuvzpevnik/scripts/<tool>`; the tools find the songbook above the package, or take `--songbook DIR`.

## Prerequisites

```bash
sudo apt-get install texlive-luatex texlive-latex-base texlive-latex-recommended \
    texlive-latex-extra texlive-plain-generic texlive-music texlive-fonts-extra \
    texlive-font-utils texlive-extra-utils texlive-lang-czechslovak lilypond \
    fonts-open-sans fonts-freefont-otf fonts-noto-cjk unifont poppler-utils mupdf-tools
```

| Package | Provides |
|---|---|
| `texlive-music` | the `songs` and `lyluatex` packages |
| `texlive-fonts-extra` | Roboto Mono, Alegreya Sans |
| `texlive-font-utils` | `epstopdf`, which converts engraved scores for embedding |
| `texlive-extra-utils` | `pdfbook2`, which imposes the camp A5 booklet |
| `poppler-utils` | `pdfinfo`, used to check the booklet page count |
| `mupdf-tools` | `mutool`, which repairs the A5 book's print file: `pdfunite` leaves its merge with a broken cross-reference table that viewers fix silently but a printer may not |
| `lilypond` | engraves the embedded sheet music |
| `fonts-noto-cjk` | Noto Sans CJK JP, the fallback for kana and kanji (a Japanese band name); without it they are left out with a warning |

If the list ever drifts out of date, `texlive-full` instead of the `texlive-*`
packages always works.

Index sorting wants a Czech locale (`sudo locale-gen cs_CZ.UTF-8`); without one
the build warns and falls back to the system default.

### Cover fonts

The camp songbook cover is set in SKAUT Bold and TheMix C5, from the
[official scouting visual style](https://krizovatka.skaut.cz/komunikace-a-propagace/skautsky-vizualni-styl/zakladni-prvky-jednotneho-vizualniho-stylu).
They are licensed for Junák use only, so they are **never committed and never
cached** — the only copy is the one you install yourself, and the one a tagged
camp release downloads into a throwaway CI runner.

They are therefore optional. `taborovyzpevnik.cls` asks for each with
`\IfFontExistsTF` and falls back to the text font with a `\ClassWarning`, so
the camp songbook builds for anyone; only the licensed typography is missing.
The cover title sits in a fixed-height box (`\ZUB@covertitleheight`) so that
substitution cannot change the page count: *Zpěvník* has a 17 pt descender in
Open Sans against 1 pt in SKAUT Bold, and those few points were enough to spill
the front matter onto a third page and break the
[booklet paging](internals.md#why-the-page-count-must-be-a-multiple-of-4).

## Building a songbook

Each project has its own script:

```bash
projects/velkyzpevnik/build.sh       # Main A4 songbook → build/velkyzpevnik.pdf
projects/malyzpevnik/build.sh        # A5 hardback songbook → build/malyzpevnik.pdf + build/malyzpevnikBook.pdf
projects/tabory/2026/build.sh        # A5 camp songbook → build/tabor2026.pdf + build/tabor2026Booklet.pdf
projects/tinwhistle/build.sh         # Tin whistle sheet music → build/tinwhistle.pdf
projects/interpreti/ayreon/build.sh  # Single-artist songbook → build/ayreon.pdf
```

Each sets `TEXINPUTS` to reach the package, the shared song database and its own
directory, then changes into `build/` and hands off to `scripts/build.sh` with
the project's index names. `build/` is the only place a build writes, and it is
not in version control.

`scripts/build.sh` itself writes to the *working* directory, so building
somewhere else — to compare two PDFs without disturbing `build/`, say — is one
`cd` away; you then want `build/tmp-ly` linked in, or the scores are engraved
again from scratch. The repository root is on `TEXINPUTS` so that
`\graphicspath{{img/}}`, which resolves against the working directory, still
finds the cover images from wherever the build runs.

The camp years share one script: `projects/tabory/<year>/build.sh` is a two-line
wrapper that hands its own directory to `projects/tabory/build.sh`, which derives
the job name from it (`2026` → `tabor2026`) and runs the booklet imposition. A
new camp needs the wrapper copied and nothing else.

Options, passed through to `scripts/build.sh`:

| Option | Effect |
|---|---|
| `-v` | print the whole LuaLaTeX log instead of the filtered warnings |
| `-i indexname` | build a specific index (repeat for several) |
| `-l lang[,…]` | include only songs with those languages |
| `-e lang[,…]` | exclude songs with those languages |
| `-o output` | output PDF name, without extension |
| `-c` | remove the build files afterwards, in the output directory and beside the `.tex` |
| `-s sheets` | *malyzpevnik only* — target sheets per signature (default 5) |

`-l` and `-e` cannot be combined. A song with no `lang` key is kept by `-e` and
dropped by `-l`; see
[`README.md`](../README.md#language-and-filtering).
Example — a Czech/Slovak-only variant:

```bash
projects/velkyzpevnik/build.sh -l czech,slovak -o velkyzpevnikCz
```

### How the build works

1. **First LuaLaTeX pass.** `-shell-escape` is required so `lyluatex` can call
   `lilypond`. Language filters are injected as TeX code prepended to the
   `\input` of the document, which is why they arrive as `\ZUB@includelangs`
   before the package's `\providecommand` default.
2. **Index build.** `scripts/buildindex.sh` runs `songidx.lua` under `texlua`
   once per index, turning each `.sxd` into a `.sbx`. Czech collation decides
   the order, including the "Ch" block; the locale name is spelled differently
   on different systems (`cs_CZ.utf8` on glibc, `cs_CZ.UTF-8` on macOS/BSD), so
   the script picks the first spelling the machine actually has. `build.sh`
   warns about a missing locale up front, before the long first pass.
3. **Second LuaLaTeX pass**, which typesets the finished indexes. It is
   deliberately quiet even with `-v`: its errors would only repeat the first
   pass. It runs only when `-i` was given.

Two passes converge because both classes restart page numbering after the front
matter, so the index's own length never shifts the song page numbers it records.

#### What the build prints

A LuaLaTeX pass over the songbook is about 2 000 lines of log, of which a
handful matter, so the default build prints the steps and then only those:

```
Building songbook: tabor2025...
Building index: obsah...
Building index: obsahAutor...
Rebuilding songbook with the indexes...
  Package zubuvzpevnik Warning: Song 'Gandalfovy obchodní úspěchy' is not marked as fitting a5 paper; ...
  (28 routine font notice(s) hidden; -v shows the whole log)
Finished: tabor2025.pdf (36 pages)
```

Two of those warnings are the ones worth watching for: a song not marked for the
paper being typeset, and a two-page song that had to move to the next spread and
left a blank page behind it (see
[internals.md](internals.md#the-blank-page-before-a-spread-song)).

Surfaced: `!` errors, `LaTeX`/`Package`/`Class`/`Module` warnings, and
`Missing character` lines — the last deduplicated with a count, because those
are exactly the characters LuaLaTeX drops from the PDF without failing
([tools.md](tools.md#checksongspy--metadata)).

Counted rather than printed: `LaTeX Font Warning`, which is Roboto Mono having
no small-caps or slanted shapes and appears 28 times on every build.

The filter reads the `.log` rather than LuaLaTeX's stdout, because the log is
where a warning is a block ending at a blank line. Those blocks are wrapped
mid-word at `max_print_line` (see below), so they are glued back into one line
before printing — which is why the filter and that variable are linked.

The same filter runs when a pass fails, ahead of the log tail: with
`-halt-on-error` the end of the log is the geometry dump LaTeX prints while
dying, not the error, so the tail alone is no help. It is only used as a
fallback, when nothing matched.

`-v` replaces all of this with the raw pass.

#### Index blocks

`songidx.lua` is not told the alphabet. It recovers the index sections by
walking the first character of each sorted title and starting a new block
whenever the locale collates one after the last, which means **a section can
only exist where the sort produces a contiguous run of titles**. Two rules
follow from that, and both are decided by the locale rather than by a table, so
a build under a different one gets that locale's alphabet:

- **Accents.** Czech collation interleaves `Á Ď É Ě Í Ň Ó Ť Ú Ů Ý` with their
  base letter — `Ábel, Anna, ďábel, dálka, dech` — so they cannot have sections
  of their own, however much they are letters when reciting the alphabet. A `Ď`
  section would start at "ďábel" and swallow every later D title. `Č Ch Ř Š Ž`
  *do* get runs (`cesta, cyklus, čas, chvála`) and so do get sections.
  `blockchar` folds each start character onto whichever it is: `strcoll` is a
  total order and never reports an accent as equal, so it is probed instead —
  an accent sorts below any following letter, putting "Ú" before "UZ" where the
  distinct letter "Š" does not come before "SZ".
- **Numbers.** A leading number is a section of its own, so "21 Guns" heads a
  `21` section and a book can end up with `2`, `7`, `21`, `100`. `songcmp`
  sorts those titles before the words and by value, and the locale agrees with
  neither — it files digits after `Ž`, and orders "1000" ahead of "21" — so
  `startcharlt` orders numeric sections by value to match the sort. The label
  goes through `tonumber`, which normalizes it and so keeps "007 James" in the
  same section as "7 dní".

Leading punctuation needs no rule: both the sort and the block scan skip to the
first alphanumeric, so "!Divný" files under D. A title with no alphanumeric at
all sorts first, into a `#` section. When the two orderings do disagree the
block scan silently swallows the rest of the index into one section — the
symptom is an index that is one giant block — so it now warns on stderr
instead, visible with `-v`.

Each project script resolves the repository root once into `REPO_ROOT` instead
of hanging `../../` off `SCRIPT_DIR`, so the paths TeX prints for every song it
opens are 28 characters shorter.

`build.sh` exports `max_print_line=120` before calling LuaLaTeX. TeX starts a
new line before a file name only when the name would not fit in what is left of
the current one, so the value decides the shape of the build output: at the
default 79 nothing ever fits, giving one song per line but splitting every path
mid-word, while a large value lets several songs share a line. 120 sits between
the longest song path (94 characters) and the point where a second song starts
fitting beside one (about 150), so every song gets its own unbroken line. The
two numbers are linked — shortening the paths again means re-checking this one.
`error_line`/`half_error_line` are raised alongside it so the error context line
is shown whole instead of being elided with `...`.

No install step is needed: the package is found through `TEXINPUTS` and locates
its own LilyPond includes via kpse.

#### What a build leaves behind

Everything a build writes lands in its **working directory**, which for the
project scripts is `build/`: the PDF, the LaTeX scratch files (`.aux`, `.log`,
`.sxc`), the `.sxd`/`.sbx` index pair, and `tmp-ly/` — lyluatex's engraving
cache, which it puts in the working directory rather than next to the package.
Nothing is written anywhere else in the tree, which is what makes `/build/` a
sufficient `.gitignore` entry and `rm -rf build` a complete clean.

`scripts/cleanup.sh` removes the scratch files and keeps both the `.sbx`, which
the next first pass reads, and `tmp-ly`. `-c` hands it the working directory and
the directory the `.tex` came from, one level deep and no further. The second of
those is not where a build writes: it collects what latexindent and an
editor-run build leave beside the document, which would otherwise sit there
until someone swept the tree. Run `cleanup.sh` with no argument for that sweep —
the recursive form, which also reaches the strays left next to a song.

One thing sits outside all of this: LilyPond 2.24 leaves its intermediate
PostScript in `$TMPDIR` as `lilypond-tmp-<n>`, roughly 1 MB per engraved score,
and never removes it. Nothing here deletes those — the names say nothing about
which build owns them, so a sweep would race a concurrent one — but that is
where a surprising amount of `/tmp` goes after a few cold builds.

### Booklet imposition

Camp builds additionally run `scripts/makebooklet.sh`, which calls `pdfbook2`
with `--short-edge` (uniform page orientation — do not reintroduce alternating
180° rotation) and `--no-crop` (keep the A5 margins), then renames the result to
`<jobname>Booklet.pdf`.

It first refuses any PDF whose page count is not a multiple of 4, because
`pdfbook2` pads short input at the *end* and would bury the back cover on an
inner sheet face. The page arithmetic that guarantees the multiple, and the
class-side warning that diagnoses a break, are in
[internals.md](internals.md#why-the-page-count-must-be-a-multiple-of-4).

### Other scripts

| Script | Purpose |
|---|---|
| `scripts/makebook.sh` | cut a bound book into signatures and impose each as a booklet (`malyzpevnik`) |
| `scripts/cleanup.sh` | remove LaTeX build files — the whole repo, or just the directories named, one level deep ([what a build leaves behind](#what-a-build-leaves-behind)) |
| `scripts/install.sh` | copy the package into `~/texmf/tex/latex` for use outside this repo |
| `scripts/uninstall.sh` | remove it again |

`songidx.lua` is vendored in `scripts/` out of necessity — it is not packaged
separately.

### Editing song files

`latexindent.yaml` in the repo root configures `latexindent` for song sources:
`\[...]` is a chord rather than display math, so latexindent's `\[ \]` handler
is switched off, and the `\beginX … \endX` song parts are declared as indentable
blocks — the pattern excludes real `\begin{...}` environments and
`\beginsong`/`\endsong`, so part content sits at one indent level rather than
two. Indentation is 4 spaces, matching the existing song metadata, rather than
latexindent's default tab. Formatting a song this way is rendering-neutral.

```bash
latexindent -l latexindent.yaml songs/chords/Artist/Song.tex
```

In VS Code / VSCodium with LaTeX Workshop, point the formatter at it:

```json
"latex-workshop.formatting.latexindent.args": [
    "-c", "%DIR%/", "-l=%WORKSPACE_FOLDER%/latexindent.yaml", "%TMPFILE%"
]
```

That is what the committed `.vscode/settings.json` uses, so it works in any
clone. (`latex-workshop.formatting.latexindent.args` is the current setting
name; the bare `latex-workshop.latexindent.args` is deprecated.)

`%WORKSPACE_FOLDER%` is the *first* workspace folder, and empty when a file is
opened without one — then the `-l` path does not resolve and latexindent
silently falls back to its own defaults, exit code 0 and all. The result is
tabs and no song-part indentation; content, chords included, is untouched. So
the worst case is cosmetic, but open the repo as a folder to get the intended
formatting.

## Continuous integration

`.github/workflows/build.yml` runs on every push and pull request, with two
independent jobs.

**`lint`** runs the two song linters. It needs no TeX, so it answers in seconds
beside the builds. `checksongs.py` is the gate, deliberately **without**
`--strict`: it fails on errors only — a missing `by`, an unbalanced
`\beginsong`/`\endsong`, a character LuaLaTeX would silently drop from the PDF
— and leaves the recommended-metadata warnings as warnings. Several of those
are unfixable in principle (a tempo nobody knows), and a gate that can never go
green is a gate you learn to ignore. The warnings and the deliberate orphans
still print in the log. `checkkeys.py --validate` runs alongside it purely for
the record, with `|| true`: the detector is a heuristic and is not always
right, so a drop in the agreement it reports should be visible without failing
a build.

**`build`** rebuilds the songbooks from scratch, so a broken song file or a
missing prerequisite is caught immediately rather than at the next release. The
apt list lives in `.github/actions/setup-build-env/action.yml` and mirrors the
one above, so CI also verifies that the documented list stays sufficient.

`malyzpevnik` earns its place in that matrix twice over: `makebook.sh` and
`\insertusedchords` are exercised by no other build. Only its pages are
uploaded, though — the imposed `malyzpevnikBook.pdf` is 7 MB against the 500 MB
artifact quota, and what tests the imposition is building it, not keeping it.
The release workflow publishes both.

Engraved scores are cached: `lyluatex` keys `build/tmp-ly/` by content, so
restoring the cache skips re-engraving unchanged LilyPond sources. The cache is never
pruned, so it grows over time.

The camp entries deliberately do **not** set `fonts: true`, so ordinary pushes
never touch the font links at all: the camp books build with the fallback cover,
which still exercises the class, `\padbookletpages` and the booklet imposition.
A tag is the only thing that fetches them — `release-camp.yml` passes
`cover-fonts: true`, and the setup action then verifies with `fc-list` that what
arrived really is a font, since a failed Drive download yields an HTML page. So
a published release still cannot go out with the wrong cover, while a Drive
hiccup can no longer red CI for an unrelated change. The trade-off is that a
broken link stays unnoticed until you tag.

Note that `-shell-escape` means a pull request from a fork executes arbitrary
code in CI. The blast radius is small — the `pull_request` trigger gives a
read-only token and no secrets — but it is worth knowing it is there.

## Releasing

Pushing a version tag builds velkyzpevnik and malyzpevnik and publishes them as
a GitHub release, which keeps the README's `releases/latest/download/…` links
serving fresh PDFs. The hardback contributes two assets, the pages
(`malyzpevnik.pdf`) and the imposed signatures (`malyzpevnikBook.pdf`):

```bash
git tag v2026.06
git push origin v2026.06
```

A `tabor<year>` tag does the same for that year's camp songbook
(`.github/workflows/release-camp.yml`), publishing `tabor<year>.pdf` and
`tabor<year>Booklet.pdf`:

```bash
git tag tabor2026
git push origin tabor2026
```

That workflow marks the release as a **pre-release** on purpose:
`releases/latest` points at the most recent *full* release, so a camp release
published without the flag would hijack the velkyzpevnik download link. Keep
that in mind if you ever publish a camp songbook by hand.

Both workflows fall back from `gh release create` to `gh release upload
--clobber`, so re-running an already-released tag refreshes the assets instead
of failing.
