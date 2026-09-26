#!/usr/bin/env python3
"""Compare a song's lyrics word by word with the same song on lyric sites.

Read-only developer tool: it fetches web pages and prints only the words that
differ, never the lyrics themselves. Every source counts the same, the song's
own src= included -- a tab is often where a mistake came from -- so a
difference two or more sites agree on is the one worth checking. How it reads
the pages, and its limits, are in docs/tools.md.

Usage: scripts/checklyrics.py [options] SONG.tex ...   (--help for the options)
Exit status: 0 = done (differences are information, not failure), 2 = no songs.
"""

import argparse
import difflib
import html
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from songfile import collect_song_files, parse_song  # noqa: E402

AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/126 Safari/537.36")
MIN_MATCH = 0.5          # below this the page is not the song (or a bot check)
MAX_SPAN = 5             # longer differences are verses the book leaves out

# Words a site puts between the verses: section labels, repeat marks, menus.
PAGE_NOISE = {
    "r", "ref", "refren", "refrén", "sloka", "rec", "dur", "moll", "původní",
    "orig", "kapo", "capo", "intro", "verse", "chorus", "solo", "interlude",
    "bridge", "outro", "x2", "x3", "x4", "2x", "3x", "4x", "dne", "nehledáš",
    "náhodou", "m", "mi", "dim", "aug", "sus2", "sus4", "maj", "maj7",
}
# A chord a site sets inline with the words, lowercased.
PAGE_CHORD = re.compile(r"^[a-h](is|es|#|b)?(m|mi|maj|dim|aug|sus\d?|add\d+)?\d*$")
FILLER = re.compile(r"(o+h*|a+h*|y?e+a+h*|na|la|hey|ho|m+|whoa|woah|uh+)")
WORD = re.compile(r"[\w']+")


def words(text):
    text = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    return [w for w in WORD.findall(text) if not w.isdigit()]


