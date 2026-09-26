# Implementation notes

Why the LaTeX package is built the way it is. *How to use* it is
[`zubuvzpevnik/README.md`](../zubuvzpevnik/README.md); this file is for whoever
maintains the code.

Everything here sits **on top of** the [`songs`](https://songs.sourceforge.net/)
package, mostly by patching its internals with `xpatch`. Line references like
`songs.sty:1295` point into the installed package
(`kpsewhich songs.sty`) and are the single biggest debugging aid when a TeX Live
upgrade breaks something — every patch carries a `\PackageError` that fires if
its search pattern is gone, so a broken patch fails the build loudly instead of
silently doing nothing.

## Contents

- [Source layout](#source-layout)
- [Package setup](#package-setup)
- [Localisation (`lokalizace.cfg`)](#localisation-lokalizacecfg)
- [Indexes (`obsah.cfg`)](#indexes-obsahcfg)
- [Metadata (`metadata.cfg`)](#metadata-metadatacfg)
- [Chords (`akordy.cfg`)](#chords-akordycfg)
- [Multi-voice (`hlasy.cfg`)](#multi-voice-hlasycfg)
- [Song parts](#song-parts)
- [The chorus (`refren.cfg`)](#the-chorus-refrencfg)
- [Document classes and booklet page maths](#document-classes-and-booklet-page-maths)
  - [The hardback book: signatures instead of one booklet](#the-hardback-book-signatures-instead-of-one-booklet)

## Source layout

```
zubuvzpevnik/
├── zubuvzpevnik.sty      loads songs, fonts, layout; \imports the modules below
├── velkyzpevnik.cls      A4 class  (article)
├── malyzpevnik.cls       A5 class  (book, twoside) hand-bound hardback
├── taborovyzpevnik.cls   A5 class  (book, twoside) camp booklet
├── a5layout.cfg          the A5 body both A5 classes share
├── feature/
│  ├── lokalizace.cfg     language, note naming, filtering, quotes
│  ├── obsah.cfg          index registration and formatting
│  ├── metadata.cfg       song keys (key/tun/tem/…) and the prelude
│  ├── akordy.cfg         capo notation, chord-diagram tweaks
│  └── hlasy.cfg          multi-voice and role labels
├── songpart/
│  ├── sloka.cfg          verse, part core, \newSongPartType, chord memory
│  ├── refren.cfg         chorus restyle + source capture
│  └── instrumental.cfg   \chordsonly and the instrumental part
└── lilypond/             .ily includes reachable by bare name
```

The modules are pulled in with `\import{feature/}{…}`, which resolves through
kpathsea rather than relative to the package — the relative path is found
because `zubuvzpevnik/` is on `TEXINPUTS` (repo build) or inside a texmf tree
(`install.sh`). A document whose own working directory contained a `feature/`
subdirectory would shadow ours, since `.` comes first on `TEXINPUTS`;
`\subimport` would be the robust form if that ever bites.

## Package setup

**Fonts.** Open Sans for text, Roboto Mono for lyrics and chords, FreeSans for
Hebrew, all via `\babelfont`. Alegreya Sans (role labels) and the two camp cover
faces are selected by name with `\setmainfont` at the point of use.

**Hyphenation in the lyric font.** Roboto Mono is declared
`HyphenChar={-}`, because `fontspec` loads a *monospaced* font with
`\hyphenchar\font=-1` — hyphenation off — and the lyrics are set in `tt`. Two
things need that character back: TeX's own line breaking, and `songs`, which
draws the hyphens of a word split across chords (`\[C]lo\[G/B]ne\[Am]ly` →
`lo - ne - ly`) only `\ifnum\hyphenchar\font>-1` (songs.sty:2595). The
declaration belongs to the *family*, so it is reapplied every time a font of
that family is loaded.

That last part is the whole point. The `hyphenat` package's `htt` option, which
used to stand here, assigns `\hyphenchar` by selecting each `tt` shape once
`\AtBeginDocument` — so it only ever reaches the font instances live at that
moment, and every instance loaded later comes up with fontspec's default. Two
things load later:

- **Other sizes.** A4 sets lyrics in plain `\ttfamily` (10pt) and worked; the A5
  body is `\small\ttfamily` (9pt, see [The A5 body size](#the-a5-body-size)) and
  `\smalleronsmallpage` is 8pt, and neither hyphenated.
- **Other languages.** `\babelfont` builds a separate family per language,
  lazily, at the first `\selectlanguage`. Only the main language (`czech`) is
  up at begin-document, so every `lang={english}` song was un-hyphenated on both
  papers.

**Styling hooks.** The package defines `\zub@lyricfont`, `\zub@printchord`,
`\zub@stitlefont`, `\zub@meterfont` and `\zub@repfont` as internal defaults and
wires them into the `songs` hooks (`\lyricfont` and friends). Classes override
the `\zub@…` versions, so restyling never touches the package.

`\zub@repfont` has no `songs` hook to wire into, so `\rep` is redefined outright
to `({\zub@repfont ×n})`: a repeat count is read rather than sung, and bold sets
it apart from the lyric it trails the way chords and the `R:` marker are set
apart. The times sign has to be the body font's own — `songs`' is `\char2` of
cmsy, a font with no bold series, so it stays light however it is wrapped.

**LilyPond include path.** A `\directlua` block asks kpse where
`zubuvzpevnik.sty` was found and appends that directory's `lilypond/` to
lyluatex's `includepaths`. That is what lets a song fragment write
`\include "zubuvzpevnik.ily"` by bare name with no copy into `songs/`, and it
works identically whether the package came from `TEXINPUTS` or `~/texmf`. It
appends rather than replaces, so a host document's own include paths survive.

**LilyPond note names.** A fragment never names its own language.
`\lilypondfile` is wrapped to read `\SB@songlang` and hand lyluatex
`language=deutsch` for `lang={czech}` and `lang={slovak}`, leaving the package
default `english` for everything else. So each `.ly` is written in the names its
song prints: `h` and `b` for B and B flat in a Czech song, `b` and `bf` in an
English one. There is no `czech` to ask for — LilyPond has no such language, and
Czech note names are the German ones anyway. `english` spells accidentals `s`
and `f`, so a sharp is `fs`, not `fis`.

`zubuvzpevnik.ily` derives the *printed* names from that same setting instead of
each fragment asking for them: an `h` in `pitchnames` means the fragment is in
German names, so `chordRootNamer` becomes the German one (H, B) and otherwise
stays the default (B, B♭). `\germanChords` is the stock way to ask for this, and
two things are wrong with it here. It has to stand *inside* the `ChordNames`
context — at top level it parses as a score of its own and is dropped with a
*zero-duration score* warning. And it also sets `chordNoteNamer`, which spells
bass notes lowercase and with `is`/`es` rather than glyphs (`G/h`, `H7/dis`);
LilyPond's own source marks that `lowercase?` is ignored as a FIXME. Leaving
`chordNoteNamer` unset makes bass notes fall back to `chordRootNamer`, which
gives the `G/H` and `H7/D♯` the songs print in their own chord lines.

A fragment moved between songs of different languages has to be respelled, and
nothing checks that — it parses either way and simply sounds wrong. Engraving it
before and after with chord names hidden and comparing the bitmaps is the way to
tell.

**Air around a score.** lyluatex wraps every engraved system in
`\preLilyPondExample` and `\postLilyPondExample` and leaves both undefined,
which is why a score otherwise butts straight against the lines above and below
it. The package defines them as `\addvspace{\zub@lilypondsep}`, a class
overridable in the `\zub@…` family like the fonts. A4 carries `\medskipamount`
without costing any song its one-page fit. A5 has next to none to spare — the
songs with scores sit right at the edge there — so `a5layout.cfg` drops it to a
token `1pt`; `scripts/checkpaper.py --measure a5` is what says whether a larger
value still fits.

**Tab stems.** `zubuvzpevnik.ily` draws tablature the way tab sites do: every
stem starts half a staff space below the bottom line and runs a fixed
`Stem.length` of 4 half-spaces, which ends it on the beam line
(`Beam.positions` −5). Two LilyPond details force the shape of it. The overrides
ride inside a redefined `\tabFullNotation`, because that command reverts
`Stem.length` and would undo a plain `\layout` override. And a beamed stem
ignores `stem-begin-position`, so a `Stem.stencil` wrapper cuts beamed stems off
at the same height; unbeamed ones keep `tabvoice::draw-double-stem-for-half-notes`
and its half-note double stem.

## Localisation (`lokalizace.cfg`)

### Quotes

`\enquote` is redefined to splice babel's per-language quote characters in
**literally**, rather than using csquotes' macro-delivered marks. With the macro
form, the `songs` chord scanner adds a stray `"- "` when a chord ends a quoted
phrase; a literal character does not. A language's marks become available once
its locale is imported, hence the `\babelprovide[import]` calls; un-imported
languages fall back to English quotes.

It also switches `#` and `&` to their active meanings (`\shrp`, `\flt`) itself,
in a group around the argument read. `songs` only activates them while it scans
a chord name — `\SB@bracket` → `\SB@begincname` sets the catcodes, then
`\SB@@chord` reads up to the `]` — which is late enough for an ordinary lyric
line, where TeX has not tokenised the rest of the line yet, but too late for
text already swallowed as a macro argument. Without it, `\enquote{… \[C#m]…}`
fails with *Illegal parameter number in definition of `\SB@tempv`* (songs.sty:1832,
the branch a `\transpose`d song takes) because the `#` arrives as a real
parameter token. `\uv` is `\let` to `\enquote` rather than wrapping it, so it
does not read the argument one level too early and lose the same trick.

Any other macro taking lyric text as an argument has the same constraint —
`\multivoice` among them, though songs there keep their chords outside the
argument. Spelling the accidental as `\[C\shrp m]` works everywhere regardless.

### Note names: the eighth note

Two naming systems are in play:

| | A | B♭ | B♮ |
|---|---|---|---|
| English | A | B flat | **B** |
| German/Czech | A | **B** | **H** |

The `songs` package supports exactly seven note names, but German/Czech needs an
eighth: `B` meaning English B-flat. Two `\patchcmd`s on `\SB@trtrans` add it:

- **input** — a name matching none of the seven `\notenames` is compared against
  `\ZUB@noteBb` and read as semitone 1;
- **output** — semitone 1 prints `\ZUB@printBb` instead of `\printnoteB\flt`, so
  German/Czech names give `B` rather than the nonsense `Hb`.

A third patch, on `\SB@trnote`, is what makes those two reliable. `songs` folds
a chord's accidental into the semitone only while transposing; with
`\SB@transposefactor` at zero it skips the accidental (songs.sty:1891), because
within one naming system it cannot change. Transliteration is the case where it
can — the note *letter* moves — so an English `\[B&]`, whose letter maps to `H`,
used to print as the nonexistent `H♭` instead of German `B`. The shortcut is
switched off (the test is patched to `\iffalse`), so the `\flt`/`\shrp` branches
after it always run. The cost is that a transliterated accidental is now
re-spelled by preference rather than kept verbatim, which is what transposing
already did.

`songs` reads chords through `\notenamesin` and prints them through
`\notenamesout`, with the semitone as a language-neutral intermediary. That
split is what makes `\useenglishchords` and friends possible: a song's chords
are always *read* in its own language's convention but may be *printed* in
another, which transliterates. When the two match, `\SB@convertnotesfalse` makes
`songs` leave chords verbatim, so no enharmonic re-spelling happens — the
original behaviour.

### Accidental spelling

`\prefersharps` is a `songs` command, and `songs` overrides it per song:
`\transpose` sets `\SB@needkeytrue` (songs.sty:1811) and `\SB@setkeysig` then
picks sharps or flats *globally* from the key the song transposes into. So a
`\prefersharps` in a preamble never survives the first song.

`\usesharps` / `\useflats` / `\useautoaccidentals` pin the choice book-wide, the
way `\useenglishchords` pins a naming. Two hooks are needed, because the two
paths that set the preference are different: `\SB@setkeysig` is wrapped so the
automatic choice yields to a pinned one, and `\SB@@@beginsong` re-asserts it for
songs that never transpose, where `\SB@setkeysig` is not consulted at all. Both
assignments are `\global`, as `songs`' own are: a chord is set inside a group
that the next song must not inherit from.

`\prefersharps` and `\preferflats` are redefined onto the same mechanism, as a
one-song pin that outranks the book-wide one. Left as `songs` defines them they
only set the flags, so `\transpose` below them takes the choice straight back —
*Amazonka* asks for `\preferflats` and, before this, printed its descending
Hm–B♭m–Am as **Hm A♯m Am** because the `\transpose{-2}` on the next line
re-armed the guess. Recording the request instead of only acting on it makes it
hold wherever in the song it stands. `\SB@@@beginsong` clears it, so it does not
leak into the next song — which is also why a `\prefersharps` in a preamble
still does not survive the first song.

### Index sort directive

`\SB@addtoindex` is patched to emit a `%lang <language>` line before each song's
index entries, so `songidx.lua` can apply per-language title rules — rotating
the English articles *The/A/An* while leaving the Czech conjunction *A* alone.
The `%` is written as `\@percentchar` so it reaches the file as a literal.

### Language filtering

`\SB@submitsong` is wrapped: a song that fails the filter has its box voided
(`\setbox\SB@songbox\box\voidb@x`) and the song counter rolled back.

Voiding the box is also what keeps filtered songs **out of the indexes**, which
is not obvious. `\SB@addtoindex` does not write immediately — it parks deferred
`\write` whatsits in `\SB@songwrites`, which `\SB@endsong` unboxes into
`\SB@envbox` and thence into `\SB@songbox`. Discarding that box discards the
whatsits, so they never ship and never reach the `.sxd` file.

A song with **no `lang` key** is kept by `\excludelangs` and dropped by
`\includelangs`, because `\IfSubStr{list}{}` is false in xstring for an empty
needle. That asymmetry is intended — see the user-facing note in
[`zubuvzpevnik/README.md`](../zubuvzpevnik/README.md#language-and-filtering).
Note the test is a substring match, so a language name that is a substring of
another in the list would collide; harmless with the current language set.

## Indexes (`obsah.cfg`)

Two indexes are registered: `obsah` (title) and `obsahAutor` (author).
`\SB@@@beginsong` is patched so the author index receives `author-->title`
rather than the author alone, which is what produces the *Author → Title*
entries. Two more patches on `\SB@makeauthorindex` force the author index to use
the large-index layout with per-author section headings, which the package
otherwise only uses for long indexes. `\idxheadwidth` is widened from the stock
1.5 cm because the headings are now author names, not single letters.

**`\idxheadwidth` is set from the column, not the page.** `\SB@idxsetup` runs
inside each index column with `\hsize` already narrowed to the column width, so
hooking it is what keeps the heading inside its column. Setting the length once
at load time from `\linewidth` takes the whole text block — harmless in a
one-column index, but in a two-column A5 index that is 254 pt of heading in a
177 pt column, and it pushes the right-hand column clean off the page (the
author index measured a *negative* right margin).

Both indexes are two columns on both papers; on A5 that takes them from 13 pages
to 7. **`\insertindex` narrows `\hsize` by 8 pt first**, which is what keeps
them inside the margins. Two things eat into the right edge otherwise, and both
only show from the *second* page of an index, because songs.sty sets the first
page of each as one centred column:

- `\SB@multiline` ends every entry with `\rightskip2em` and then pulls the page
  reference back out with `\kern-2em`, so a reference wider than 2 em hangs past
  the line. Three-digit page numbers do exactly that.
- `\SB@colwidth` is derived from `\hsize` at `\SB@displayindex` time, and twice
  the column plus one `\columnsep` came out about 1.4 pt wider than the text
  block.

Together they cost 6 pt — 2.1 mm of the 10 mm outer margin, which on a verso is
the spine side of a book bound with no allowance. Taking 8 pt off `\hsize`
absorbs both and costs no pages.

A long author name still has to wrap, so the heading box measures the name and
falls back to a `\parbox` when it does not fit; that measurement needs its own
save box, because box 0 is scratch for the index machinery around it and reusing
it reflows 40 pages of A4. Note `\SB@colorbox` pads with a hardcoded `\kern3\p@`
rather than `\fboxsep` under the `noshading` option all our classes pass, so
`\fboxsep` is not the knob it looks like.

## Metadata (`metadata.cfg`)

Each optional key (`key`, `tun`, `tem`, `ori`, `chr`, `src`) is a `\newsongkey`
that stores a formatted fragment in a macro; `\extendprelude` prints them in a
fixed order. `\makeprelude` is redefined to put the title on the left and, on
large paper only, a right-aligned 7 cm `\parbox` of metadata beside it, inside a
zero-width `\makebox` so it costs no horizontal space.

`met` and `cap` are not display fragments: their macros (`\zub@songmeter`,
`\zub@songcapo`) run from a hook appended to `\SB@@@beginsong`, inside the song
box, where a top-of-song `\meter`/`\capo` would have run. The hook has to come
after that macro's own `\meter44` (songs.sty `\SB@@@beginsong`), which is why a
song without `met` gets an explicit `\meter{}{}`: otherwise every song with
measure bars would show 4/4 at its first bar whether it is in 4/4 or not.
`checksongs.py` warns on a song with bars and no `met`.

The macros holding the fragments (`\key`, `\tuning`, `\tempo`, `\original`,
`\usedchords`, `\sourcelink`) are unprefixed. `songs` defines none of these — if
it did, we would be using its version instead of a second one — and each is a
`\newcommand`, which refuses a name that is already taken, so a collision with
some other package is a build error naming the macro rather than a silent
override. Renaming to `\zub@…` is the fix if one ever turns up.

### Paper fit

`pap={}` is a *claim*, and two checks test it. `\zub@checkpaperfit` reads the
key: it warns when the paper being typeset is not listed, which catches a song
nobody has measured. That one cannot catch the opposite mistake — a song that
still says `a5` after an edit made it too long — because the key alone cannot
know.

`\zub@checkpagespan` catches that one by asking the build. songs.sty puts the
prelude at the top of the song box and the postlude at the bottom
(songs.sty:884, 896), so a `\write` parked in each ships out with the song's
first and last page. Both land in the `.aux` as `\zub@songpage{id}{s|e}{page}`
and are read back on the next run, so this needs two LuaLaTeX passes exactly as
`\pageref` does — every project build makes at least two. The first pass of a
fresh build is therefore silent; the warning appears on the pass after it.

Three details are load-bearing:

- The id is `\theSB@songsnum-\thesongnum`, the same pair songs.sty uses for its
  hyperref anchors, so it stays unique across several `songs` environments. The
  language filter decrements `songnum` for a song it drops (`lokalizace.cfg`),
  which keeps the numbering dense and the ids stable between runs.
- The page is written as `\the\c@page`, not `\thepage`: front matter may number
  in roman and the span is arithmetic. It is `\let` to `\relax` inside
  `\protected@write` so it survives the `\edef` unexpanded and is expanded at
  shipout, which is what makes it the page the song actually landed on rather
  than the page the page-builder happened to be on.
- A song dropped by the language filter has its box voided, so neither `\write`
  ever ships and the lookup finds nothing — no warning for a song the build did
  not print.

The allowance comes from which mark matched: a plain `a5` promises one page, a
bare `a5x2` two. A song listing both is held to the stronger claim.

## Chords (`akordy.cfg`)

`\capo{n}` either transposes (when the `songs` `transposecapos` option is on) or
prints a *Capo n* note; the projects do not enable that option, so capo and
`\transpose` stay separate axes and the written `\[chord]` shapes are what you
finger. Two `\patchcmd`s tune the diagrams: `\SB@fretnum` gets a monospace barre
number, and `\SB@topempty` gains a strut so empty frets reserve height.

Accidentals inside chords are `#` and `&`; the printed glyphs come from `songs`'
own `\shrp` (a raised superscript `#`) and `\flt` (a shrunk, raised `$\flat$`).
The math-mode `\sharp`/`\flat` render but do not match, which is why
`checksongs.py` nags about them — see [tools.md](tools.md).

### No chord

`\nochord` is the *N.C.* mark, and it is a macro because the text cannot be
written out. `\[N.C.]` has its `C` read as a note name and transposed with
everything else, so in a song carrying a `\transpose` it prints as whatever the
`C` became — `\[N.C.]` in *Amazonka* (`\transpose{-2}`) printed **N.A♯**. The
transposition scanner only reads uppercase letter tokens as note names
(`\SB@trstep`) and copies anything else into its output register untouched, so a
macro token survives and expands to the literal text afterwards.

Bracing the text does not work: `\[{N.C.}]` reaches `\SB@@chord#1]` as a single
brace group, and TeX strips the outer braces off a macro argument before
`\SB@trgroup` — which does pass groups through — ever sees them.

## Multi-voice (`hlasy.cfg`)

`\multivoice{main}{second}` stacks two lines in a `\vtop` with
`\offinterlineskip`, pulling the second up by `\secondvoiceraise` so it tucks
under the main line rather than sitting a full small-line below it. The `\strut`
goes *inside* `\secondvoicestyle` so it shrinks with the smaller font. `\role`
is the right-aligned label variant. `\multivoiceoff` (used by the A5 class)
drops the second voice and keeps only the main line.

`\multivoiceinline` prints `main (second)` on one line. Songs often split a
second voice across chords (`\[D]{\multivoice{}{should we be}}\[Am]{\multivoice{}{lieve you?}}`),
and each fragment lands in its own chord `\vbox`, so TeX can't see the next one
when it closes the paren. The parens (and any space `\multivoice` inserted
before one) carry the `\zub@mvattr` attribute instead, and `lua/hlasy.lua`
runs in `pre_linebreak_filter`: walking only the lyric row of each chord box, it
deletes every `)`…`(` pair with no lyric glyph between them and shrinks the
boxes they sat in. Other lyric content splits too, though it isn't a glyph: a
measure bar (a `\vrule` in its box's last row) and filler spacing such as `~`
(`\nobreak` + space). A chord over no lyric ends in the same `\nobreak` +
space (`\SB@emitchord`), so after a chord box with an empty lyric row that pair
is the chord's, not filler. A space typed at the end of the second voice is moved
outside the `)` so the join keeps the word gap (`It's my `+`life`).

`\rolestyle` selects a family defined once with `\newfontfamily`; calling
`\setmainfont` per label would re-read the font each time.

## Song parts

### Chord memory

`songs` memorises and replays chords through **one** shared register,
`\SB@cr@`: inside `\beginverse` (songs.sty:1295) the first verse-based part in a
song memorises its chords and every later part replays them wherever you put `^`
markers. Since all our parts are built on `\beginverse`, that single register
would let an instrumental's chords leak into a later verse's replay.

So each part **type** gets its own register:

- `\zub@newpartchords{name}` declares `SB@cr@<name>` once (via the package's
  `\newchords`) and records the name in `\zub@partnames`.
- `\zub@resetpartchords`, hooked into `\SB@@@beginsong`, empties every named
  register at each song. The package resets only the default one
  (songs.sty:842), so without this chords would leak across songs.
- `\zub@partchords{name}`, called from `\zub@beginpart` just after
  `\beginverse`, points the memory at that part's register — memorise if empty,
  replay otherwise — overriding the choice songs.sty:1295 just made.

Plain `\beginverse` keeps the package default register, which is also reachable
under the name **`verse`** (`\SB@cr@verse` is `\let` to `\SB@cr@`) so it can be
named in `\usechords`/`\copychords`.

`\memorize` is redefined so the bracket-less form targets the current part's
register; `\memorize[name]` is unchanged. `\zub@currentpart` holds the current
part name — empty in a plain verse and during songs.sty:1295, which runs before
`\zub@beginpart` sets it, so plain verses and the package's own internal call
still hit the default register.

This is rendering-neutral: memorising chords does not affect the
chord-split-word hyphens, which are a typesetting-time width decision
independent of which register is active. Verify changes here by building the
same document against two `TEXINPUTS` trees, not by diffing sources.

### The part core

`\zub@beginpart{name}{label}{indentEm}{setup}` starts a numbered `\beginverse`
and immediately rolls the counter back, so the part does not consume a verse
number; `label` (bold) replaces the number in the slot and `indentEm` sets the
slot width. An empty `label` shows no marker — that is how intro/outro/
instrumental get their unnumbered look without a separate `verse*` path, since
the rollback is needed for the labelled parts anyway. `setup` is extra body
code, e.g. `\chordsonly`. `\printversenum` prints the trailing dot only for a
non-empty label.

`\newSongPartType[setup]{name}{label}{indent}` declares the register, defines
`\begin<name>` on the core, and wraps it in a `\newenvironment{<name>}` so both
`\begin<name>…\end<name>` and `\begin{<name>}…\end{<name>}` work, as they do for
the package's own verse. `\newenvironment` defines `\<name>` (what
`\begin{<name>}` calls) and `\end<name>` (shared by both spellings), and
sidesteps `\newcommand`'s refusal of `end`-prefixed names. Don't mix spellings
within one part — that trips LaTeX's environment checker exactly as it would for
`verse`.

### Chords-only parts

`\chordsonly` is `\nolyrics` plus fixed-width chord boxes (`\zub@chordwidth`,
set via `\setchordwidth`) and tightened vertical spacing. Passed as the
`[setup]` of `\newSongPartType` it makes any part type chords-only; the built-in
instrumental is exactly `\newSongPartType[\chordsonly]{instrumental}{}{0}`.

There is deliberately **no `\ifchorded` guard**: a chords-only part in a `lyric`
build simply renders empty. The old guard wrapped only the verse and not its
`\[…]` body, so in `lyric` mode the orphaned `\[` started display math and
errored.

### Collected chord diagrams

The `chr={}` diagrams are laid out beside the title, which only the large-paper
prelude has room for, so on A5 they would simply not print. `\insertusedchords`
gathers them instead: each song stashes `\ZUB@chordentry{title}{diagrams}` into
`\ZUB@chr@pending` from `\makeprelude`, and the flush into the global
`\ZUB@chordlist` hangs off `\SB@origsubmitsong`.

Both halves are deliberate. The stash has to happen *inside* the song, because
`\songtitle` is only the song's own there — `\SB@@@beginsong` walks the title
list and `\resettitles` restores it within the song's group, so after `\endsong`
it is whatever the previous song left. The flush has to happen at
`\SB@origsubmitsong`, because that is what `lokalizace.cfg` calls *only* for a
song the language filter keeps; hooking anything earlier would list the chords
of songs the build dropped. `metadata.cfg` is imported after `lokalizace.cfg`,
which is what makes that hook available.

Printing is a `\renewcommand` of `\ZUB@chordentry` inside a group, so the stored
list is one flat token list replayed under whatever layout the book wants — the
shipped one is a two-column row per song, title left and diagrams right, built
from two `\parbox[t]`es. Each opens with `\vspace{0pt}` so the boxes align by
their tops rather than by first baseline, which is what puts the title level
with the chord names instead of down on the fret numbers. `\par` is neutralised
inside the diagram box, because `\usedchords` ends with one; let that escape and
it breaks whatever environment encloses the list. The name column is a fraction
resolved at use time, not a length fixed at load: the class loads `geometry`
after this package, so `\linewidth` only means the text width once a page exists.

`\insertallchords` replays that same list with `\gtab` bound to a recorder
instead of a drawing command, which is why the collection stores the `chr` blob
whole rather than parsed: the parsing is free at print time. Deduplication and
sorting happen in Lua (`zubuvzpevnik/lua/akordy.lua`) — the package is
LuaLaTeX-only through `lyluatex` anyway, and sorting in TeX is not worth it. The
Lua lives in a file rather than inline because `\directlua` expands its argument
as TeX, which eats the backslashes and percent signs the code needs. Emission is
`tex.print` per chord so that each input line's end supplies the glue TeX needs
to break the chart into rows; `tex.sprint` would run them into one unbreakable
line. No chord name in the corpus contains a literal `#` or `&` — they are all
written `\shrp` and `\flt` — which is what lets the recorder take `\gtab`'s
arguments with a plain two-argument macro instead of repeating `\SB@begincname`'s
catcode dance.

Placement inside a `songs` environment needs care, and the commands handle it.
`\end{songs}` is what ships the queued songs (`\commitsongs`), so material
typeset inside the environment but outside a song reaches the page *ahead* of
songs still queued, and a `\clearpage` there tears the queue apart — the
symptom is a chart printed before the last song, with that song split across two
pages. `\ZUB@chr@ownpage` therefore wraps the output in songs.sty's own
`intersong*` while `\ifSB@songsenv` holds, which hands it to the same pipeline a
song goes through, and falls back to a plain `\clearpage` outside.

`malyzpevnik` calls it before its indexes; adding pages there moves no song page,
for the same reason the indexes sit there. Its length is close to free: with
`\padbookpages` rounding the book up to a multiple of four, an overview of one,
two, three or four pages all cost the same four pages of paper.

### The blank page before a spread song

`songs.sty` will not start a two-page song on a right-hand page: `\SB@spdblpg`
advances the column counter by a whole page when the parity is wrong, and the
song moves to the next spread. Every song here starts on a fresh page
(`\spenalty=-10000`), so nothing fills the page left behind and the book gets a
blank leaf mid-way.

That branch is patched to warn, naming the song. The patch point is the
`\advance\SB@cnt\SB@numcols` inside `\if@twoside\ifodd\c@page\else`, which is
the skip itself rather than the two-page case, so a spread song whose parity
already works raises nothing — tabor2025 carries two of them silently. The title
comes from `\ZUB@lastsongtitle`, stashed globally in `\makeprelude`, because
`\songtitle` is restored inside the song's group and no longer the song's own by
the time `\SB@submitsong` places it.

The fix is never in the song: it is to change how many pages precede it, by
moving a one-page song across the boundary. `scripts/checkpaper.py --layout`
reports the same thing from the finished PDF.

## The chorus (`refren.cfg`)

### Verse-like look

Three patches: `\justifyleft` gains a bigger left indent while
`\ifSB@inchorus`, `\beginchorus` is flipped to `\vnumberedtrue` to give the
chorus a number slot, and `\SB@@beginchorus` fills that slot with a bold `R:`.
`\norepchoruses` disables the package's box-based repetition (we capture the
source ourselves) and `\cbarwidth` is zeroed to drop the left-hand bar — the
documented way, and what the `noshading` option also does.

### Source capture

`\beginchorus` grabs its body as a delimited argument, stores it detokenized in
`\zub@chorusstr`, and replays it through the real chorus with `\scantokens`.
Re-reading it as *input* is the point: the `songs` chord reader runs again, so
sharps and everything else render normally, and `\insertchorus*` can turn chords
off for the reminder line. During the grab, line ends must survive
(`\endlinechar=13`, since `songs` sets it to −1) and `#` is made a plain
character so it is storable and detokenizes cleanly.

**Both spellings work, as they do for the verse** — but they need different grab
delimiters:

| Spelling | Delimiter |
|---|---|
| `\beginchorus … \endchorus` | `\endchorus` |
| `\begin{chorus} … \end{chorus}` | `\end` |

The environment form never puts an `\endchorus` token in the input:
`\end{chorus}` merely *calls* `\endchorus`, by which time the body would already
have to have been read. So `\chorus` — what `\begin{chorus}` runs — raises a
flag and `\beginchorus` picks the matching grabber. The flag is global because
`\beginchorus` opens a group before reading it, and is cleared the moment it is
read so it cannot leak into the next chorus.

The swallowed `\end{chorus}` is handed straight back, so LaTeX still runs
`\endchorus` (closing the chorus that `\zub@chorus@replay` opened) and still
closes the group `\begin{chorus}` opened.

**Limitation:** a `\begin{chorus}` cannot contain another environment, because
its `\end` would be taken for the chorus's. That is refused with a clear error
naming the offending line rather than a runaway argument.
`\beginchorus … \endchorus` has no such limit. Making the environment form
recursive (accumulating into a token register and re-grabbing on a foreign
`\end`) would remove it; no song has ever needed it.

Both `\zub@chorusstr` and `\zub@chorusfirststr` are stored **globally**:
`\begin{chorus}` runs inside a group of LaTeX's making that `\end{chorus}`
closes, and a local assignment would not outlive it — the symptom was
`\insertchorus*` silently printing nothing after an environment-form chorus.

`\zub@chorus@extractfirst` hands the stored string to `lua/refren.lua`, which
splits it on the catcode-12 CR and returns the first line that carries text
once control words and brace groups are set aside. That skips the empty segment
the `\beginchorus`-line newline produces and, as importantly, a line of setup
alone: `\beginchorus\chordsoffonsmallpage` leaves `\chordsoffonsmallpage` as the
first "line", and a reminder built from it printed nothing but `...`. Lua
returns the line with `tex.sprint(-2, …)`, as the same catcode-12 string
`\detokenize` made.

## Document classes and booklet page maths

All three classes load the package, set `geometry` margins, override the
`\zub@…` font hooks and add cover/index commands. `velkyzpevnik.cls` is A4 on
`article` with `\largepapertrue`; `taborovyzpevnik.cls` and `malyzpevnik.cls`
are A5 on `book`, two-sided, with multi-voice off.

The two A5 classes take their geometry, song fonts and spacing from one file,
`zubuvzpevnik/a5layout.cfg`, rather than each setting their own. That file *is*
the text block `pap={…,a5}` was measured against, so a song that fits the camp
booklet fits the hardback book and the mark means one thing; editing it makes
every A5 mark in the database stale. It warns if a class loads it on a page
that is not A5.

### The A5 body size

The A5 body is **9 pt**, one step below the 10 pt the classes hand `book`, set
in `a5layout.cfg` as `\zub@lyricfont` = `\smaller[0.5]\ttfamily`. A song needing
more room asks with `\smalleronsmallpage`, which is then 8 pt.

It was 10 pt until 2026-09-17, with each tight song shrinking itself. That put
three sizes in one book — 80 songs at 10 pt, 27 at 9 pt, 5 at 8 pt — which is
what the change is against; it buys uniformity, not room.

**`\smaller[n]`'s argument is magsteps, not points and not sizes on the ladder.**
`relsize` rounds `n` to whole *half*-magsteps and multiplies by 0.912871
(= 1/&radic;1.2) that many times, then snaps the result to the nearest standard
LaTeX size if it lands within 5 %. From a 10 pt base: `[0.5]` targets 9.129 and
snaps to **9 pt**, `[1]` targets 8.333 and snaps to **8 pt**, `[2]` targets
6.944 and snaps to **7 pt**. So two `[0.5]`s in a row give 10 &rarr; 9 &rarr; 8,
not 10 &rarr; 9.5 &rarr; 9. From the 9 pt base now in force,
`\smalleronsmallpage` is 8 pt and `[1]` targets 7.5, which is 6.7 % from both 7
and 8 — outside the tolerance — so it emits a literal `\fontsize{7.5}`.

Dropping the base by one size therefore meant dropping one notch off every
song's own lever: 29 `\smalleronsmallpage` lines deleted (the base now does that
job) and 5 `[1]` weakened to plain. That is why no song changed size but the 80
that carried no lever.

**`\printversenum` must not re-apply `\lyricfont`.** It used to, and because
`\lyricfont` now carries the body *size*, the verse number was sized twice —
which broke both ways round. With a relative `\smaller[0.5]` in
`\zub@lyricfont` the number came out one step *below* the lyrics; with the
absolute `\small` it was *pinned* to 9 pt and stopped following a song's own
`\smalleronsmallpage`, so a song shrunk to 8 or 7 pt kept 9 pt verse numbers
(caught on *Cudzinka v tvojej zemi*, 2026-09-17). The fix is to print the number
with no font command at all: the verse's font is already in force, which is
exactly why the `R:` chorus label (`refren.cfg`, a plain `\bfseries{R:}`) tracked
the body size correctly all along. Anything added to `\zub@lyricfont` is applied
wherever `\lyricfont` is called, so check those call sites before putting a size
in it.

Sizes are verified from the PDF rather than by reasoning: `pdftotext -bbox`
gives each word's box, and in the monospaced body the advance width is 0.6 em,
so `width / len(word) / 0.6` is the point size. Verse number, `R:`, chord and
lyric should all agree.

Nothing else moved: same 128 pages, the same songs fit, and the A4 book is
unchanged, `\smalleronsmallpage` being a no-op on large paper. Two tin-whistle
songs newly fit and gained the mark. Re-measured with
`scripts/checkpaper.py --measure a5 --write` afterwards, as editing this file
always requires.

`\campyear` defaults to the build year and is pinned per book
(`\renewcommand{\campyear}{2026}`) so old songbooks rebuild unchanged.

### Why the page count must be a multiple of 4

`scripts/makebooklet.sh` imposes two A5 pages per A4 sheet, so four book pages
share a sheet. The covers only land on the outside of the first and last sheet
if the whole PDF is a multiple of 4 pages. The structure that guarantees it:

```
 2 pages   front matter   cover + index          (\makefrontcover)
 4n pages  songs          padded to a multiple   (\padbookletpages)
 2 pages   back cover     chord overview + blank (\makebackcover)
──────────
 4 + 4n    → always a multiple of 4
```

#### The hardback book: signatures instead of one booklet

`malyzpevnik.cls` is bound by hand, so it is not one booklet: the pages are cut
into several gatherings that are folded and sewn separately. That changes both
ends of the arithmetic.

It needs no cover arithmetic, because it has no printed cover — the book is
cased in by hand, behind a blank leaf at each end.

**Those two leaves are `\bindingleaf`, and they have to stay blank.** Casing in
glues the board straight onto the outer leaf of the block: the pasted side
disappears under the board, and the side facing the reader is stuck to it and
never turns, right at the hinge where nothing lies flat. Whatever is printed
there is lost. Without them the title page would be the pasted-down side and the
last index page the one at the back. Each call is one leaf, two pages, so the
front one shifts every song by an even number of pages and cannot change the
left/right parity a `pap={a5x2}` spread depends on. They are also the
conventional flyleaves if separate endpapers are used instead, so they cost
nothing either way. Page numbers run
as one arabic sequence from that page to the last, which is also why the
indexes are at the end: with no restart, an index at the front would move every
song page number it records and the two passes would never converge.

`\padbookpages` therefore only rounds the whole document up to a multiple of 4,
so the last sheet of paper is complete. Its filler runs *after* the closing
`\bindingleaf`, so it sets `\thispagestyle{empty}` too — otherwise the folio
would print on the very surface the back board is glued over. It and `\padbookletpages` are the same
loop — `\zub@padpages` in the package, which counts from the page the class
started numbering at — wrapped differently by each class. `scripts/makebook.sh` cuts the
signatures out of that page count afterwards: it picks an **even** number of
signatures as near the target thickness as it can (`-s`, default 5 sheets) and
gives them sheet counts differing by at most one, so nothing has to be padded
beyond the whole sheet. A 76-page book comes out as 19 sheets in 4 signatures
of 5, 5, 5 and 4.

Each signature is extracted with `pdfseparate`/`pdfunite` and imposed on its own
with the same `pdfbook2 --short-edge --no-crop` recipe as the camp booklet, then
the imposed signatures are concatenated in order. Extraction goes through
poppler rather than `pdfjam` because `pdfjam` re-lays the pages out on its own
paper, which would rescale them off A5 before `pdfbook2` ever ran. `pdfbook2`
itself runs with the temporary directory as its working directory: it renames a
scratch file out of the working directory, which fails across filesystems when
the temporary directory is on tmpfs.

A binding allowance is deliberately absent. `geometry`'s `bindingoffset` would
narrow the text column, every song would reflow and every A5 measurement
would be wrong; and the imposition has no slack to give, since two A5 pages fill
an A4 sheet exactly. If the sewn spine turns out to swallow too much of the
inner margin, the change that keeps the marks valid is to widen the *paper* in
the class by the allowance while leaving the text block alone, and register the
new size with `\zub@paperis` — the pages then scale down as a whole at
imposition, and nothing reflows.

`\padbookletpages` can only see the middle: `\makefrontcover` resets the page
counter to 1 so the songs number from one, which hides the front matter from it.
It therefore records the front-matter length in the `ZUB@frontpages` counter
before resetting, and warns if that is not 2 — the realistic way to break this
is an index that grows onto a second page. `makebooklet.sh` re-checks the
finished PDF with `pdfinfo` and refuses to impose a count that is not a multiple
of 4, because `pdfbook2` would otherwise pad at the *end* and bury the back
cover on an inner sheet face. The class warning explains, the script gates —
and the script is the one you will see, since `build.sh` silences LaTeX without
`-v`.
