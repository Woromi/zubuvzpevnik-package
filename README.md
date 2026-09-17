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
| `key` | Musical key — see below. |
| `tun` | Instrument tuning. A uniform detuning (`E\flat A\flat D\flat G\flat B\flat E\flat`, or `Half-step down`) transposes every shape you finger, so it counts towards `key`; a drop tuning like `D A D G B E` retunes one string and does not. |
| `tem` | Tempo. |
| `ori` | Original song (for covers / translations). |
| `chr` | Chords used, shown above the song (e.g. `\gtab` diagrams). |
| `src` | Source URL (typeset as a link). |
| `pap` | Paper sizes the song fits **one page** of, e.g. `a4,a5`, or **two facing pages** of with the `x2` suffix, e.g. `a5x2`. Prints nothing. No key means none; see below. |

`key`/`tun`/`tem`/`ori`/`chr`/`src`/`pap` are defined in `feature/metadata.cfg`; `lang` in `feature/lokalizace.cfg`. On large paper they are laid out in a box beside the title (see `\makeprelude`); on small paper they are omitted.

### Writing the `key`

**It names the key the song *sounds* in** — the shapes you finger, shifted by any global `\transpose`, by `\capo{n}`, and by a uniform `tun`. A song fingered in `Em` shapes with `\capo{4}` is `key={G\shrp m}`, not `key={Em}`; one fingered in `Am` shapes on a half-step-down guitar is `key={G\shrp m}` too.

**Note names follow the song's `lang`**, exactly as chord names do — so B-natural minor is `key={Hm}` in a Czech song and `key={Bm}` in an English one. Getting this wrong is easy and silent: `key={Bm}` in a Czech song reads as B-flat minor.

**Accidentals** use the `songs` package's own `\flt` and `\shrp` (`key={A\flt m}`, `key={G\shrp m}`). `\flat`/`\sharp` also render but draw a different glyph than the chords do, and a literal `♭`/`♯` has no glyph in the songbook font at all — LuaLaTeX drops it silently. Never spell a flat as a bare `b` (`Bbm`): it typesets as the letters.

**A song in two keys** names them all, home key first:

```latex
key={A\rightarrow Hm},        % verses in A, chorus in H minor
key={Cm\rightarrow C},        % minor verse opening into a major refrain
```

Write the arrow as `\rightarrow` with no space before it — the space after is TeX's control-word delimiter and is swallowed, so it prints tight on both sides. A literal `→` and `\textrightarrow` both resolve to a glyph the songbook font lacks and vanish from the PDF.

This is *not* what `\transpose` marks. `\transpose` reprints the chords at another pitch, for a verse that climbs a semitone; a modulation written out in the chords leaves them alone and just shifts where the music comes to rest. `scripts/checkkeys.py --parts` will tell you which parts sit in which key.

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
| Instrumental | `\begininstrumental … \endinstrumental` | — | chords only, fixed-width |

**Chorus.** Rather than the `songs` package's left-hand bar, the chorus is styled like a verse with a bold `R:` in place of the verse number and a slightly larger indent. It is still the `songs` chorus underneath. See also [Repeating the chorus](#repeating-the-chorus).

**Verse-based parts and your own.** Bridge/pre-chorus/intro/outro are created with one helper, so you can add more:

```latex
% \newSongPartType[setup]{name}{label}{indent-in-em}
\newSongPartType{solo}{S}{3}                  % \beginsolo … \endsolo, labelled "S"
\newSongPartType{interlude}{}{0}              % empty label = unnumbered (like intro)
\newSongPartType[\chordsonly]{guitarsolo}{}{0}  % chords-only (like instrumental)
```

The part renders as a verse whose number slot shows `label` and whose indent is `indent × em`. An empty label prints no marker — that's how the unnumbered parts (intro/outro/instrumental) work. An optional `[setup]` runs extra code in the part body — pass **`\chordsonly`** (see below) to make any part chords-only.

**Instrumental.** `\begininstrumental … \endinstrumental` typesets chords only, each chord in a fixed-width box (so chord-only passages align). It is just `\newSongPartType[\chordsonly]{instrumental}{}{0}` — the **`\chordsonly`** style is reusable, so you can give any part type the same look (`solo`, a song-specific break, …) with `\newSongPartType[\chordsonly]{name}{}{0}`. The chord width defaults to `2em`; change it with:

```latex
\setchordwidth{2.5em}
```

**Chord memory across parts.** The `songs` package can memorize a part's chords and replay them in a later part with `^` markers in place of the chords (see the `songs` manual's *Replaying chords*). Each part **type** keeps its own chord memory — a repeated verse replays the verse's chords, a repeated instrumental replays the instrumental's, and so on — so an instrumental's chords never accidentally become a verse's replayed chords. When you *do* want a part to replay another type's chords, say so explicitly:

```latex
% Just this interlude replays the verse's chords:
\begininstrumental\usechords{verse}
    | ^ | ^ | ^ | ^ |
\endinstrumental

% This interlude AND every later instrumental replay the verse (one call):
\begininstrumental\copychords{verse}
    | ^ | ^ | ^ | ^ |
\endinstrumental
```

Both go *inside* a part and name the source. `\usechords{source}` replays the source's chords in that one part; `\copychords{source}` copies them into the part's own register, so that part **and every later part of the same type** replay them — one `\copychords` covers a run of identical interludes. `verse` names the shared register that plain verses use; other names are part types (`instrumental`, `bridge`, …) or any register you declare with `\newchords`.

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

**Czech vs. English note names.** The note names follow the song's `lang`: Czech and Slovak songs use the German/Czech system (**H** = English B, **B** = English B-flat), everything else uses English names (B, B♭). This is selected automatically by the `lang` key; the underlying switches are `\germanchords` (alias `\czechchords`) / `\englishchords`. The `key={}` field follows the same convention — see *Writing the `key`* above.

**Forcing one printed convention for the whole book.** Put one of these in the preamble to make *every* song print its chords in the same system, regardless of language:

```latex
\useenglishchords   % print all chords in English names (B, B♭)
\usegermanchords    % print all chords in German/Czech names (H, B); \useczechchords is an alias
\useautochords      % default: each song follows its own language
```

Each song's chords are still *read* in its own language — so a Czech `\[H]` is understood as B-natural and *printed* as `B` under `\useenglishchords`, while a Czech `\[B]` (B-flat) prints as `B♭`. Only the printed names change; `\selectlanguage` (hyphenation, quotes) and the index still follow each song's `lang`. The commands also work mid-document, between songs, to switch a section.

Transliterating routes every chord through the transposer, so a chord's accidental is re-spelled to whichever of ♯/♭ is preferred rather than kept as you typed it: an English `\[F#]` prints as `G♭` in a flat-preferring book. A song printed in its own convention is never touched this way — its chords are passed through verbatim.

**Sharps or flats.** `songs` decides per song, from the key it transposes into, which is why its `\prefersharps` in a preamble does not outlive the first song. To pin one spelling for a whole book:

```latex
\usesharps            % every re-spelled accidental is a sharp
\useflats             % ... or a flat
\useautoaccidentals   % default: songs chooses, per song
```

`\prefersharps` / `\preferflats` are the one-song exception, and outrank the book-wide setting. They hold for the rest of the song wherever you put them — above or below `\transpose` / `\capo` — and do not leak into the next song. None of the three affects a song whose chords are printed verbatim — there is nothing to re-spell in a chord nobody parsed.

**Capo.** `\capo{n}` either prints a *Capo n* note (default) or actually transposes the chords by `n` semitones when capo transposition is enabled (the `songs` `transposecapos` option).

**No chord.** `\[\nochord]` marks a spot where nothing is played — it prints *N.C.* Write the macro, not the letters: in `\[N.C.]` the `C` is a note name like any other, so a song with a `\transpose` prints it transposed (*N.A♯* and so on).

**Chord diagrams.** Diagram styling is tweaked (mono barre numbers; spacing above empty frets). Diagrams are drawn with the usual `songs` `\gtab`. (Capo + diagram tweaks live in `feature/akordy.cfg`.)

## Language and filtering

The `lang` key sets the `babel` language (hyphenation), the chord naming, and a per-language sort directive used by the index sorter (`songidx.lua`), so e.g. English leading articles rotate while the Czech conjunction "A" doesn't.

**Build variants by language.** Restrict which songs appear:

```latex
\includelangs{czech,slovak}   % keep only these languages
\excludelangs{czech,slovak}   % drop these languages
```

