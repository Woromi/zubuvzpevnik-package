#!/usr/bin/env python3
"""Sanity-check song keys against the actual chords, and propose missing ones.

The `key={}` field names the song's *home* key: the chord shapes you finger,
shifted up by the \\capo amount and by any *global* \\transpose. This script
extracts every \\[chord], applies \\transpose the way songs.sty does (cumulative,
reset per \\beginsong), then the capo, plus the song's note-naming convention
(Czech/Slovak use H=B-natural, B=B-flat), then infers the most likely key from
the chord progression and compares it to what's written.

Modulations: a \\transpose *before the first chord* is a global shift and applies
to the whole song; a \\transpose *after* chords have started is a mid-song key
change (a bridge, or a verse that climbs a semitone). Detection uses only the
chords at the song's initial transposition level so the home key still resolves;
such songs are tagged "(modulates)". (\\[chord] replays via ^ in a transposed
section are invisible to a text scan, so a modulation may sound bigger than the
chords we can see.)

Tinwhistle songs are skipped in directory scans: they are melody tabs with no
\\[chords] to check, and their key is fixed by the tune's sharps/flats. Their key
field reads "<song key> (<whistle> whistle)" -- the parenthetical names the
whistle the tune is *playable on*, not the key. (Pass such a file explicitly to
analyze it anyway; the parenthetical is then stripped before comparison.)

It is a heuristic helper, not an authority: keys are genuinely ambiguous
(relative major/minor, modal songs, songs that modulate or end away from home),
so treat disagreements as "worth a look," not "wrong." It never edits files.

Usage:
    scripts/checkkeys.py [PATH ...]      # report (default: songs/chords)
    scripts/checkkeys.py --validate      # agreement stats vs. existing keys
    scripts/checkkeys.py --missing       # only propose keys for songs lacking one
    scripts/checkkeys.py --all           # show every song, not just disagreements
    scripts/checkkeys.py --explain PATH  # show why a key is detected (the workings)
"""

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Note letter -> semitone (pitch class). German/Czech naming swaps B and H.
NOTE_EN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11, "H": 11}
NOTE_DE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 10, "H": 11}

CAPO_RE = re.compile(r"\\capo\{(\d+)\}")
# A single ordered scan: either a \transpose{n} (group 1) or a \[chord] (group 2).
# Scanning both in document order lets us apply the cumulative \transpose to only
# the chords that follow it, the way songs.sty does.
TOKEN_RE = re.compile(r"\\transpose\*?\{([+-]?\d+)\}|\\\[([^\]]*)\]")


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