def song_words(text):
    """The sung words of a comment-stripped song, as the A5 book prints them
    (the \\else branch of \\iflargepaper), with line numbers."""
    text = re.sub(r"\\iflargepaper(.*?)\\else(.*?)\\fi",
                  lambda m: "\n" * m[1].count("\n") + m[2], text, flags=re.S)
    text = re.sub(r"\\iflargepaper(.*?)\\fi",
                  lambda m: "\n" * m[1].count("\n"), text, flags=re.S)
    text = re.sub(r"\\beginsong\{.*?\n\]", lambda m: "\n" * m[0].count("\n"),
                  text, count=1, flags=re.S)
    out = []
    for lineno, line in enumerate(text.split("\n"), 1):
        line = re.sub(r"\\\[[^\]]*\]", "", line)
        line = re.sub(r"\\multivoice\{([^{}]*)\}\{([^{}]*)\}", r"\1 \2", line)
        line = re.sub(r"\\(role|textnote|musicnote|gtab|lilypondfile|rep|meter|capo|"
                      r"mbar|transpose|usechords|copychords|newchords|setcounter|"
                      r"setchordwidth|newSongPartType)\*?(\{[^{}]*\})+", " ", line)
        line = re.sub(r"\\[a-zA-Z@]+\*?", " ", line)
        line = line.replace("\\", " ").replace("^", "").replace("~", " ")
        out += [(w, lineno) for w in words(line)]
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT,
                                               "Accept-Language": "cs,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    if body.lstrip().startswith("{"):             # a lyrics API's JSON
        try:
            body = json.loads(body).get("lyrics", "")
        except ValueError:
            pass
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", body)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return [w for line in body.split("\n") for w in words(line)]


def slug(s, sep="-"):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", sep, s.replace("'", "").replace("&", "")).strip(sep)


def candidate_urls(info):
    """Where the song is likely to be: lyric and chord sites, and its own src=."""
    title = info["title"] or ""
    by = re.sub(r"\\ ", " ", info["keys"].get("by", ""))
    artist = re.split(r",| a |\\and| & ", by)[0].strip()
    bare = re.sub(r"^the ", "", artist.lower())
    urls = [f"https://www.velkyzpevnik.cz/{slug(artist)}/{slug(title)}"]
    urls += re.findall(r"https?://[^\s,}]+", info["keys"].get("src", ""))
    urls += [
        f"https://www.azlyrics.com/lyrics/{slug(bare, '')}/{slug(title, '')}.html",
        "https://genius.com/" + slug(f"{artist} {title}").capitalize() + "-lyrics",
        "https://api.lyrics.ovh/v1/" + urllib.parse.quote(artist) + "/"
        + urllib.parse.quote(title),
        f"https://akordy.kytary.cz/song/{slug(title)}",
        f"https://pisnicky-akordy.cz/{slug(artist)}/{slug(title)}",
    ]
    return list(dict.fromkeys(urls))


def page_window(song, page):
    """The stretch of a page the song is on, dropping menus around it."""
    sm = difflib.SequenceMatcher(None, page, song, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 3]
    if not blocks:
        return []
    lo = min(b.a for b in blocks)
    hi = max(b.a + b.size for b in blocks)
    return page[max(0, lo - 5):hi + 5]


def trivial(a, b):
    """Same words once apostrophes and a site's inline chords are gone."""
    b = [w for w in b if w not in PAGE_NOISE and not (PAGE_CHORD.match(w) and len(w) <= 5)]
    if "".join(a).replace("'", "") == "".join(b).replace("'", ""):
        return True
    return all(FILLER.fullmatch(w) for w in a + b)


def compare(path, info, extra_urls):
    song = song_words(info["text"])
    sung = [w for w, _ in song]
    urls = candidate_urls(info) + extra_urls
    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = list(pool.map(fetch, urls))
    used, votes = [], {}
    for url, page in zip(urls, pages):
        site = urllib.parse.urlparse(url).netloc.removeprefix("www.")
        if any(u.startswith(site + " ") for u in used):
            continue                  # one vote per site
        win = page_window(sung, page)
        sm = difflib.SequenceMatcher(None, sung, win, autojunk=False)
        if not win or sm.ratio() < MIN_MATCH:
            continue
        used.append(f"{site} {sm.ratio():.2f}")
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            a, b = sung[i1:i2], win[j1:j2]
            if op == "equal" or max(len(a), len(b)) > MAX_SPAN or trivial(a, b):
                continue
            b = [w for w in b if w not in PAGE_NOISE]
            votes.setdefault((i1, i2, " ".join(b)), set()).add(site)
    return song, used, votes


def main():
    ap = argparse.ArgumentParser(description="Compare lyrics with lyric sites.")
    ap.add_argument("paths", nargs="+", help="song files or directories")
    ap.add_argument("--min", type=int, default=2, metavar="N",
                    help="show differences at least N sites agree on (default 2)")
    ap.add_argument("--url", action="append", default=[],
                    help="another page to compare with (repeatable)")
    args = ap.parse_args()

    files = collect_song_files(args.paths)
    if not files:
        print("No .tex song files found.", file=sys.stderr)
        return 2
    for f in files:
        info = parse_song(f)
        if not info["text"]:
            continue
        song, used, votes = compare(f, info, args.url)
        print(f"{f}\n  sources: {', '.join(used) if used else 'none found'}")
        for (i1, i2, alt), sites in sorted(votes.items()):
            if len(sites) < args.min:
                continue
            ctx = lambda lo, hi: " ".join(w for w, _ in song[lo:hi])  # noqa: E731
            line = song[min(i1, len(song) - 1)][1]
            print(f"  line {line}: [{ctx(i1, i2)}] -> [{alt}]"
                  f"   ({ctx(i1 - 2, i1)} … {ctx(i2, i2 + 2)})  {len(sites)}/{len(used)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
