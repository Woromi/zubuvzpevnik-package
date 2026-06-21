# Song parts — implementation notes

These files customise the `songs` package's verse-based parts:

- `sloka.cfg` — per-part chord memory, the shared part core (`\zub@beginpart`), and the `\newSongPartType` factory (verse, bridge, intro, outro, prechorus).
- `instrumental.cfg` — the chords-only `instrumental` part.
- `refren.cfg` — the restyled chorus (documented in that file).

*How to use* the parts (`\usechords`/`\copychords`, the part list, etc.) is in the package `README.md` one level up. This file is the *why/how* for whoever maintains the code.

## Chord memory

The `songs` package memorises and replays chords through one shared register, `\SB@cr@`: inside `\beginverse` (songs.sty, ~line 1295) the first verse-based part in a song *memorises* its chords, and every later part *replays* them wherever you put `^` markers. Since all our parts are built on `\beginverse`/`verse*`, that single register means an instrumental's chords would leak into a later verse's `^` replay.

So each part **type** gets its own register:

- `\zub@newpartchords{name}` declares a register `SB@cr@<name>` once (via the package's `\newchords`) and records the name in `\zub@partnames`.
- `\zub@resetpartchords`, hooked into `\SB@@@beginsong`, empties every named register at the start of each song. The package resets only the default register (songs.sty:842), so without this a part's chords would leak across songs.
- `\zub@partchords{name}`, called from `\zub@beginpart` just after `\beginverse`, points the memory at that part's register — memorise if empty, replay otherwise — overriding the default-register choice songs.sty:1295 made.

Plain `\beginverse` keeps the package default register, which is also reachable under the name **`verse`** (`\SB@cr@verse` is `\let` to `\SB@cr@`) so it can be named in `\usechords`/`\copychords`.

## Bare `\memorize`

`\memorize` is redefined so the bracket-less form targets the current part's register (`\memorize[name]` is unchanged). So `\beginbridge\memorize` captures into the bridge register instead of silently into the default one. `\zub@currentpart` holds the current part name — empty in a plain verse and during songs.sty:1295 (which runs before `\zub@beginpart` sets it), so plain verses and the package's own internal call still hit the default register.

This is rendering-neutral: memorising chords does **not** affect the chord-split-word hyphens (those are a typesetting-time width decision, independent of which register is active).

## Sharing chords across parts

Both go *inside* a part and name a source part:

- `\usechords{source}` (= `\replay[source]`) — replay the source's chords in **this part only**.
- `\copychords{source}` — copy the source's register into the current part's register, then replay, so this part **and every later part of the same type** replay it. One `\copychords` on the first of a run of identical interludes covers them all.

## The part core: `\zub@beginpart` / `\zub@endpart`

`\zub@beginpart{name}{label}{indentEm}{setup}` starts a verse-based part: a numbered `\beginverse` followed by `\addtocounter{versenum}{-1}` so the part doesn't consume a verse number; `label` (bold) replaces the number in the slot and `indentEm` sets the slot width (the indent). An empty `label` shows no marker, giving the unnumbered look (intro/outro/instrumental) without a separate `verse*` path — the rollback is needed for the labelled parts (`bridge`/`prechorus`) anyway, so everything uses one mechanism. `setup` (arg 4) is extra body code, e.g. `\chordsonly`. It also records `\zub@currentpart` and calls `\zub@partchords` (see above). `\zub@endpart` closes the verse and the surrounding group.

## `\newSongPartType{name}{label}{indent}`

Signature `{O{} m m m}`: an optional `[setup]`, then name/label/indent. It declares the part's register and defines `\begin<name>`/`\end<name>` on the core, passing `[setup]` through as the body code.

- An empty `label` prints no marker (see `\printversenum`, which prints the trailing dot only for a non-empty label) — that is how `intro`/`outro`/`instrumental` get their unnumbered look; a non-empty label (`*`, `P`) sits in the number slot.
- `[setup]` runs in the part body — e.g. `\chordsonly`.

Built-in parts: `bridge`, `intro`, `outro`, `prechorus`, and `instrumental` (below).

## Chords-only parts (`\chordsonly`) and the instrumental

`\chordsonly` is a public part-body style — `\nolyrics` plus fixed-width chord boxes (width `\zub@chordwidth`, set via `\setchordwidth`). Passed as the `[setup]` of `\newSongPartType`, it makes any part type chords-only, so `solo`, a song-specific break, etc. all get the instrumental look:

```latex
\newSongPartType[\chordsonly]{solo}{}{0}
```

The built-in instrumental is exactly `\newSongPartType[\chordsonly]{instrumental}{}{0}`. `\begin{instrumental}` is kept as an alias — `\let\instrumental\begininstrumental` — so `\begin` runs `\instrumental` and `\end` runs the factory's `\endinstrumental` (which `\newSongPartType` defines with `\NewDocumentCommand`, since `\newcommand` refuses names starting with `end`). Aliasing rather than `\newenvironment` avoids redefining that `\endinstrumental`.

There is **no `\ifchorded` guard**: a chords-only part in a `lyric` build simply renders empty (chords suppressed). The old guard wrapped only the verse, not its `\[...]` body, so in `lyric` mode the orphaned `\[` started display math and errored — dropping it fixes that.
