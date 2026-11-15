# zubuvzpevnik-package

The LaTeX package behind Zubův zpěvník (on the `songs` package, built with
LuaLaTeX): `zubuvzpevnik.sty`, the classes (`velkyzpevnik` A4, `malyzpevnik` A5
hardback, `taborovyzpevnik` A5 camp), `songpart/*.cfg`, `feature/*.cfg`,
`lua/*.lua`, the LilyPond includes, the build helpers and the `check*.py` tools
(`scripts/`, shared parser `songfile.py`). The songs and the books are the
[ZubuvZpevnik](https://github.com/Woromi/ZubuvZpevnik) repository, which has this
one as the submodule `zubuvzpevnik/`; the Zpěvníkář app bundles its own copy.
Read the docs before changing anything non-trivial — they hold the rationale
that the code comments deliberately omit:

- `README.md` — the song-writing syntax (user-facing macros)
- `docs/internals.md` — how the package works
- `docs/building.md` — prerequisites, build scripts, CI, releasing
- `docs/tools.md` — the `scripts/check*.py` tools

## Verifying a change

Changes should be rendering-neutral unless intended. Compare before/after by
building a book of the songbook twice and diffing `pdftotext -layout` output:

- A book's `build.sh` puts its own `zubuvzpevnik/` first on `TEXINPUTS`, so the
  "before" side is a copy of the songbook whose `zubuvzpevnik/` holds the old
  package — a **full copy**, not just the changed file: `\zub@loadlua` loads
  `lua/*.lua` next to whichever `zubuvzpevnik.sty` kpathsea finds.
- A scratch document compiled with `lualatex` directly can instead take a full
  copy of the package first on `TEXINPUTS`.
- Prefer this over `git stash` (the working trees usually have unrelated edits).
- For a new feature, also compile a small scratch song that exercises it.

No absolute paths in tracked files: the scripts find the songbook above the
package or take `--songbook DIR`.

## Conventions

- Comments are one line and point at `docs/`; put explanations in the docs.
- Commented-out lines in `.tex` files and scripts are intentional usage
  reminders — don't remove them.
- When adding or changing a user-facing macro, update `README.md` and, if the
  mechanism is non-obvious, `docs/internals.md`.
- The cover fonts are licensed for Junák use only — never commit them
  (see `docs/building.md#cover-fonts`).

## Companion website

[ZubuvZpevnikWeb](https://github.com/Woromi/ZubuvZpevnikWeb) parses the song
`.tex` files itself. A change to macro syntax or semantics (e.g. new arguments
to `\insertchorus`) needs a matching change in its `zpevnikweb/` parser and tests
(`python3 -m unittest discover -s tests`); its `tools/checkchords.py` compares
the site's chords with the PDF's.
