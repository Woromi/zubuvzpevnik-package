#!/usr/bin/env python3
"""Sanity-check song keys against the actual chords, and propose missing ones.

Extracts every \\[chord], brings it to sounding pitch (\\transpose, \\capo, tun),
expands ^ replays, scores all 24 keys and compares the winner to what is written.

A heuristic helper, not an authority: keys are genuinely ambiguous, so treat
disagreements as "worth a look", not "wrong". It never edits files. How every
rule below was chosen, and how to read the output: docs/tools.md

Usage: scripts/checkkeys.py [--validate|--missing|--all|--explain|--parts] [PATH ...]
"""

import argparse
import os
import re
import signal
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from songfile import songbook_root, strip_comments  # noqa: E402

NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Note letter -> semitone (pitch class). German/Czech naming swaps B and H.
NOTE_EN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
NOTE_DE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 10, "H": 11}

CAPO_RE = re.compile(r"(?:\\capo|\bcap=)\{(\d+)\}")
TUN_RE = re.compile(r"tun=\{([^}]*)\}")
LARGEPAPER_RE = re.compile(r"\\iflargepaper(.*?)(?:\\else.*?)?\\fi", re.S)
# A key={} field may name several keys when the song modulates: "Cm -> C".
KEY_SPLIT_RE = re.compile(r"\s*(?:→|->|/|,|;)\s*")
# Standard guitar tuning, low to high, as pitch classes.
STANDARD_TUNING = [4, 9, 2, 7, 11, 4]          # E A D G B E
# Tunings spelled out in words rather than as string names.
NAMED_TUNINGS = {"standard": 0, "half-step down": -1, "half step down": -1,
                 "whole-step down": -2, "whole step down": -2}
# The register a plain \beginverse uses; sloka.cfg also names it "verse".
DEFAULT_REGISTER = "verse"
# Part types; load() also picks up any the song adds with \newSongPartType.
PART_TYPES = {"verse", "chorus", "prechorus", "bridge",
              "intro", "interlude", "outro", "instrumental"}
