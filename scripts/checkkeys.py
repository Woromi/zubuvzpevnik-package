#!/usr/bin/env python3
"""Sanity-check song keys against the actual chords, and propose missing ones.

The `key={}` field names the key the song actually *sounds* in: the chord shapes
you finger, shifted by any *global* \\transpose, by the \\capo amount, and by the
\\tun{} tuning. This script extracts every \\[chord], applies \\transpose the way
songs.sty does (cumulative, reset per \\beginsong), then the capo and tuning, plus
the song's note-naming convention (Czech/Slovak use H=B-natural, B=B-flat), then
infers the most likely key from the chord progression and compares it to what is
written.

Tuning: a uniformly detuned guitar shifts every chord you finger. tun={E\\flat
A\\flat D\\flat G\\flat B\\flat E\\flat} (or "Half-step down") lowers everything a
semitone, so fingered Am sounds G#m. Only a *uniform* shift counts -- drop
tunings like tun={D A D G B E} change one string, and the shapes still sound at
their written pitch, so they shift nothing. String names are read as English
(B=B-natural) regardless of lang, which is how the corpus writes them.

Modulations: a \\transpose *before the first chord* is a global shift and applies
to the whole song; a \\transpose *after* chords have started is a mid-song key
change (a bridge, or a verse that climbs a semitone). Detection uses only the
chords at the song's initial transposition level so the home key still resolves;
such songs are tagged "(modulates)". (\\[chord] replays via ^ in a transposed
section are invisible to a text scan, so a modulation may sound bigger than the
chords we can see.)

Truncated reprises: an abbreviated final chorus ("first line...", rest commented
out) ends mid-phrase, so its last chord is not a cadence. Such a part -- chord
sequence a strict prefix of a longer part of the same type, and text elided with
"..." -- is skipped when deciding what chord the song ends on; the last complete
part supplies the ending instead.

Tinwhistle songs are skipped in directory scans: they are melody tabs with no
\\[chords] to check, and their key is fixed by the tune's sharps/flats. Their key
field reads "<song key> (<whistle> whistle)" -- the parenthetical names the
whistle the tune is *playable on*, not the key. (Pass such a file explicitly to
analyze it anyway; the parenthetical is then stripped before comparison.)

Songs in two keys: a song whose parts sit in different keys names them all,
home key first -- key={Cm → C} for a minor verse opening into a major refrain.
Detecting any of the listed keys counts as agreement; the finer verdicts
(relative / parallel) compare against the home key. → / -> / , / ; all separate.
This is *not* what \\transpose marks: \\transpose reprints the chords at a new
pitch, while a modulation like this leaves the printed chords alone and shifts
where the music comes to rest.

Certainty: reports are sorted by "margin" -- how far the detected key outscores
the best of the stated ones (for --missing, how far the proposal outscores the
runner-up).
It is a score gap, not a probability. A large margin means the chords barely
support what is written; a margin of 0 means the two keys tied and the sort broke
it arbitrarily, so the disagreement says nothing. The gap also grows with song
length, so compare margins between songs of similar size.

It is a heuristic helper, not an authority: keys are genuinely ambiguous
(relative major/minor, modal songs, songs that modulate or end away from home),
so treat disagreements as "worth a look," not "wrong." It never edits files.

Usage:
    scripts/checkkeys.py [PATH ...]      # report (default: songs/chords)
    scripts/checkkeys.py --validate      # agreement stats vs. existing keys
    scripts/checkkeys.py --missing       # only propose keys for songs lacking one
    scripts/checkkeys.py --all           # show every song, not just disagreements
    scripts/checkkeys.py --explain PATH  # show why a key is detected (the workings)
    scripts/checkkeys.py --parts PATH    # detect a key per song part (spot modulations)
"""

import argparse
import os
import re
import signal
import sys
from collections import Counter
from pathlib import Path

NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Note letter -> semitone (pitch class). German/Czech naming swaps B and H.
NOTE_EN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
NOTE_DE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 10, "H": 11}

CAPO_RE = re.compile(r"\\capo\{(\d+)\}")
TUN_RE = re.compile(r"tun=\{([^}]*)\}")
# A key={} field may name several keys when the song modulates: "Cm -> C".
KEY_SPLIT_RE = re.compile(r"\s*(?:→|->|/|,|;)\s*")
# Standard guitar tuning, low to high, as pitch classes.
STANDARD_TUNING = [4, 9, 2, 7, 11, 4]          # E A D G B E
# Tunings spelled out in words rather than as string names.
NAMED_TUNINGS = {"standard": 0, "half-step down": -1, "half step down": -1,
                 "whole-step down": -2, "whole step down": -2}
# Song part types, as \beginverse...\endverse or \begin{verse}...\end{verse}.
# Songs may add their own with \newSongPartType; load() picks those up too.
PART_TYPES = {"verse", "chorus", "prechorus", "recprechorus", "bridge", "bridgeb",
              "intro", "outro", "instrumental"}
NEW_PART_RE = re.compile(r"\\newSongPartType\{([a-zA-Z]+)\}")
# A single ordered scan: \transpose{n}, \[chord], or a song part boundary.
# Scanning them in document order lets us apply the cumulative \transpose to only
# the chords that follow it, the way songs.sty does, and lets us group chords by
# the part they sit in (needed to spot truncated reprises).
TOKEN_RE = re.compile(
    r"\\transpose\*?\{([+-]?\d+)\}"              # 1: transpose
    r"|\\\[([^\]]*)\]"                           # 2: chord
    r"|\\begin(?:\{([a-zA-Z]+)\}|([a-zA-Z]+))"   # 3/4: part opens (env / macro form)
    r"|\\end(?:\{([a-zA-Z]+)\}|([a-zA-Z]+))"     # 5/6: part closes
)


def parse_note(tok, german):
    """Read a note + accidentals from the start of tok.
    Returns (pitch_class, rest_of_string) or (None, tok) if not a note."""
    if not tok:
        return None, tok
    table = NOTE_DE if german else NOTE_EN
    letter = tok[0].upper()
    if letter not in table:
        return None, tok
    pc = table[letter]
    i = 1
    while i < len(tok):
        if tok[i] == "#":
            pc += 1; i += 1
        elif tok[i] in "&":
            pc -= 1; i += 1
        elif tok.startswith("\\shrp", i) or tok.startswith("\\sharp", i):
            pc += 1; i += len("\\shrp") if tok.startswith("\\shrp", i) else len("\\sharp")
        elif tok.startswith("\\flat", i) or tok.startswith("\\flt", i):
            pc -= 1; i += len("\\flat") if tok.startswith("\\flat", i) else len("\\flt")
        else:
            break
    return pc % 12, tok[i:]


def is_minor(quality):
    q = quality.strip().lstrip("\\").strip()
    if q.startswith("maj") or q.startswith("Maj") or q.startswith("M"):
        return False
    if q.startswith("dim") or q.startswith("min"):
        return True
    return q[:1] == "m"


def parse_chord(tok, german):
    """Parse a \\[...] token to (root_pc, is_minor) or None."""
    tok = tok.strip().replace("\\ ", " ").strip()
    if not tok:
        return None
    tok = tok.split("/")[0].strip()           # drop slash bass
    tok = re.sub(r"\\[a-zA-Z]+\s*$", "", tok)  # trailing macro junk
    pc, rest = parse_note(tok, german)
    if pc is None:
        return None
    return (pc, is_minor(rest))


