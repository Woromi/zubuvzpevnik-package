# Zubův zpěvník

A customization of the [songs](https://songs.sourceforge.net/) LaTeX package, styled to look like my old songbook originally written in Word.

To use this package in your own LaTeX documents, make it visible to LaTeX one of two ways: run `scripts/install.sh` to copy it into your home TeX tree (`~/texmf/tex/latex/`; `scripts/uninstall.sh` removes it again), or add this directory to `TEXINPUTS` without copying — the approach this repo's build scripts use. It locates its own LilyPond includes either way.

Everything here builds **on top of** the `songs` package — its manual still applies. This document only covers what `zubuvzpevnik` adds or changes. The package itself is thin: it loads `songs`, sets up fonts and layout, and then `\import`s the individual features (`feature/`) and song parts (`songpart/`); see [Source layout](#source-layout) for the module map.

## Contents

- [Writing a song](#writing-a-song)
- [Song metadata keys](#song-metadata-keys)
- [Song parts](#song-parts)
- [Repeating the chorus](#repeating-the-chorus)
- [Chords](#chords)
- [Language and filtering](#language-and-filtering)
- [Indexes](#indexes)
- [Large vs. small paper](#large-vs-small-paper)
- [Customization hooks](#customization-hooks)
- [LilyPond sheet music](#lilypond-sheet-music)
- [Document classes](#document-classes)
- [Package / class options](#package--class-options)
- [Source layout](#source-layout)

## Writing a song

A song is the standard `songs` `\beginsong … \endsong`, with the extra metadata keys below:

```latex
\beginsong{Song Title}[
    by={Artist Name},
    lang={english},
    key={Em},
]
\capo{2}

\beginverse
\[Em]Lyrics with chords \[G]inline,
written \[D]one line per \[H7]line.
\endverse

\beginchorus
\[C]Chorus lines \[D]here.
\endchorus

\endsong
```

Each lyric line is its own source line (the `songs` package breaks lines at the source newlines). Chords are written `\[chord]` immediately before the syllable they sit over; sharps use `#` (e.g. `\[F#m]`). Then `\input` the song from a project file inside a `\begin{songs}{obsah,obsahAutor}` environment.

## Song metadata keys

Keys go in the optional `[...]` argument of `\beginsong`. All are optional except `by`.

| Key   | Meaning |
|-------|---------|
| `by`  | Artist / author (drives the author index). *(from `songs`)* |
| `lang`| Song language — `czech`, `slovak`, `english`, … Selects hyphenation, chord naming, index sorting and `-l`/`-e` filtering. |
| `key` | Musical key. |
| `tun` | Instrument tuning. |
| `tem` | Tempo. |
| `ori` | Original song (for covers / translations). |
| `chr` | Chords used, shown above the song (e.g. `\gtab` diagrams). |
| `src` | Source URL (typeset as a link). |

`key`/`tun`/`tem`/`ori`/`chr`/`src` are defined in `feature/metadata.cfg`; `lang` in `feature/lokalizace.cfg`. On large paper they are laid out in a box beside the title (see `\makeprelude`); on small paper they are omitted.

## Song parts

Inside a song you can use these parts (all but the chorus are verse-based and share the verse look):

| Part | Command | Label shown | Notes |
|------|---------|-------------|-------|
| Verse | `\beginverse … \endverse` | the verse number | *(from `songs`)*, numbers in bold |
| Chorus | `\beginchorus … \endchorus` | `R:` | looks like a verse, just indented more |
| Bridge | `\beginbridge … \endbridge` | `*` | |
| Pre-chorus | `\beginprechorus … \endprechorus` | `P` | |
| Intro | `\beginintro … \endintro` | *(none)* | |
| Outro | `\beginoutro … \endoutro` | *(none)* | |
| Instrumental | `\begin{instrumental} … \end{instrumental}` | — | chords only, fixed-width |

**Chorus.** Rather than the `songs` package's left-hand bar, the chorus is styled like a verse with a bold `R:` in place of the verse number and a slightly larger indent. It is still the `songs` chorus underneath. See also [Repeating the chorus](#repeating-the-chorus).

**Verse-based parts and your own.** Bridge/pre-chorus/intro/outro are created with one helper, so you can add more:

```latex
% \newSongPartType{name}{label}{indent-in-em}
\newSongPartType{solo}{S}{3}   % defines \beginsolo … \endsolo, labelled "S"
```

The part renders as an (unnumbered) verse whose number slot shows `label` and whose indent is `indent × em`. An empty label prints no marker (that's how intro/outro work).

**Instrumental.** `\begin{instrumental} … \end{instrumental}` typesets chords only, each chord in a fixed-width box (so chord-only passages align). It renders only when chords are shown (`chorded`). The chord width defaults to `2em`; change it with:

```latex
\setchordwidth{2.5em}
```

**Multi-voice.** For two simultaneous voices on one line, use `\multivoice` inside the lyrics — the main text on top, the second voice in smaller gray type just below:

```latex
\[Am]{\multivoice{Main vocal line}{Second voice line}}
```

A right-aligned **role label** (e.g. for a duet or call-and-response) is `\role`, optionally with a second-voice label stacked below it:

```latex
\role{Soprano}            % just the label, flush right
\role{Soprano}{Alto}      % both, the second one grayed (only if multi-voice is on)
```

Multi-voice can be switched per document with `\multivoiceon` / `\multivoiceoff` (the A5 camp class turns it off by default — the second voice is dropped and only the main line is kept). Tunables: `\secondvoiceraise` (how far the second voice tucks up under the main line, default `2pt`), `\rolestyle`, `\secondvoicestyle`. Defined in `feature/hlasy.cfg`.

## Repeating the chorus

The captured chorus can be reprinted later without retyping it:

| Command | Result |
|---------|--------|
| `\insertchorus`  | Reprints the whole chorus (chords and line breaks intact). |
| `\insertchorus*` | A one-line reminder: the **first source line only**, with **chords off**, a **trailing comma dropped** and **`...`** appended. |

```latex
\beginchorus
\[C]Refrén první řádek,
\[G]Refrén druhý řádek
\endchorus
...
\insertchorus     % => the full chorus again
\insertchorus*    % => "R:  Refrén první řádek..."
```

The most recently defined chorus is the one repeated. Put `\beginchorus` on its own line. (Defined in `feature/refren.cfg`.)

## Chords

**Czech vs. English note names.** The note names follow the song's `lang`: Czech and Slovak songs use the German/Czech system (**H** = English B, **B** = English B-flat), everything else uses English names (B, B♭). This is selected automatically by the `lang` key; the underlying switches are `\germanchords` (alias `\czechchords`) / `\englishchords`.

**Forcing one printed convention for the whole book.** Put one of these in the preamble to make *every* song print its chords in the same system, regardless of language:

```latex
\useenglishchords   % print all chords in English names (B, B♭)
\usegermanchords    % print all chords in German/Czech names (H, B); \useczechchords is an alias
\useautochords      % default: each song follows its own language
```

Each song's chords are still *read* in its own language — so a Czech `\[H]` is understood as B-natural and *printed* as `B` under `\useenglishchords`, while a Czech `\[B]` (B-flat) prints as `B♭`. Only the printed names change; `\selectlanguage` (hyphenation, quotes) and the index still follow each song's `lang`. The commands also work mid-document, between songs, to switch a section. Note that transliterating across systems routes chords through the transposer, so accidentals are re-spelled to flats by default — add `\prefersharps` if you want sharps.

**Capo.** `\capo{n}` either prints a *Capo n* note (default) or actually transposes the chords by `n` semitones when capo transposition is enabled (the `songs` `transposecapos` option).

**Chord diagrams.** Diagram styling is tweaked (mono barre numbers; spacing above empty frets). Diagrams are drawn with the usual `songs` `\gtab`. (Capo + diagram tweaks live in `feature/akordy.cfg`.)

## Language and filtering

The `lang` key sets the `babel` language (hyphenation), the chord naming, and a per-language sort directive used by the index sorter (`songidx.lua`), so e.g. English leading articles rotate while the Czech conjunction "A" doesn't.

**Build variants by language.** Restrict which songs appear:

```latex
\includelangs{czech,slovak}   % keep only these languages
\excludelangs{czech,slovak}   % drop these languages
```

A song whose `lang` doesn't match is removed from the output (and not numbered). The project build scripts expose this as `-l` / `-e`. (Defined in `feature/lokalizace.cfg`, which also maps `\uv{…}` to proper Czech quotes.)

## Indexes

Two indexes are registered: **`obsah`** (by title) and **`obsahAutor`** (by author). The author index lists each author followed by their song titles (`Author --> Title`), with section headings per author. Classes typeset them via `\showindex`/`\insertindex` (see below). Defined in `feature/obsah.cfg`.

## Large vs. small paper

The boolean `\iflargepaper` (true in the A4 class, false in the A5 booklet) drives a few responsive helpers, so the same song source works on both sizes:

| Command / env | Effect |
|---------------|--------|
| `\smalleronsmallpage[frac]` | Shrinks its line on small paper only (default factor `0.5`). |
| `\begin{narrowonlargepaper} … \end{...}` | On large paper, sets the content in a narrower (80 %) column; full width otherwise. |
| `\narrowtextnote{…}` | A `\textnote` wrapped in `narrowonlargepaper`. |
| `\narrowlilypondfile{…}` | A `\lilypondfile` wrapped in `narrowonlargepaper`. |

## Customization hooks

Set these (usually in a class or the preamble) to restyle without touching the package:

| Hook | Controls |
|------|----------|
| `\zub@lyricfont` | Lyric font (default `\ttfamily`). |
| `\zub@printchord` | Chord font. |
| `\zub@stitlefont` | Song-title font. |
| `\zub@meterfont` | Meter font. |
| `\setchordwidth{…}` | Fixed chord width in `instrumental`. |
| `\secondvoiceraise` | Second-voice vertical tuck (multi-voice). |
| `\rolestyle`, `\secondvoicestyle` | Fonts/colors for role labels and the second voice. |

Fonts out of the box: Open Sans for text, Roboto Mono for lyrics and chords, FreeSans for Hebrew.

## LilyPond sheet music

Embed engraved sheet music with `lyluatex`'s `\lilypondfile{…}` (or `\narrowlilypondfile{…}`). Song fragments `\include "zubuvzpevnik.ily"` by bare name: `zubuvzpevnik.sty` adds this package's `lilypond/` directory to lyluatex's include path (locating it via kpse), so it works whether the package is on `TEXINPUTS` or installed in `~/texmf` — no copying required. The shared includes are `zubuvzpevnik.ily` and `tinwhistle.ily`.

## Document classes

### velkyzpevnik.cls

The big **A4** songbook, based on `article`. Adds:

- `\makefrontcover{image}` — a title page with the document `\title`/`\author` over the given cover image.
- `\insertindex` — a two-column table of contents built from both indexes (`obsah` and `obsahAutor`).
- Song metadata is shown in a box beside the title (large-paper layout).

### taborovyzpevnik.cls

The small **A5** camp songbook, based on `book` (two-sided, half-line spacing, multi-voice off). Adds:

- `\campyear` — the year shown on the covers; defaults to the build year, so pin it per book with `\renewcommand{\campyear}{2025}` to keep old songbooks reproducible.
- `\makefrontcover` — generated cover: big *Zpěvník*, the troop emblem, the `\title` and `\campyear` (year in the footer corner).
- `\makefrontcover[cover.pdf]` — use a hand-made cover PDF instead (its first page replaces the generated title page; the 2025 book uses one for its tengwar title).
- `\makebackcover[note]` — inside back cover with a chord overview (`akordy`) and credits; the optional `note` is printed above the credit line.
- `\padbookletpages[n]` — pad with blank pages up to a multiple of `n` (default 4) so `scripts/makebooklet.sh` can impose it as a printable booklet.

The generated cover and back cover use the SKAUT Bold and TheMix C5 fonts (Junák visual style; not in the repo).

## Package / class options

Options on `\documentclass[…]{velkyzpevnik}` (or `taborovyzpevnik`) are passed through to `songs`. The ones the projects use:

| Option | Effect |
|--------|--------|
| `chorded` / `lyric` | Show / hide chords. |
| `onesongcolumn` / `twosongcolumns` | One or two song columns per page. |
| `noshading` | No background shading or chorus bar. |
| `transposecapos` | `\capo{n}` transposes instead of printing a note. |

Any other `songs` option works too — see the `songs` manual.

## Source layout

```
zubuvzpevnik/
├── zubuvzpevnik.sty        # loads songs, fonts, layout, then imports the below
├── velkyzpevnik.cls        # A4 class
├── taborovyzpevnik.cls     # A5 camp/booklet class
├── feature/                # cross-cutting features
│  ├── lokalizace.cfg       #   language, H/B chords, filtering, Czech quotes, index sort
│  ├── obsah.cfg            #   index registration + formatting
│  ├── metadata.cfg         #   song metadata keys + the prelude box
│  ├── akordy.cfg           #   capo + chord-diagram styling
│  └── hlasy.cfg            #   multi-voice (\multivoice, \role)
├── songpart/               # structural song sections
│  ├── sloka.cfg            #   verse + \newSongPartType (bridge/prechorus/intro/outro)
│  ├── refren.cfg           #   chorus + \insertchorus / \insertchorus*
│  └── instrumental.cfg     #   chords-only part
└── lilypond/               # shared LilyPond includes (zubuvzpevnik.ily, tinwhistle.ily)
```