NEW_PART_RE = re.compile(r"\\newSongPartType\*?(?:\[[^\]]*\])?\{([a-zA-Z]+)\}")
# One ordered scan, so \transpose applies only to the chords that follow it.
TOKEN_RE = re.compile(
    r"\\transpose\*?\{([+-]?\d+)\}"                 # 1: transpose
    r"|\\\[([^\]]*)\]"                              # 2: chord
    r"|\\begin(?:\{([a-zA-Z]+)\}|([a-zA-Z]+))"      # 3/4: part opens (env / macro form)
    r"|\\end(?:\{([a-zA-Z]+)\}|([a-zA-Z]+))"        # 5/6: part closes
    r"|\\(usechords|copychords)\{([a-zA-Z]+)\}"     # 7/8: replay another register
    r"|(\^)"                                        # 9: replay the next chord
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
    pc, rest = parse_note(tok, german)
    if pc is None:
        return None
    # Stripped after the root, or it would eat a macro accidental (\[C\shrp])
    rest = re.sub(r"\\[a-zA-Z]+\s*$", "", rest)
    return (pc, is_minor(rest))


def parse_tuning(val, german=False):
    """Semitone shift a tuning applies to every chord shape, or 0 for a drop
    tuning. String names follow the song's naming, as chord names do: in a
    Czech song B is B-flat and H is B-natural (checksongs.py enforces it)."""
    if val is None:
        return 0
    name = " ".join(val.replace("\\", " ").split()).lower()
    if name in NAMED_TUNINGS:
        return NAMED_TUNINGS[name]
    notes = []
    for tok in val.split():
        pc, rest = parse_note(tok, german=german)
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
    """Keys a key={} value names, home key first. Ignores "(... whistle)"."""
    val = re.sub(r"\(.*?\)", "", val).replace("\\ ", " ")   # \  is an escaped space
    val = re.sub(r"\\(?:textrightarrow|rightarrow|to)\b", "→", val).replace("$", " ")
    specs = [parse_key_field(part, german) for part in KEY_SPLIT_RE.split(val)]
    return [s for s in specs if s]


def key_names(specs):
    """Render every key a field names, e.g. "Cm→C" for a modulating song."""
    return "→".join(key_name(s) for s in specs) if specs else "?"


def key_label(spec, german):
    """A key name spelled the way this song spells notes, so it can be pasted
    straight into key={}."""
    pc, minor = spec
    if german and pc == 11:
        name = "H"
    elif german and pc == 10:
        name = "B"
    else:
        name = NAMES_SHARP[pc].replace("#", r"\shrp ")
    return name + ("m" if minor else "")


def sounding(d, chords, lvl=None):
    """Fingered chords at the pitch they sound: shifted by capo and tuning, and
    by how far a part's own \\transpose sits from the song's home level."""
    shift = d["capo"] + d["tuning"] + (0 if lvl is None else lvl - d["transpose"])
    return [((pc + shift) % 12, mn) for pc, mn in chords]


def parts_sounding(d):
    """d["parts"], with each part's chords brought to sounding pitch."""
    return [(kind, tuple(sounding(d, chords, lvl)), elided, lvl)
            for kind, chords, elided, lvl in d["parts"]]


def part_type_pools(d):
    """Sounding chords pooled per part type, in order of first appearance."""
    pools = {}
    for kind, snd, _, _ in parts_sounding(d):
        pools.setdefault(kind, []).extend(snd)
    return pools


def part_type_keys(d, minimum=1):
    """Pooled key per part type, for types with at least `minimum` chords.
    Pooling beats scoring parts singly: one verse is often too short."""
    return [(kind, score_keys(pool, pool[-1])[0][1])
            for kind, pool in part_type_pools(d).items() if len(pool) >= minimum]


def key_name(spec):
    if spec is None:
        return "?"
    pc, minor = spec
    return NAMES_SHARP[pc] + ("m" if minor else "")


def load(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    text = strip_comments(text)
    # key={} names one key for every paper, so read the A4 variant only: an
    # A5 branch may re-finger the song with a capo of its own.
    text = LARGEPAPER_RE.sub(r"\1", text)
    german = bool(re.search(r"lang=\{\s*(czech|slovak)\s*[,}]", text))
    capo_m = CAPO_RE.search(text)
    capo = int(capo_m.group(1)) if capo_m else 0
    tun_m = TUN_RE.search(text)
    tuning = parse_tuning(tun_m.group(1) if tun_m else None, german)
    key_m = re.search(r"key=\{([^}]*)\}", text)
    stated_raw = key_m.group(1) if key_m else None
    stated_all = parse_key_fields(stated_raw, german) if stated_raw else []
    # Without the song's own part types, parts come out empty
    part_types = PART_TYPES | set(NEW_PART_RE.findall(text))
    # verse and chorus share the songs default register; the rest own theirs
    own_register = part_types - {"verse", "chorus"}
    # \transpose is BLOCK-SCOPED: docs/tools.md#transpose-is-block-scoped
    song_level = 0            # shift in force outside any part
    level = 0                 # shift in force right now
    in_part = False
    home = None               # song_level when the first chord turned up
    modulates = False
    chords = []
    parts = []                # (part type, chords in it, text elided with "...")
    cur, start, cur_level = [], None, 0
    # One register per part type, holding chords as *written*; None keeps step.
    registers = {}
    reg_name = None           # this part's own register
    memo_reg = None           # register the written chords are being stored into
    memorizing = False
    queue = []                # chords still to be handed out to ^ in this part
    memo = []

    def emit(c, replayed=False):
        """Record one sounding chord. Replays reach the part but NOT the pooled
        list -- see docs/tools.md#replayed-chords for why that balance matters."""
        nonlocal home, cur_level, modulates
        pc, minor = c
        if home is None:
            home = level
        if not cur:
            cur_level = level             # the level this part plays at
        cur.append(((pc + level) % 12, minor))
        if level != home:
            modulates = True
        elif not replayed:
            chords.append(cur[-1])

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
            if memorizing:
                memo.append(c)                # None too: keeps ^ in step with TeX
            if c:
                emit(c)
            continue
        if m.group(9) is not None:            # ^ hands out the next stored chord
            if queue:
                c = queue.pop(0)
                if c:
                    emit(c, replayed=True)
            # An empty queue means songs.sty would have errored here, so if it
            # happens we have mis-read a register; there is nothing to replay.
            continue
        if m.group(7) is not None:            # \usechords / \copychords
            src = list(registers.get(m.group(8), ()))
            if m.group(7) == "copychords" and reg_name:
                registers[reg_name] = tuple(src)
            memorizing, queue, memo = False, src, []
            continue
        if (m.group(3) or m.group(4)) in part_types:
            cur, start, cur_level = [], m.end(), song_level
            in_part, level = True, song_level      # the part opens a TeX group
            reg_name = m.group(3) or m.group(4)
            # songs acts on its default register, then sloka.cfg repoints \SB@creg
            # but not the replay tail \SB@ctail: docs/tools.md#replayed-chords
            memo, memo_reg = [], DEFAULT_REGISTER
            if reg_name == "chorus" or registers.get(DEFAULT_REGISTER):
                queue, memorizing = list(registers.get(DEFAULT_REGISTER, ())), False
            else:
                queue, memorizing = [], True
            if reg_name in own_register:
                if registers.get(reg_name):
                    queue, memorizing = list(registers[reg_name]), False
                else:
                    memorizing, memo_reg = True, reg_name   # queue stays as above
        elif (m.group(5) or m.group(6)) in part_types:
            if memorizing and memo:
                registers[memo_reg] = tuple(memo)
            if cur:
                body = text[start:m.start()] if start is not None else ""
                parts.append((m.group(5) or m.group(6), tuple(cur),
                              "..." in body or "…" in body, cur_level))
            cur, start = [], None
            in_part, level = False, song_level     # ...and closing it reverts
            reg_name, memorizing, queue, memo = None, False, [], []
    return {
        "german": german, "capo": capo, "tuning": tuning,
        "transpose": home if home is not None else song_level,
        "modulates": modulates, "stated_raw": stated_raw,
        "stated_all": stated_all,
        "stated": stated_all[0] if stated_all else None,   # the home key
        "chords": chords, "parts": parts,
    }


# Diatonic triads per key; minor includes the borrowed major V and VII.
MAJOR_TRIADS = {(0, False), (2, True), (4, True), (5, False), (7, False), (9, True)}
MINOR_TRIADS = {(0, True), (3, False), (5, True), (7, True), (8, False), (10, False), (7, False)}


def is_truncated_reprise(i, parts):
    """True if parts[i] is an abbreviated repeat, which stops mid-phrase and so
    does not end on a cadence: a strict chord prefix of a longer part, elided."""
    kind, chords, elided, _ = parts[i]
    if not elided:
        return False
    return any(k == kind and len(c) > len(chords) and c[:len(chords)] == chords
               for j, (k, c, _, _) in enumerate(parts) if j != i)


def ending_chord(parts, fallback):
    """The last chord of the last part that is not a truncated reprise."""
    for i in range(len(parts) - 1, -1, -1):
        if not is_truncated_reprise(i, parts):
            return parts[i][1][-1]
    return fallback


def score_keys(sounding, last=None):
    """Score all 24 keys, best first, as [(score, (tonic_pc, is_minor)), ...].
    The weights are tabulated in docs/tools.md#scoring; --explain shows them."""
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


def relative(spec):
    """Relative major<->minor: 3 semitones above a minor tonic, 3 below a major."""
    pc, minor = spec
    return ((pc + 3) % 12, False) if minor else ((pc - 3) % 12, True)


def classify(stated_all, detected):
    """Detecting any of the named keys is agreement; the finer verdicts
    (relative/parallel) compare against the home key."""
    if detected is None:
        return "no-chords"
    if not stated_all:
        return "propose"
    if detected in stated_all:
        return "match"
    # Near-misses test every named key, not just the home one
    if any(detected == relative(k) for k in stated_all):
        return "relative"
    if any(k[0] == detected[0] for k in stated_all):
        return "parallel"          # same root, major/minor flip
    return "mismatch"


def margin(scored, stated_all, detected):
    """Score gap between the detected key and the best stated one (or the
    runner-up). Clamped at 0; see docs/tools.md#reading-the-output."""
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
    d["sounding"] = snd = sounding(d, d["chords"])
    # Only home-level parts may decide the cadence; key={} leads with the home key
    home_parts = [p for p in parts_sounding(d) if p[3] == d["transpose"]]
    d["ending"] = ending_chord(home_parts, snd[-1]) if snd else None
    d["scored"] = score_keys(snd, d["ending"]) if snd else []
    detected = d["scored"][0][1] if d["scored"] else None
    # For a song in more than one key the parts, not the pooled chords, decide
    d["modulation"] = None
    if detected is not None:
        spec, why = modulation_key(d)
        if spec is not None and spec != detected:   # only when it changes the answer
            d["modulation"] = why
            detected = spec
    d["margin"] = margin(d["scored"], d["stated_all"], detected)
    cls = classify(d["stated_all"], detected)
    # A zero margin is a tie the sort broke: no evidence against what is written
    if cls in ("relative", "parallel", "mismatch") and d["margin"] == 0:
        cls = "tie"
    # Suggest the compound key only when adopting it settles the disagreement
    d["split"] = None
    if cls in ("relative", "parallel", "mismatch"):
        ptk = part_type_keys(d, minimum=6)
        specs = [s for _, s in ptk]
        distinct = set(specs)
        # >2 keys is short-part noise; a relative pair is major/minor ambiguity
        if (len(distinct) == 2 and detected in distinct
                and any(s in distinct for s in d["stated_all"])
                and relative(specs[0]) not in distinct):
            d["split"] = ptk
    return d, detected, cls


def best_shift(a, b):
    """(semitones, agreement) for the transposition of `a` best matching `b`."""
    n = min(len(a), len(b))
    if n < 4:
        return 0, 0.0
    best = (0, 0.0)
    for k in range(12):
        hits = sum(1 for i in range(n) if ((a[i][0] + k) % 12, a[i][1]) == b[i])
        if hits / n > best[1]:
            best = (k, hits / n)
    return best


# Overlap needed to call two parts the same progression moved; corpus-measured.
RATCHET_MATCH = 0.8


def modulation_key(d):
    """Home key of a song whose parts are not all in one key, as (spec, reason),
    or (None, None). Two signals: a part type replayed at another pitch, or every
    part agreeing where the pooled set does not. Why only those two, and why
    "their keys differ" is not one: docs/tools.md#scoring."""
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
    """Best key per part on its own; with_chords adds the sounding chords."""
    out = []
    for kind, snd, _, _ in parts_sounding(d):
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
    """Detect a key for each song part on its own -- what a modulation looks
    like from the chords. See docs/tools.md#reading-the-output."""
    d, detected, cls = analyze(path)
    print(os.path.relpath(path, repo))
    print(f"  stated key : {d['stated_raw'] or '-'}  ({key_names(d['stated_all'])})")
    print(f"  shift      : {shifts_note(d)}  (fingered chords -> sounding pitch)")
    print(f"  whole song : {key_name(detected)}  [{cls}]")
    if not d["parts"]:
        print("  no song parts with chords found\n")
        return
    ps = parts_sounding(d)
    print(f"  {'#':>2}  {'part':<20} {'n':>3}  {'chords (sounding)':<44}  best keys for that part")
    for i, (kind, snd, elided, lvl) in enumerate(ps):
        label = kind
        if lvl != d["transpose"]:
            label += f" {lvl - d['transpose']:+d}"
        # An ellipsis alone is not a truncation; ask what the cadence logic asks
        if is_truncated_reprise(i, ps):
            label += " (cut short)"
        seq = " ".join(key_name(c) for c in snd)
        if len(seq) > 44:
            seq = seq[:43] + "…"
        top = "   ".join(f"{key_name(s)} {sc:.0f}" for sc, s in score_keys(snd, snd[-1])[:3])
        print(f"  {i:>2}  {label:<20} {len(snd):>3}  {seq:<44}  {top}")
    # Pooling by type separates a verse key from a chorus key
    pools = part_type_pools(d)
    if len(pools) > 1 or len(ps) > len(pools):
        print("  pooled by part type:")
        for kind in sorted(pools):
            pool = pools[kind]
            hist = "  ".join(f"{key_name(c)}×{n}" for c, n in Counter(pool).most_common(5))
            top = "   ".join(f"{key_name(s)} {sc:.1f}" for sc, s in score_keys(pool, pool[-1])[:3])
            print(f"    {kind:<14} ({len(pool):>3})  {hist:<40}  -> {top}")
    print()


def explain(path, repo):
    """Print the detector's reasoning for one song."""
    d, detected, cls = analyze(path)
    print(os.path.relpath(path, repo))
    naming = "Czech/Slovak (H=B♮, B=B♭)" if d["german"] else "English (B=B♮)"
    print(f"  stated key : {d['stated_raw'] or '-'}  ({key_names(d['stated_all'])})")
    print(f"  note naming: {naming}")
    print(f"  shift      : {shifts_note(d)}  (fingered chords -> sounding pitch)")
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
    ap.add_argument("--songbook", metavar="DIR",
                    help="the songbook checkout (default: the one this package sits in, "
                         "or the one around the working directory)")
    args = ap.parse_args()

    repo = songbook_root(args.songbook)
    scan = args.paths if args.paths else [repo / "songs" / "chords"]
    files = []
    for p in scan:
        p = Path(p)
        if p.is_dir():
            # Skip tinwhistle melody tabs; pass one explicitly to analyze it
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
        agree = sum(1 for r in graded if r[3] in ("match", "relative", "tie"))
        print("Agreement vs. existing keys (chord-based detector):")
        for cls in ("match", "tie", "relative", "parallel", "mismatch", "propose", "no-chords"):
            print(f"  {cls:<10} {counts.get(cls, 0)}")
        if graded:
            print(f"\n  no disagreement (match+tie+relative) = {agree}/{len(graded)}"
                  f" = {100*agree/len(graded):.0f}% of keyed songs")
        return 0

    # Strongest disagreements first; ties land at the bottom, next to matches
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
        # A tie carries no evidence either way, so it is as quiet as a match.
        if not args.all and cls in ("match", "tie", "no-chords"):
            continue
        tag = {"relative": "rel. maj/min", "parallel": "MAJ/MIN FLIP",
               "mismatch": "MISMATCH", "propose": "MISSING", "match": "ok",
               "tie": "tie - no preference"}.get(cls, cls)
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
        if d["split"]:
            seen, distinct = set(), []
            for _, spec in d["split"]:
                if spec not in seen:
                    seen.add(spec)
                    distinct.append(key_label(spec, d["german"]))
            seq = "  ".join(f"{k}:{key_label(s, d['german'])}" for k, s in d["split"])
            print(f"  part types differ ({seq})"
                  f" -> try key={{{r'\rightarrow '.join(distinct)}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
