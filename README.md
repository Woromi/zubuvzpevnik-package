# Zubův zpěvník

A customization of the [songs](https://songs.sourceforge.net/) LaTeX package, styled to look like my old songbook originally written in Word.

To use this package in your own LaTeX documents, make it visible to LaTeX one of two ways: run `scripts/install.sh` to copy it into your home TeX tree (`~/texmf/tex/latex/`; `scripts/uninstall.sh` removes it again), or add this directory to `TEXINPUTS` without copying — the approach this repo's build scripts use. It locates its own LilyPond includes either way.

## zubuvzpevnik.sty

The core package, built on top of `songs`. It provides:

- Custom verse, chorus, and instrumental song parts (defined in `songpart/`), plus multi-voice support
- Song metadata keys: `by`, `lang`, `key`, `tun` (tuning), `tem` (tempo), `ori` (original), `chr` (chord diagrams), `src` (source URL)
- Two indexes: `obsah` (by title) and `obsahAutor` (by author)
- Language filtering via `\includelangs{...}` / `\excludelangs{...}` — songs with a non-matching `lang` key are dropped from the output
- Language-aware chord names: Czech songs use H/B notation, others the English B/Bb
- `\capo{n}` that either prints a *Capo n* note or transposes the chords (with `transcapos`)
- LilyPond sheet music embedding via `lyluatex`
- Fonts: Open Sans for text, Roboto Mono for lyrics and chords

## velkyzpevnik.cls

Class for the big A4 songbook, based on `article` and using `zubuvzpevnik`. Defines the title page (with a cover image), a two-column table of contents from both indexes, and a layout where song metadata (key, tuning, tempo, …) is shown in a box next to the song title.

## taborovyzpevnik.cls

Class for the small A5 camp songbook, based on `book` and using `zubuvzpevnik`. Defines the front cover, table of contents on the inside front cover, page numbering, and a back cover with a chord overview and credits. The year on the covers comes from `\campyear`, which defaults to the year of the build — each camp project pins it (`\renewcommand{\campyear}{2025}`) so that old songbooks can be rebuilt unchanged. A hand-made cover PDF can be used instead of the generated title page by passing it as `\makefrontcover[cover.pdf]` (the 2025 songbook had one, with a tengwar title). `\padbookletpages` fills the document with blank pages to a multiple of 4 so that `scripts/makebooklet.sh` can reorder it into a printable booklet. The cover uses the SKAUT Bold and TheMix C5 fonts.

## songpart/

Song part definitions imported by `zubuvzpevnik.sty`: `sloka.cfg` (verse), `refren.cfg` (chorus styled as a verse prefixed with *R:*), `instrumental.cfg` (chords-only part with fixed-width chords), `index.cfg` (indexing titles with authors), and `voices.cfg` (multi-voice support).

## lilypond/

Shared LilyPond includes (`zubuvzpevnik.ily`, `tinwhistle.ily`) for songs with embedded sheet music. `zubuvzpevnik.sty` adds this directory to lyluatex's include path (locating it via kpse), so song fragments can `\include "zubuvzpevnik.ily"` by bare name — no copying required.
