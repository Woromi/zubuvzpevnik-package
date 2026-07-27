# Building and releasing

## Prerequisites

```bash
sudo apt-get install texlive-luatex texlive-latex-base texlive-latex-recommended \
    texlive-latex-extra texlive-plain-generic texlive-music texlive-fonts-extra \
    texlive-font-utils texlive-extra-utils texlive-lang-czechslovak lilypond \
    fonts-open-sans fonts-freefont-otf unifont poppler-utils
```

| Package | Provides |
|---|---|
| `texlive-music` | the `songs` and `lyluatex` packages |
| `texlive-fonts-extra` | Roboto Mono, Alegreya Sans |
| `texlive-font-utils` | `epstopdf`, which converts engraved scores for embedding |
| `texlive-extra-utils` | `pdfbook2`, which imposes the camp A5 booklet |
| `poppler-utils` | `pdfinfo`, used to check the booklet page count |
| `lilypond` | engraves the embedded sheet music |

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
projects/velkyzpevnik/build.sh       # Main A4 songbook → velkyzpevnik.pdf
projects/tabory/2026/build.sh        # A5 camp songbook → tabor2026.pdf + tabor2026Booklet.pdf
projects/tinwhistle/build.sh         # Tin whistle sheet music → tinwhistle.pdf
projects/interpreti/ayreon/build.sh  # Single-artist songbook → ayreon.pdf
```

Each sets `TEXINPUTS` to reach the package, the shared song database and its own
directory, then hands off to `scripts/build.sh` with the project's index names.
Output lands in the current working directory.

Options, passed through to `scripts/build.sh`:

| Option | Effect |
|---|---|
| `-v` | verbose output |
| `-i indexname` | build a specific index (repeat for several) |
| `-l lang[,…]` | include only songs with those languages |
| `-e lang[,…]` | exclude songs with those languages |
| `-o output` | output PDF name, without extension |
| `-c` | remove build files afterwards |

`-l` and `-e` cannot be combined. A song with no `lang` key is kept by `-e` and
dropped by `-l`; see
[`zubuvzpevnik/README.md`](../zubuvzpevnik/README.md#language-and-filtering).
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

No install step is needed: the package is found through `TEXINPUTS` and locates
its own LilyPond includes via kpse.

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
| `scripts/cleanup.sh` | remove LaTeX build files across the repo (skips `.git`; keeps `.sbx`, which the next first pass wants) |
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
green is a gate you learn to ignore. The warnings and the 7 deliberate orphans
still print in the log. `checkkeys.py --validate` runs alongside it purely for
the record, with `|| true`: the detector is a heuristic and is not always
right, so a drop from the current 97 % should be visible without failing a
build.

**`build`** rebuilds the songbooks from scratch, so a broken song file or a
missing prerequisite is caught immediately rather than at the next release. The
apt list lives in `.github/actions/setup-build-env/action.yml` and mirrors the
one above, so CI also verifies that the documented list stays sufficient.

Engraved scores are cached: `lyluatex` keys `tmp-ly/` by content, so restoring
the cache skips re-engraving unchanged LilyPond sources. The cache is never
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

Pushing a version tag builds velkyzpevnik and publishes it as a GitHub release,
which keeps the README's `releases/latest/download/…` link serving a fresh PDF:

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