def parse_tuning(val):
    """Semitone shift a tuning applies to every chord shape, or 0.

    A uniformly detuned guitar transposes everything you finger; a drop tuning
    retunes one string and leaves the shapes sounding as written. String names
    are read as English (B=B-natural), which is how the corpus spells them even
    in Czech songs."""
    if val is None:
        return 0
    name = " ".join(val.replace("\\", " ").split()).lower()
    if name in NAMED_TUNINGS:
        return NAMED_TUNINGS[name]
    notes = []
    for tok in val.split():
        pc, rest = parse_note(tok, german=False)
        if pc is None or rest.strip():
            return 0                    # not a plain list of string names
        notes.append(pc)
    if len(notes) != len(STANDARD_TUNING):
        return 0
    shifts = {(n - s + 6) % 12 - 6 for n, s in zip(notes, STANDARD_TUNING)}
    return shifts.pop() if len(shifts) == 1 else 0   # uniform shift only


def parse_key_field(val, german):
    """Parse one key name to (tonic_pc, is_minor) or None."""
    val = val.strip()
    if not val:
        return None
    pc, rest = parse_note(val, german)
    if pc is None:
        return None
    return (pc, is_minor(rest))


def parse_key_fields(val, german):
    """Parse a key={} value to the list of keys it names, in order. A song that
    modulates lists them all ("Cm -> C"); the first is the home key. Ignores a
    trailing '(... whistle)' annotation."""
    val = re.sub(r"\(.*?\)", "", val).replace("\\ ", " ")   # \  is an escaped space
    val = re.sub(r"\\(?:textrightarrow|rightarrow|to)\b", "→", val).replace("$", " ")
    specs = [parse_key_field(part, german) for part in KEY_SPLIT_RE.split(val)]
    return [s for s in specs if s]


def key_names(specs):
    """Render every key a field names, e.g. "Cm→C" for a modulating song."""
    return "→".join(key_name(s) for s in specs) if specs else "?"


def key_name(spec):
    if spec is None:
        return "?"
    pc, minor = spec
    return NAMES_SHARP[pc] + ("m" if minor else "")