def parse_key_field(val, german):
    """Parse a key={} value to (tonic_pc, is_minor) or None. Ignores a
    trailing '(... whistle)' annotation."""
    val = re.sub(r"\(.*?\)", "", val).strip()
    if not val:
        return None
    pc, rest = parse_note(val, german)
    if pc is None:
        return None
    return (pc, is_minor(rest))


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
    key_m = re.search(r"key=\{([^}]*)\}", text)
    stated_raw = key_m.group(1) if key_m else None
    # Walk chords and \transpose in document order. \transpose is cumulative and
    # shifts every chord that follows it (songs.sty resets it per \beginsong). A
    # \transpose before the first chord is a global shift that defines the home
    # transposition; a \transpose after chords have started is a mid-song
    # modulation. The key={} field names the home key, so we keep only the chords
    # at the initial level and skip the modulated sections (else a song that
    # climbs a semitone each verse would look keyless). \capo is added later, in
    # analyze(), to reach the sounding pitch: the projects do not enable songs'
    # transposecapos option, so the capo is a separate axis and the \[chord]
    # shapes are what you actually finger.
    transpose = 0
    initial = None
    modulates = False
    chords = []
    for m in TOKEN_RE.finditer(text):
        if m.group(1) is not None:
            transpose += int(m.group(1))
            if initial is not None:
                modulates = True          # a \transpose after chords = modulation
            continue
        c = parse_chord(m.group(2), german)
        if c:
            pc, minor = c
            if initial is None:
                initial = transpose
            if transpose == initial:
                chords.append(((pc + transpose) % 12, minor))
            # chords at other levels are transient modulations -> skip
    return {
        "german": german, "capo": capo,
        "transpose": initial if initial is not None else 0,
        "modulates": modulates, "stated_raw": stated_raw,
        "stated": parse_key_field(stated_raw, german) if stated_raw else None,
        "chords": chords,
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


def score_keys(sounding):
    """Score all 24 keys against the chord list. Returns [(score, spec), ...]
    sorted best-first. spec is (tonic_pc, is_minor). This is the heart of the
    heuristic; --explain prints the top of this list so the ranking is visible."""
    freq = Counter(sounding)
    roots = {pc for pc, _ in sounding}
    first, last = sounding[0], sounding[-1]
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


def detect_key(sounding):
    """sounding: list of (pc, is_minor). Returns (tonic_pc, is_minor) or None."""
    if not sounding:
        return None
    return score_keys(sounding)[0][1]


def relative(spec):
    """Relative major<->minor of a key spec. Relative major sits 3 semitones
    above the minor tonic (Am->C); relative minor 3 below the major (C->Am)."""
    pc, minor = spec
    return ((pc + 3) % 12, False) if minor else ((pc - 3) % 12, True)


def classify(stated, detected):
    if detected is None:
        return "no-chords"
    if stated is None:
        return "propose"
    if stated == detected:
        return "match"
    if detected == relative(stated):
        return "relative"
    if stated[0] == detected[0]:
        return "parallel"          # same root, major/minor flip
    return "mismatch"


def analyze(path):
    d = load(path)
    sounding = [((pc + d["capo"]) % 12, mn) for pc, mn in d["chords"]]
    d["sounding"] = sounding
    detected = detect_key(sounding)
    cls = classify(d["stated"], detected)
    return d, detected, cls


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
    naming = "Czech/Slovak (H=B♮, B=B♭)" if d["german"] else "English (B=B♮)"
    print(f"  stated key : {d['stated_raw'] or '-'}  ({key_name(d['stated'])})")
    print(f"  note naming: {naming}")
    print(f"  shift      : {' + '.join(shift) if shift else 'none'}  (fingered chords -> sounding pitch)")
    if d["modulates"]:
        print("  modulates  : mid-song \\transpose found -> detecting the HOME key only")
    sounding = d["sounding"]
    if not sounding:
        print("  no chords found -> cannot detect a key\n")
        return
    freq = Counter(sounding)
    hist = "  ".join(f"{key_name(c)}×{n}" for c, n in freq.most_common())
    print(f"  first chord: {key_name(sounding[0])}    last chord: {key_name(sounding[-1])}")
    print(f"  chords     : {hist}")
    print("  best key candidates (higher score = better fit of chords + first/last):")
    for score, spec in score_keys(sounding)[:4]:
        marker = " <- detected" if spec == detected else ""
        rel = key_name(relative(spec))
        kind = "minor" if spec[1] else "major"
        relkind = "major" if spec[1] else "minor"
        print(f"      {key_name(spec):<4} {kind:<5} score {score:6.1f}   relative {relkind}: {rel}{marker}")
    print(f"  verdict    : detected {key_name(detected)} vs stated {key_name(d['stated'])}  [{cls}]\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--validate", action="store_true", help="agreement stats only")
    ap.add_argument("--missing", action="store_true", help="only songs without a key")
    ap.add_argument("--all", action="store_true", help="show every song")
    ap.add_argument("--explain", action="store_true", help="show the detector's reasoning")
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

    for f, d, detected, cls in rows:
        rel = os.path.relpath(f, repo)
        if args.missing:
            if cls == "propose":
                print(f"{rel}\n  propose key={{{key_name(detected)}}}  (capo {d['capo']}, {len(d['chords'])} chords)")
            continue
        if not args.all and cls in ("match", "no-chords"):
            continue
        tag = {"relative": "rel. maj/min", "parallel": "MAJ/MIN FLIP",
               "mismatch": "MISMATCH", "propose": "MISSING", "match": "ok"}.get(cls, cls)
        shift = f"  capo={d['capo']}"
        if d["transpose"]:
            shift += f"  transpose={d['transpose']:+d}"
        if d["modulates"]:
            shift += "  (modulates)"
        print(f"{rel}")
        print(f"  stated={{{d['stated_raw'] or '-'}}}={key_name(d['stated'])}  detected={key_name(detected)}"
              f"{shift}  [{tag}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