A song whose `lang` doesn't match is removed from the output (and not numbered), index entry included. The project build scripts expose this as `-l` / `-e`.

A song with **no `lang` key** is kept by `\excludelangs` and dropped by `\includelangs`: including asks for songs *stated* to be in a language, excluding asks for everything that is not a named one. So the two are not complements — `\includelangs{czech}` plus `\excludelangs{czech}` does not reproduce the whole book. `scripts/checksongs.py --missing lang` lists the songs this affects. (Defined in `feature/lokalizace.cfg`, which also maps `\uv{…}` to proper Czech quotes.)

## Indexes

`\insertusedchords` prints every `chr={}` diagram in the book, grouped by song and headed *Přehled akordů* (pass an optional argument for another heading). It is for a book whose page is too small to show them beside the title — `malyzpevnik` calls it before its indexes. Only songs the language filter kept are listed. Nothing is printed in a `lyric` build, or when no song in the book declares `chr`.

`\insertallchords` is the compact alternative: the same diagrams merged into one sorted chart, no song titles, duplicates removed — a book's worth of unusual chords on a single page. Sorting puts a root's plain chords before its altered ones (`C7, C9, Cmaj7, C\shrp 7b9`), and two spellings of the same name are kept apart, so three different `F6` fingerings all survive. Both commands read the same collected list, so a book can use either (or both). Either may go inside the `songs` environment or after it, but **the list only holds the songs typeset before the command**, so a chart placed ahead of the songs prints nothing and says so in a warning. For a camp songbook the neat place is the project's own `akordy.tex`, which `\makebackcover` already `\input`s — replacing the hand-written chart with `\insertallchords` needs no class change.

Two indexes are registered: **`obsah`** (by title) and **`obsahAutor`** (by author). The author index lists each author followed by their song titles (`Author --> Title`), with section headings per author. Classes typeset them via `\showindex`/`\insertindex` (see below). Defined in `feature/obsah.cfg`.

## Large vs. small paper

The boolean `\iflargepaper` (true in the A4 class, false in the A5 booklet) drives a few responsive helpers, so the same song source works on both sizes:

| Command / env | Effect |
|---------------|--------|
| `\smalleronsmallpage[frac]` | Shrinks its line on small paper only (default factor `0.5`). The A5 body is already 9 pt, so the bare form gives 8 pt — see [the A5 body size](../docs/internals.md#the-a5-body-size). |
| `\chordsoffonsmallpage` | Inside a part: keeps its chords on large paper, drops them on small. |
| `\begin{narrowonlargepaper} … \end{...}` | On large paper, sets the content in a narrower (80 %) column; full width otherwise. |
| `\narrowtextnote{…}` | A `\textnote` wrapped in `narrowonlargepaper`. |
| `\narrowlilypondfile{…}` | A `\lilypondfile` wrapped in `narrowonlargepaper`. |

### Which songs fit which paper

Fitting A4 is not fitting A5, and the helpers above are how a song is tightened
until it does. The A5 body is set one step below A4 to begin with (9 pt against
10 pt), so most songs need no lever at all and the book reads at one size;
`\smalleronsmallpage` is for the few that still overflow, and takes them to
8 pt. Reach for `\chordsoffonsmallpage` before `\smalleronsmallpage`:
a part that reprints chords an earlier part already showed costs a chord line
above every lyric line, and dropping those buys back about as much room as a
whole font step without making anything harder to read.

The `pap={}` key records the outcome: `pap={a4,a5}` means the song has been
checked to fit **one page** of each, and `pap={a5x2}` that it
fits **two facing A5 pages** — a spread, which the two-sided A5 classes lay a
two-page song on so that it is played without a page turn. Every size a song is
known to fit is written down, so no key means none of them — whether the song is
too long for any page or nobody has measured it yet.

There is no `a4x2`: `velkyzpevnik` is one-sided, so it cannot promise the second
page of a song faces the first. The `x2` mark is written by hand — a song that
measures two pages may be one meant for a spread or one nobody has tightened
yet, which is a reading of the song rather than of the page.

No class declares which paper it is: `\zub@papername` is read off
`\paperwidth`/`\paperheight` at `\begin{document}` and matched against the
`\zub@paperis` lines in `zubuvzpevnik.sty`, so it always agrees with the paper
option the class handed `\LoadClass`. Teaching the package a new size is one
`\zub@paperis` line; a page size it does not know warns once and skips the
per-song check.

A song whose `pap` does not list the paper being typeset raises a package
warning while the book builds, with no opt-out — so an A5 build lists the songs
nobody has checked at that size.

The build also checks the claim against itself: a song marked for **one** page
that actually came out on two warns as well, naming both numbers. That one reads
the pages the song really landed on out of the `.aux`, so it needs the second
LuaLaTeX pass every project build already runs — a fresh build is silent on the
first pass and warns on the next. It is what catches a song that was tightened
onto one page once and has since grown.

`scripts/checkpaper.py` reports the flags, `--measure a5` re-derives them by
actually typesetting every song — a song with a line too wide for the column
does not count as fitting — and `--layout` builds the books and checks that the
two pages of a spread song really came out facing; see
[docs/tools.md](../docs/tools.md#checkpaperpy--paper-fit).

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

### malyzpevnik.cls

The **A5** songbook meant to be bound by hand as a hardback, based on `book`
(two-sided). It shares its whole body — geometry, song fonts, spacing,
multi-voice off — with `taborovyzpevnik` through `a5layout.cfg`, so a song
marked `pap={a4,a5}` fits both. What differs is everything around the songs:

- `\maketitlepage` — the first page *inside* the book (there is no printed
  case), with the document `\title`/`\author`/`\date`. `\maketitlepage[image]`
  prints an image under the title.
- `\insertindex` — both indexes, one column, meant to be called at the **end**.
- `\padbookpages[n]` — pad with blank pages up to a multiple of `n` (default 4)
  so the last sheet of paper is complete; `scripts/makebook.sh` cuts the
  signatures out afterwards.
- Page numbers are one arabic sequence from the title page to the last page,
  with the folio suppressed on the title page only. Nothing restarts the
  counter, which is why the indexes have to come last — see
  [../docs/internals.md](../docs/internals.md#the-hardback-book-signatures-instead-of-one-booklet).

### taborovyzpevnik.cls

The small **A5** camp songbook, based on `book` (two-sided, half-line spacing, multi-voice off). Adds:

- `\campyear` — the year shown on the covers; defaults to the build year, so pin it per book with `\renewcommand{\campyear}{2025}` to keep old songbooks reproducible.
- `\makefrontcover` — generated cover: big *Zpěvník*, the troop emblem, the `\title` and `\campyear` (year in the footer corner).
- `\makefrontcover[cover.pdf]` — use a hand-made cover PDF instead (its first page replaces the generated title page; the 2025 book uses one for its tengwar title).
- `\makebackcover[note]` — inside back cover with a chord overview (`akordy`) and credits; the optional `note` is printed above the credit line.
- `\padbookletpages[n]` — pad with blank pages up to a multiple of `n` (default 4) so `scripts/makebooklet.sh` can impose it as a printable booklet.

The generated cover uses the SKAUT Bold and TheMix C5 fonts (Junák visual style; not in the repo). They are optional: without them the cover falls back to the text font and warns, so the book still builds. See [../docs/building.md](../docs/building.md#cover-fonts).

## Package / class options

Options on `\documentclass[…]{velkyzpevnik}` (or `malyzpevnik`/`taborovyzpevnik`) are passed through to `songs`. The ones the projects use:

| Option | Effect |
|--------|--------|
| `chorded` / `lyric` | Show / hide chords. |
| `onesongcolumn` / `twosongcolumns` | One or two song columns per page. |
| `noshading` | No background shading or chorus bar. |
| `transposecapos` | `\capo{n}` transposes instead of printing a note. |

Any other `songs` option works too — see the `songs` manual.

## Source layout

Why any of it is written the way it is — the `songs` patches, the chord
registers, the chorus capture — is in [../docs/internals.md](../docs/internals.md).

```
zubuvzpevnik/
├── zubuvzpevnik.sty        # loads songs, fonts, layout, then imports the below
├── velkyzpevnik.cls        # A4 class
├── malyzpevnik.cls         # A5 class, hand-bound hardback
├── taborovyzpevnik.cls     # A5 class, camp booklet
├── a5layout.cfg            # the A5 body both A5 classes share
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
