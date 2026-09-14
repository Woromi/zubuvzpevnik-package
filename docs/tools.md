# Developer tools

Three tools under `scripts/`. None of them affects the build; all are
conveniences for after adding songs and before a release. The first two never
edit files; `checkpaper.py` does only when asked with `--write`.

- [`checksongs.py`](#checksongspy--metadata) — metadata and text that will not
  render
- [`checkkeys.py`](#checkkeyspy--keys) — `key={}` versus the chords actually
  written
- [`checkpaper.py`](#checkpaperpy--paper-fit) — `pap={}` versus what actually
  fits on a page, and how the books lay the pages out

## `checksongs.py` — metadata

```bash
scripts/checksongs.py                    # report all issues across songs/
scripts/checksongs.py --missing tem      # only songs missing a tempo
scripts/checksongs.py --csv > meta.csv   # dump all metadata to a spreadsheet
scripts/checksongs.py songs/chords/Ayreon   # check one folder
```

| Option | Effect |
|---|---|
| `--all` | also list clean songs |
| `--missing FIELD[,…]` | report only songs missing those fields |
| `--no-orphans` | skip the unreferenced-song check |
| `--csv` | emit CSV of all metadata instead of a report |
| `--strict` | exit non-zero on warnings and orphans too |

Exit status: 0 clean, 1 errors (or warnings with `--strict`), 2 nothing to scan.

CI gates on the plain run, not `--strict` — see
[building.md](building.md#continuous-integration) for why. `--strict` is for a
deliberate cleanup pass, when you want the whole backlog to show up as failure.

### What it checks

**Metadata.** The required `by` key; recommended keys per song kind (`lang`,
`key`, `tem`, `tun` for chord songs, `key`/`tem` for instrumental tin-whistle
ones — `pap` is deliberately not among them, since a song that fits nothing
correctly has none); unknown keys, which are almost always typos; `lang` values outside the
recognised set; `pap` values outside the paper sizes the classes know, which
would silently match nothing; and structural damage such as a missing
`\endsong`. The tiers, the language list and the paper list are constants at
the top of the script — edit them when introducing a new language or paper.

**Orphans.** Songs under `songs/` that no project `\input`s, and so appear in no
songbook. Project files are comment-stripped first, so a song parked behind a
`%` counts as unreferenced — commenting a song out of every project is exactly
how songs go missing.

**Text that will not reach the PDF.** The books set text in Open Sans, which has
no arrow and no musical-accidental glyphs. LuaLaTeX does not fail on a missing
character: it logs *Missing character* and drops it, so the build stays green
while the character silently vanishes.

| Reported | Severity | Why |
|---|---|---|
| `→` and any U+2190–U+21FF, `♭`, `♯`, `♮` | error | no glyph in Open Sans, dropped silently |
| `\textrightarrow` | error | resolves through the text font, so it drops too |
| `\flat`, `\sharp` | warning | render, but not the way the chords do |
| `Bb`-style flat in `key={}` or `\[Bb…]` | warning | typesets as the literal letters |

`\rightarrow` and `$\rightarrow$` both *do* render — they resolve through the
math font — which is why the house spelling for a modulation is
`key={Cm\rightarrow C}`, with no space before the arrow (the space after is
TeX's control-word delimiter and is swallowed, so it prints tight on both
sides).

For accidentals the house rule is `songs`' own `\flt` and `\shrp` everywhere.
`\flt` sets `$\flat$` smaller and raised, and `\shrp` is a raised superscript
`#` rather than the musical ♯, so mixing them with the math-mode macros makes a
prelude's accidentals disagree with the printed chords. There is no natural
equivalent in `songs`, so `♮` has to be `$\natural$`. Inside a chord, write `&`
and `#`, which `songs` renders with the same glyphs.

## `checkkeys.py` — keys

Checks each song's `key={}` against the chords actually written, and proposes
one for songs that have none.

```bash
scripts/checkkeys.py                  # disagreements, most certain first
scripts/checkkeys.py --validate       # agreement stats over the whole database
scripts/checkkeys.py --missing        # propose a key for songs lacking one
scripts/checkkeys.py --all            # show every song, not just disagreements
scripts/checkkeys.py --explain PATH   # why a key was detected: scores and workings
scripts/checkkeys.py --parts PATH     # detect a key per song part
```

It is a heuristic helper, not an authority. Keys are genuinely ambiguous —
relative major/minor, modal songs, songs that modulate or end away from home —
so treat disagreements as *worth a look*, not *wrong*. It never edits files.
Current agreement with the database is 97 %; `--validate` is the regression
check after touching any of the rules below.

### Reaching sounding pitch

`key={}` names the key the song *sounds* in, so the written chords have to be
shifted before they can be scored:

- **`\transpose`** is applied the way `songs.sty` does it — see below.
- **`\capo{n}`** adds *n* semitones. The projects do not enable the `songs`
  `transposecapos` option, so capo is a separate axis and the `\[chord]` shapes
  are what you actually finger.
- **`tun={}`** counts only when the detuning is *uniform*: a half-step-down
  guitar transposes every shape you finger, so a fingered `Am` sounds `G♯m`. A
  drop tuning like `D A D G B E` retunes one string and the shapes still sound
  as written, so it shifts nothing. String names are read as English (B = B♮),
  which is how the corpus spells them even in Czech songs.
- **Note naming** follows `lang`: Czech and Slovak read H = B♮ and B = B♭.

### `\transpose` is block-scoped

`songs.sty` advances `\SB@transposefactor` without `\global`
(songs.sty:1806), and every song part is a TeX group
(`\SB@beginverse` opens `\vbox\bgroup\begingroup`, `\SB@endverse` closes it), so
a `\transpose` inside a part reverts at `\endverse`. Several in one part do add
up. One *outside* any part — typically right after `\beginsong` — stays in force
for the rest of the song, which is how a song gets printed at a pitch other than
the one it was transcribed in.

So the shift in force between parts is the song's home level, and a part
transposed away from it is a mid-song modulation. Since `key={}` leads with the
home key, only chords at the home level are scored; such songs are tagged
*(modulates)*.

### Replayed chords

A `^` marker replays the next chord a part memorised, and half the corpus writes
its chords once and repeats them with carets. Those are expanded — that is what
lets `--parts` see a part with no `\[chords]` of its own.

Replays feed the **per-part** view only, never the pooled chord count. A
repeated verse would otherwise multiply its progression by the repeat count,
scaling the chord-frequency term while the fixed cadence bonuses stay put, and
diluting the very signals that separate a key from its relative. Counting each
written progression once is measurably better: pooling replays costs 2 points of
corpus agreement.

The model of the registers mirrors [the package's](internals.md#chord-memory),
including the subtlety that `\memorize` repoints `\SB@creg` but not the replay
tail `\SB@ctail`, so a part whose own register is empty memorises into it while
its `^` markers still replay the default register. A `^` inside a `\chordsoff`
run is a no-op in TeX that this does not model, so a handful of carets in such
runs are read as replays that TeX skips.

### Scoring

All 24 keys are scored against the chord list:

| Signal | Score |
|---|---|
| chord is diatonic in the key | +1 per occurrence |
| right root, "wrong" quality (7th/sus/…) | +0.3 |
| out-of-key chord | −0.5 |
| song ends on the tonic | +6 |
| song starts on the tonic | +3 |
| tonic never appears | −4 |

The minor triad set includes the borrowed major V and major ♭VII common in folk
and pop. Widening it further — Dorian IV, Mixolydian ♭VII — measured
net-negative; modal songs ride the cadence bonus instead.

**Truncated reprises.** An abbreviated final chorus ("first line…", the rest
commented out) stops mid-phrase, so its last chord is not a cadence. A part
whose chord sequence is a strict prefix of a longer part of the same type *and*
whose text is elided with `...` is skipped when deciding what the song ends on;
the last complete part supplies the ending instead.

**Modulation from the parts.** The pooled chords are the wrong evidence for a
song that plays in more than one key, so two per-part signals can override them:
two parts of the same type that are the same progression at a different pitch
(the song writes its modulation out rather than using `\transpose` — then the
opening key is the one to name), or every part agreeing on a key on its own when
only the pooled set disagrees (a modal song whose pooled chords fit a
neighbouring key better). "Their detected keys differ" is deliberately *not* a
signal: verses commonly detect differently just from being short and ending on
different chords, and acting on it measured 4 songs fixed against 14 broken.

### Reading the output

Each disagreement carries a **margin**: how far the detected key outscored the
best of the stated ones, or the runner-up when nothing is stated. It is a score
gap, not a probability. Reports sort by it, so the top of the list is where the
chords least support what is written. A margin of 0 means the stated key scored
just as well and the sort merely broke a tie — reported as `tie` and kept as
quiet as a match. The gap grows with song length, so only compare margins
between songs of similar size.

`--parts` is the tool for a song that will not settle: it scores every part on
its own, which is what separates a verse's key from a chorus's, and pools by
part type because one verse is often too short to settle a key where four are
not. When the part types split cleanly into two unrelated keys, the report
suggests the compound key to write.

### Songs in two keys

A song whose parts sit in different keys names them all, home key first —
`key={Cm→C}` for a minor verse opening into a major refrain. Detecting any of
the listed keys counts as agreement; the finer verdicts (*relative*, *parallel*)
compare against the home key. `→`, `->`, `,` and `;` all separate. This is not
what `\transpose` marks: `\transpose` reprints the chords at a new pitch, while
a modulation like this leaves the printed chords alone and shifts where the
music comes to rest.

### Tin whistle songs

Skipped in directory scans: they are melody tabs with no `\[chords]` to check,
and their key is fixed by the tune's sharps and flats. Their `key` field reads
`<song key> (<whistle> whistle)`, where the parenthetical names the whistle the
tune is *playable on*, not the key. Pass such a file explicitly to analyse it
anyway; the parenthetical is stripped before comparison.

## `checkpaper.py` — paper fit

Every song is written for A4; a song is only usable in an A5 book if it *also*
fits A5, which usually takes tightening it by hand. The `pap={}` key records
which sizes a song has been checked on, and this script both reports the flags
and re-measures them. `--layout` goes one step further and asks the books
themselves where their songs came out.

```bash
scripts/checkpaper.py                     # which songs are marked for which paper
scripts/checkpaper.py --summary           # counts and the per-project check only
scripts/checkpaper.py --measure a5        # typeset everything on A5; what really fits
scripts/checkpaper.py --measure a5 --write  # ... and record the answer in the songs
scripts/checkpaper.py --layout            # build every book; check where its songs landed
```

| Option | Effect |
|---|---|
| `--summary` | counts and the project table, without the song lists |
| `--measure PAPER` | typeset every song on `PAPER` and compare with the flags |
| `--layout` | build every project and check the pages its songs came out on |
| `--write` | with `--measure`: write the measured result into the song files |
| `--keep` | keep the probe build directories for inspection |
| `-v` | echo LuaLaTeX's errors |
| `--strict` | exit non-zero on any disagreement |

### What `pap={}` means

`pap={a4,a5}` says the song fits **one page** of each size listed;
`pap={a5x2}` says it fits **two facing pages** of A5 — a spread, which is read
and played through without turning the page. Every size a song is known to fit
is written down, so **no key means none of them** — the state of a song too
long even for one A4 page, and of a song nobody has measured yet. There is no
second spelling of that: `--write` takes the key out rather than writing an
empty one. The build says so on every paper, which is what surfaces an
unmeasured song.

Only A5 has the `x2` spelling, because only its classes are two-sided.
`velkyzpevnik` is one-sided `article`, so nothing there puts the second page of
a song opposite the first, and a song needing two A4 pages still fits nothing —
which is what keeps the A4 build listing it.

Fitting is not the same as being *used*: a song marked `a5x2` is a song the
camp booklet *could* carry on a spread, not one it does.

Each `--measure` run only records the paper it measured, so a new song wants
both (`--measure a4 --write`, then `--measure a5 --write`) before its key is
the whole answer.

The paper a book is being typeset on is not declared anywhere — `zubuvzpevnik.sty`
reads it off `\paperwidth`/`\paperheight` at `\begin{document}`, after
`geometry` has had its say, and matches them against the `\zub@paperis` lines
there. So the name cannot drift from the paper option the class passed to
`\LoadClass`, and a new size needs one line in one place. A page that matches no
line warns once and turns the per-song check off, since there is nothing to
check against.

Every song whose `pap` does not list the paper being typeset gets a LaTeX
warning, with no way to opt out: building the camp book lists the songs nobody
has checked at that size, and building the A4 book lists the three that need
two pages there.

### How `--measure` decides

It typesets the whole database as one songbook, in the class for that paper and
with the options the projects pass (`chorded, onesongcolumn, noshading`), so
the measurement is the real layout — including the `\iflargepaper` branches a
song uses to shorten itself on small paper.

`\spenalty=-10000` starts every song on a fresh page, so no song can be
lengthened or shortened by its neighbours and a subset measures the same as the
whole. Song start pages come from the page numbers `songs` writes into the raw
index file (`obsah.sxd`), and the probe sets `\pagestyle{empty}` so that the
*blank* page a forced break sometimes leaves behind can be told apart from a
page the song really spilled onto; blank pages are not counted against a song.

The probe builds in a temporary directory with the repo's `tmp-ly` symlinked
in, so it shares the LilyPond cache with the real builds and a re-measure costs
no LilyPond runs.

It is a measurement, not an opinion: run against the 58 songs of the 2025 and
2026 camp books it reproduces those PDFs page for page, including the two songs
that take two pages there.

### Lines that do not fit either

A song line too wide for the column is not an error — TeX breaks it like any
other paragraph and sets the tail on a second line, with the chords still over
the words they belong to and the shape of the verse gone. Nothing is logged: an
overfull box only happens where TeX could not break at all.

So the probe asks TeX directly. `\SB@par`, which songs.sty ends every song line
with, is patched to look at `\prevgraf` — the number of lines the paragraph
just came out as — and to write down any line that came out as more than one.
A song with such a line **does not fit that paper**, however few pages it takes,
and `--write` takes the mark off. Two songs on A4 and 55 on A5 are in that
state today.

The report names the line: chorus lines are counted from the start of the
chorus rather than of the file, because `\insertchorus` replays the chorus from
its own captured source (see [internals.md](internals.md#source-capture)), which
is also why one wide chorus line is reported once however often it is printed.

The patch reports itself into the same file, so a `songs.sty` whose `\SB@par`
has changed shape fails the run instead of quietly measuring nothing.

### What `--layout` checks

Page counts say what a song needs; they do not say what the book gave it.
`--layout` builds every project the way its own `build.sh` does — one pass, in a
temporary directory, with no index files, which moves no song because the
hardback puts its indexes last and the camp booklet holds its front matter to
the two pages the class checks for itself — and then reads the book back:

- **A song on two pages has to sit on a spread.** `songs.sty` already arranges
  that in a two-sided book: it will not start a two-page song on a right-hand
  page. So this is a check that the arrangement held, not a demand.
- **No blank page between songs.** That is the price of the arrangement: when a
  two-page song comes up on a right-hand page, the package pushes it over and
  leaves the page behind empty. Nothing in the build says so, and the fix is
  never in the song — it is to move a one-page song earlier or later.
- **A song over two pages** is reported for information: no ordering of the book
  can spare it a page turn.

Two numbers have to be tied together for that, and neither is in the PDF text.
The page a song starts on comes from the index data file, in the page numbers
the book prints; which *sheet* that is does not follow from it, because a book
with a cover restarts the counter at its first song. So the run also records the
page counter of every sheet as it ships, in order, which pins the two together —
and the printed page style is forced back to plain numbers first, so a front
matter counted in roman numerals or letters cannot hide the number.

A song's own page count comes from the `--measure` probe rather than from the
book, since a book cannot say where a song stopped and its blank page began.
`--layout` therefore measures every paper its projects use before it starts.

It reproduces the real books: the 2025 camp booklet's two-page songs come out on
sheets 10–11 and 30–31, which is where they are in `tabor2025.pdf`.