def load(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    text = strip_comments(text)
    german = bool(re.search(r"lang=\{(czech|slovak)\}", text))
    capo_m = CAPO_RE.search(text)
    capo = int(capo_m.group(1)) if capo_m else 0
    tun_m = TUN_RE.search(text)
    tuning = parse_tuning(tun_m.group(1) if tun_m else None)
    key_m = re.search(r"key=\{([^}]*)\}", text)
    stated_raw = key_m.group(1) if key_m else None
    stated_all = parse_key_fields(stated_raw, german) if stated_raw else []
    # Songs may define extra part types; without them the parts below come out
    # empty and the ending chord falls back to the last chord in the file.
    part_types = PART_TYPES | set(NEW_PART_RE.findall(text))
    # Walk chords and \transpose in document order.
    #
    # \transpose is BLOCK-SCOPED, not cumulative over the song: songs.sty advances
    # \SB@transposefactor without \global (songs.sty:1806) and every song part is a
    # TeX group (\SB@beginverse opens \vbox\bgroup\begingroup, \SB@endverse closes
    # it), so a \transpose inside a part reverts at \endverse. Several \transpose in
    # one part do add up. One outside any part -- typically right after \beginsong --
    # stays in force for the rest of the song, which is how a song gets printed at a
    # pitch other than the one it was transcribed in.
    #
    # So `song_level` is the shift in force between parts, and a part transposed away
    # from it is a mid-song modulation. The key={} field leads with the home key, so
    # we keep only the chords at the home level and skip the modulated parts (else a
    # song that climbs a semitone each verse would look keyless). \capo and the
    # tuning are added later, in analyze(), to reach the sounding pitch: the projects
    # do not enable songs' transposecapos option, so both are separate axes and the
    # \[chord] shapes are what you actually finger.
    song_level = 0            # shift in force outside any part
    level = 0                 # shift in force right now
    in_part = False
    home = None               # song_level when the first chord turned up
    modulates = False
    chords = []
    parts = []                # (part type, chords in it, text elided with "...")
    cur, start, cur_level = [], None, 0
    for m in TOKEN_RE.finditer(text):
        if m.group(1) is not None:
            level += int(m.group(1))
            if in_part:
                if level != song_level:
                    modulates = True      # this part is played in another key
            else:
                song_level = level        # persists until \endsong
                if home is not None:
                    modulates = True      # the song re-pitches partway through
            continue
        if m.group(2) is not None:
            c = parse_chord(m.group(2), german)
            if c:
                pc, minor = c
                if home is None:
                    home = level
                if not cur:
                    cur_level = level         # the level this part plays at
                cur.append(((pc + level) % 12, minor))
                if level == home:
                    chords.append(cur[-1])
                else:
                    modulates = True
                # chords in modulated parts stay out of the detection pool, but
                # the part still gets recorded so --parts can show it
            continue
        if (m.group(3) or m.group(4)) in part_types:
            cur, start, cur_level = [], m.end(), song_level
            in_part, level = True, song_level      # the part opens a TeX group
        elif (m.group(5) or m.group(6)) in part_types:
            if cur:
                body = text[start:m.start()] if start is not None else ""
                parts.append((m.group(5) or m.group(6), tuple(cur),
                              "..." in body or "…" in body, cur_level))
            cur, start = [], None
            in_part, level = False, song_level     # ...and closing it reverts
    return {
        "german": german, "capo": capo, "tuning": tuning,
        "transpose": home if home is not None else song_level,
        "modulates": modulates, "stated_raw": stated_raw,
        "stated_all": stated_all,
        "stated": stated_all[0] if stated_all else None,   # the home key
        "chords": chords, "parts": parts,
    }


def strip_comments(text):
    out = []
    for line in text.splitlines(keepends=True):
        i, cut = 0, None
        while i < len(line):
            if line[i] == "\\":
                i += 2; continue
            if line[i] == "%":
                cut = i; break
            i += 1
        out.append(line if cut is None else line[:cut] + ("\n" if line.endswith("\n") else ""))
    return "".join(out)


# Diatonic triads as (interval_from_tonic, is_minor) for major and minor keys.
# Minor includes the borrowed major V and major VII common in folk/pop.
MAJOR_TRIADS = {(0, False), (2, True), (4, True), (5, False), (7, False), (9, True)}
MINOR_TRIADS = {(0, True), (3, False), (5, True), (7, True), (8, False), (10, False), (7, False)}


def is_truncated_reprise(i, parts):
    """True if parts[i] is an abbreviated repeat: its chords are a strict prefix
    of a longer part of the same type, and its text trails off in "...". Such a
    part stops mid-phrase, so its final chord is not a cadence."""
    kind, chords, elided = parts[i]
    if not elided:
        return False
    return any(k == kind and len(c) > len(chords) and c[:len(chords)] == chords
               for j, (k, c, _) in enumerate(parts) if j != i)


def ending_chord(parts, fallback):
    """The chord the song really ends on: the final chord of the last part that
    is not a truncated reprise. Falls back to the last chord seen."""
    for i in range(len(parts) - 1, -1, -1):
        if not is_truncated_reprise(i, parts):
            return parts[i][1][-1]
    return fallback


def score_keys(sounding, last=None):
    """Score all 24 keys against the chord list. Returns [(score, spec), ...]
    sorted best-first. spec is (tonic_pc, is_minor). `last` is the chord the song
    ends on (default: the last one seen). This is the heart of the heuristic;
    --explain prints the top of this list so the ranking is visible."""
    freq = Counter(sounding)
    roots = {pc for pc, _ in sounding}
    first = sounding[0]
    if last is None:
        last = sounding[-1]
    scored = []
    for tonic in range(12):
        for minor in (True, False):
            triads = MINOR_TRIADS if minor else MAJOR_TRIADS
            diatonic = {((tonic + iv) % 12, mn) for iv, mn in triads}
            diatonic_roots = {(tonic + iv) % 12 for iv, _ in triads}
            score = 0.0
            for chord, n in freq.items():
                if chord in diatonic:
                    score += n
                elif chord[0] in diatonic_roots:
                    score += 0.3 * n      # right root, "wrong" quality (7th/sus/etc.)
                else:
                    score -= 0.5 * n      # out-of-key chord
            tonic_chord = (tonic, minor)
            if last == tonic_chord:
                score += 6                 # songs usually end on the tonic
            if first == tonic_chord:
                score += 3                 # ...and often start on it
            if tonic not in roots:
                score -= 4                 # tonic should appear somewhere
            scored.append((score, tonic_chord))
    scored.sort(key=lambda x: -x[0])
    return scored


def detect_key(sounding, last=None):
    """sounding: list of (pc, is_minor). Returns (tonic_pc, is_minor) or None."""
    if not sounding:
        return None
    return score_keys(sounding, last)[0][1]


def relative(spec):
    """Relative major<->minor of a key spec. Relative major sits 3 semitones
    above the minor tonic (Am->C); relative minor 3 below the major (C->Am)."""
    pc, minor = spec
    return ((pc + 3) % 12, False) if minor else ((pc - 3) % 12, True)


def classify(stated_all, detected):
    """stated_all: every key the field names (a modulating song lists more than
    one). Detecting any of them is agreement; the finer verdicts compare against
    the home key."""
    if detected is None:
        return "no-chords"
    if not stated_all:
        return "propose"
    if detected in stated_all:
        return "match"
    # The near-misses are tested against every named key, not just the home one:
    # in a song that modulates, the detector may well land on the relative of the
    # section it liked best rather than of the key the song opens in.
    if any(detected == relative(k) for k in stated_all):
        return "relative"
    if any(k[0] == detected[0] for k in stated_all):
        return "parallel"          # same root, major/minor flip
    return "mismatch"


def margin(scored, stated_all, detected):
    """How far the detected key beats what it is being compared against: the best
    of the stated keys, or the runner-up when nothing is stated. It is the score
    gap, not a probability -- 0 means the detector had no real preference (a coin
    flip, so the disagreement means nothing), and it grows with both the strength
    of the evidence and the length of the song. Never negative: when the detected
    key came from the parts rather than the pooled ranking it can score below the
    stated one, and that is not a disagreement worth ranking."""
    if not scored:
        return None
    if not stated_all:
        return scored[0][0] - scored[1][0] if len(scored) > 1 else 0.0
    ours = [score for score, spec in scored if spec == detected]
    theirs = [score for score, spec in scored if spec in stated_all]
    if not ours or not theirs:
        return None
    return max(0.0, ours[0] - max(theirs))


def analyze(path):
    d = load(path)
    sounds = d["capo"] + d["tuning"]        # fingered shapes -> sounding pitch
    shift = lambda seq: [((pc + sounds) % 12, mn) for pc, mn in seq]
    sounding = shift(d["chords"])
    d["sounding"] = sounding
    # Only home-level parts can supply the ending: the key={} field leads with the
    # home key, so a part transposed away from it must not decide the cadence.
    home_parts = [(kind, tuple(shift(c)), elided)
                  for kind, c, elided, lvl in d["parts"] if lvl == d["transpose"]]
    d["ending"] = ending_chord(home_parts, sounding[-1]) if sounding else None
    d["scored"] = score_keys(sounding, d["ending"]) if sounding else []
    detected = d["scored"][0][1] if d["scored"] else None
    # The pooled chords are the wrong evidence for a song that plays in more than
    # one key; when the parts say so, they decide instead.
    d["modulation"] = None
    if detected is not None:
        spec, why = modulation_key(d)
        if spec is not None and spec != detected:   # only when it changes the answer
            d["modulation"] = why
            detected = spec
    d["margin"] = margin(d["scored"], d["stated_all"], detected)
    cls = classify(d["stated_all"], detected)
    return d, detected, cls


def best_shift(a, b):
    """(semitones, agreement) for the transposition of `a` that best lines up with
    `b`, comparing position by position over the shorter of the two."""
    n = min(len(a), len(b))
    if n < 4:
        return 0, 0.0
    best = (0, 0.0)
    for k in range(12):
        hits = sum(1 for i in range(n) if ((a[i][0] + k) % 12, a[i][1]) == b[i])
        if hits / n > best[1]:
            best = (k, hits / n)
    return best


# How much of two parts must line up under one shift to call it the same
# progression moved. Chosen by measuring the corpus: at this level the test fires
# only on songs that really do replay a section at another pitch.
RATCHET_MATCH = 0.8


def modulation_key(d):
    """The home key of a song whose parts are not all in the same key, or None.

    Two signals, both meaning "the per-part evidence beats the pooled chords":

    A song that modulates by writing its chords out at rising pitches -- rather
    than with \\transpose -- pools into a chord set that is a mixture of keys and
    represents none of them (Ruze z Texasu pools to A#m, a key no part of it is
    in). The giveaway is structural: two parts of the same type are the same
    progression at a different pitch. The key to name is then the opening one.

    Separately, if every part on its own agrees on a key and only the pooled set
    disagrees, the parts win -- that is a modal song whose pooled chords fit a
    neighbouring key better (Ho Ho Watanay: eight parts all D, pooled says G).

    Returns (spec, reason) or (None, None). Note "their detected keys differ" is
    NOT a usable signal: verses commonly detect differently just from being short
    and ending on different chords, and acting on that loses far more than it
    gains (measured: 4 songs fixed, 14 broken)."""
    ps = part_keys(d, with_chords=True)
    if len(ps) < 2:
        return None, None
    by = {}
    for kind, spec, snd in ps:
        by.setdefault(kind, []).append(snd)
    for kind, seqs in by.items():
        for i in range(len(seqs)):
            for j in range(i + 1, len(seqs)):
                k, frac = best_shift(seqs[i], seqs[j])
                if k != 0 and frac >= RATCHET_MATCH:
                    first = ps[0][2]
                    return (score_keys(first, first[-1])[0][1],
                            f"{kind} replayed {k:+d} semitones ({frac:.0%} of chords line up)"
                            " -> the chords span several keys; naming the opening one")
    specs = {spec for _, spec, _ in ps}
    if len(specs) == 1:
        return specs.pop(), f"all {len(ps)} parts agree on this key on their own"
    return None, None


def part_keys(d, with_chords=False):
    """Best key for each song part on its own, as [(kind, spec), ...] -- or
    [(kind, spec, chords)] with with_chords."""
    sounds = d["capo"] + d["tuning"]
    out = []
    for kind, chords, elided, lvl in d["parts"]:
        snd = [((pc + lvl - d["transpose"] + sounds) % 12, mn) for pc, mn in chords]
        if snd:
            spec = score_keys(snd, snd[-1])[0][1]
            out.append((kind, spec, snd) if with_chords else (kind, spec))
    return out


def shifts_note(d):
    """The chain that turns fingered shapes into sounding pitch, as text."""
    bits = []
    if d["transpose"]:
        bits.append(f"transpose {d['transpose']:+d}")
    if d["capo"]:
        bits.append(f"capo +{d['capo']}")
    if d["tuning"]:
        bits.append(f"tuning {d['tuning']:+d}")
    return " + ".join(bits) if bits else "none"


def parts_report(path, repo):
    """Detect a key for each song part on its own. Two sections that disagree is
    what a modulation looks like from the chords -- and the chord that is foreign
    to the other section's key is what makes the split decidable."""
    d, detected, cls = analyze(path)
    sounds = d["capo"] + d["tuning"]
    print(os.path.relpath(path, repo))
    print(f"  stated key : {d['stated_raw'] or '-'}  ({key_names(d['stated_all'])})")
    print(f"  shift      : {shifts_note(d)}  (fingered chords -> sounding pitch)")
    print(f"  whole song : {key_name(detected)}  [{cls}]")
    if not d["parts"]:
        print("  no song parts with chords found\n")
        return
    print(f"  {'#':>2}  {'part':<20} {'n':>3}  {'chords (sounding)':<44}  best keys for that part")
    for i, (kind, chords, elided, lvl) in enumerate(d["parts"]):
        snd = [((pc + lvl - d["transpose"] + sounds) % 12, mn) for pc, mn in chords]
        label = kind
        if lvl != d["transpose"]:
            label += f" {lvl - d['transpose']:+d}"
        if elided:
            label += " (reprise)"
        seq = " ".join(key_name(c) for c in snd)
        if len(seq) > 44:
            seq = seq[:43] + "…"
        top = "   ".join(f"{key_name(s)} {sc:.0f}" for sc, s in score_keys(snd, snd[-1])[:3])
        print(f"  {i:>2}  {label:<20} {len(snd):>3}  {seq:<44}  {top}")
    # Pooling each part type is what separates a verse key from a chorus key when
    # any single part is too short to score reliably.
    kinds = sorted({k for k, _, _, _ in d["parts"]})
    if len(kinds) > 1 or len(d["parts"]) > len(kinds):
        print("  pooled by part type:")
        for kind in kinds:
            pool = [((pc + lvl - d["transpose"] + sounds) % 12, mn)
                    for k, cs, _, lvl in d["parts"] if k == kind for pc, mn in cs]
            if not pool:
                continue
            hist = "  ".join(f"{key_name(c)}×{n}" for c, n in Counter(pool).most_common(5))
            top = "   ".join(f"{key_name(s)} {sc:.1f}" for sc, s in score_keys(pool, pool[-1])[:3])
            print(f"    {kind:<14} ({len(pool):>3})  {hist:<40}  -> {top}")
    print()


def explain(path, repo):
    """Print the detector's reasoning for one song: the shifts applied, the
    chords it sees, and the ranked key candidates with scores."""
    d, detected, cls = analyze(path)
    print(os.path.relpath(path, repo))
    shift = []
    if d["transpose"]:
        shift.append(f"transpose {d['transpose']:+d}")
    if d["capo"]:
        shift.append(f"capo +{d['capo']}")
    if d["tuning"]:
        shift.append(f"tuning {d['tuning']:+d}")
    naming = "Czech/Slovak (H=B♮, B=B♭)" if d["german"] else "English (B=B♮)"
    print(f"  stated key : {d['stated_raw'] or '-'}  ({key_names(d['stated_all'])})")
    print(f"  note naming: {naming}")
    print(f"  shift      : {' + '.join(shift) if shift else 'none'}  (fingered chords -> sounding pitch)")
    if d["modulates"]:
        print("  modulates  : mid-song \\transpose found -> detecting the HOME key only")
    if d["modulation"]:
        print(f"  parts      : {d['modulation']}")
    sounding = d["sounding"]
    if not sounding:
        print("  no chords found -> cannot detect a key\n")
        return
    freq = Counter(sounding)
    hist = "  ".join(f"{key_name(c)}×{n}" for c, n in freq.most_common())
    ends_on = f"ends on {key_name(d['ending'])}"
    if d["ending"] != sounding[-1]:
        ends_on += f"  (last part is a truncated reprise stopping on {key_name(sounding[-1])})"
    print(f"  first chord: {key_name(sounding[0])}    last chord: {key_name(sounding[-1])}")
    print(f"  cadence    : {ends_on}")
    print(f"  chords     : {hist}")
    print("  best key candidates (higher score = better fit of chords + first/last):")
    for score, spec in score_keys(sounding, d["ending"])[:4]:
        marker = " <- detected" if spec == detected else ""
        rel = key_name(relative(spec))
        kind = "minor" if spec[1] else "major"
        relkind = "major" if spec[1] else "minor"
        print(f"      {key_name(spec):<4} {kind:<5} score {score:6.1f}   relative {relkind}: {rel}{marker}")
    gap = "" if d["margin"] is None else f"  margin {d['margin']:.1f}"
    print(f"  verdict    : detected {key_name(detected)} vs stated {key_names(d['stated_all'])}"
          f"{gap}  [{cls}]\n")


def main():
    # Die quietly when piped into head/less instead of dumping a traceback.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--validate", action="store_true", help="agreement stats only")
    ap.add_argument("--missing", action="store_true", help="only songs without a key")
    ap.add_argument("--all", action="store_true", help="show every song")
    ap.add_argument("--explain", action="store_true", help="show the detector's reasoning")
    ap.add_argument("--parts", action="store_true", help="detect a key per song part")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    scan = args.paths if args.paths else [repo / "songs" / "chords"]
    files = []
    for p in scan:
        p = Path(p)
        if p.is_dir():
            # Skip tinwhistle melody tabs: no \[chords] to check (pass a file
            # explicitly to analyze it anyway).
            files += [f for f in sorted(p.rglob("*.tex")) if "tinwhistle" not in f.parts]
        else:
            files += [p]

    if args.explain:
        for f in files:
            explain(f, repo)
        return 0

    if args.parts:
        for f in files:
            parts_report(f, repo)
        return 0

    rows = []
    for f in files:
        d, detected, cls = analyze(f)
        rows.append((f, d, detected, cls))

    if args.validate:
        counts = Counter(cls for _, _, _, cls in rows)
        graded = [r for r in rows if r[3] not in ("propose", "no-chords")]
        agree = sum(1 for r in graded if r[3] in ("match", "relative"))
        print("Agreement vs. existing keys (chord-based detector):")
        for cls in ("match", "relative", "parallel", "mismatch", "propose", "no-chords"):
            print(f"  {cls:<10} {counts.get(cls, 0)}")
        if graded:
            print(f"\n  match+relative = {agree}/{len(graded)} = {100*agree/len(graded):.0f}% of keyed songs")
        return 0

    # Strongest disagreements first: the ones where the chords least support the
    # stated key are the ones worth opening. A margin of 0 is a tie the sort
    # broke arbitrarily, so those land at the bottom, next to the matches.
    rows.sort(key=lambda r: (-(r[1]["margin"] or 0), os.path.relpath(r[0], repo)))

    for f, d, detected, cls in rows:
        rel = os.path.relpath(f, repo)
        if args.missing:
            if cls == "propose":
                print(f"{rel}\n  propose key={{{key_name(detected)}}}  (margin {d['margin']:.1f} over"
                      f" {key_name(d['scored'][1][1])}, capo {d['capo']}, {len(d['chords'])} chords)")
                if d["modulation"]:
                    seq = " ".join(f"{k}:{key_name(s)}" for k, s in part_keys(d))
                    print(f"    {d['modulation']}\n    parts: {seq}")
            continue
        if not args.all and cls in ("match", "no-chords"):
            continue
        tag = {"relative": "rel. maj/min", "parallel": "MAJ/MIN FLIP",
               "mismatch": "MISMATCH", "propose": "MISSING", "match": "ok"}.get(cls, cls)
        shift = f"  capo={d['capo']}"
        if d["tuning"]:
            shift += f"  tuning={d['tuning']:+d}"
        if d["transpose"]:
            shift += f"  transpose={d['transpose']:+d}"
        if d["modulates"]:
            shift += "  (modulates)"
        if d["modulation"]:
            shift += "  (key from parts)"
        gap = "" if d["margin"] is None else f"  margin={d['margin']:.1f}"
        print(f"{rel}")
        print(f"  stated={{{d['stated_raw'] or '-'}}}={key_names(d['stated_all'])}  detected={key_name(detected)}"
              f"{gap}{shift}  [{tag}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
