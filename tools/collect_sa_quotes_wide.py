#!/usr/bin/env python3
"""
tools/mine_warcry_ia_ocr.py

Mine Salvation Army War Cry quotes from Internet Archive items that have OCR text
files (prefer *_djvu.txt, fallback to *_text.txt).

You can provide either:
- --djvu-txt URL(s) directly, OR
- --item IA identifier(s) (recommended). The script will look up metadata and
  find the best text file automatically.

Outputs:
- <out>: audit JSON with source + context (for human review)

Examples
--------
# Recommended: just give item IDs
python3 tools/mine_warcry_ia_ocr.py \
  --item "war-cry-1957-Sept-14" \
  --item "war-cry-1950-07-08" \
  --out warcry_quotes_audit.json

# Or: provide explicit text URLs
python3 tools/mine_warcry_ia_ocr.py \
  --djvu-txt "https://archive.org/stream/<ITEM>/<FILE>_djvu.txt" \
  --out warcry_quotes_audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


THEOLOGY_INCLUDE = [
    "jesus", "christ", "lord", "god", "holy spirit", "spirit", "prayer",
    "gospel", "salvation", "saved", "redeem", "redemption", "grace",
    "mercy", "cross", "resurrection", "repent", "faith", "holiness",
    "sanctif", "scripture", "bible", "kingdom",
]

CHARITY_EXCLUDE = [
    "donate", "donation", "fundraiser", "kettle", "food drive", "coat",
    "shelter", "disaster", "volunteer", "volunteers", "toy", "tickets",
    "registration",
]

RANKS = [
    "general", "commissioner", "colonel", "major", "lieutenant",
    "captain", "brigadier",
]

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WS = re.compile(r"\s+")


@dataclass(frozen=True)
class QuoteHit:
    author: str
    text: str
    source_url: str
    context: str


def fetch_text(url: str, timeout_s: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        data = r.read()
    return data.decode("utf-8", errors="replace")


def fetch_json(url: str, timeout_s: int = 45) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        data = r.read()
    return json.loads(data.decode("utf-8", errors="replace"))


def norm(s: str) -> str:
    return WS.sub(" ", s).strip()


def guess_author(sentence: str) -> str:
    low = sentence.lower()
    for r in RANKS:
        if r in low:
            m = re.search(
                rf"\b({re.escape(r)})\s+([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){{0,3}})",
                sentence,
            )
            if m:
                return f"{m.group(1).title()} {m.group(2).strip()}"
            return r.title()
    return "Unknown"


def is_theology(sentence: str) -> bool:
    low = sentence.lower()
    if any(x in low for x in CHARITY_EXCLUDE):
        return False
    return any(x in low for x in THEOLOGY_INCLUDE)


def extract_candidates(text: str, source_url: str, min_len: int, max_len: int) -> List[QuoteHit]:
    cleaned = norm(text)
    sents = SENTENCE_SPLIT.split(cleaned)

    hits: List[QuoteHit] = []
    for s in sents:
        s = norm(s)
        if not (min_len <= len(s) <= max_len):
            continue
        if not is_theology(s):
            continue
        author = guess_author(s)
        hits.append(QuoteHit(author=author, text=s, source_url=source_url, context=s[:300]))
    return hits


def dedupe(hits: Iterable[QuoteHit]) -> List[QuoteHit]:
    seen = set()
    out: List[QuoteHit] = []
    for h in hits:
        key = (h.author, h.text)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def best_text_file_for_item(item: str) -> Tuple[str, str]:
    """
    Returns (url, filename) for best OCR text file.
    Prefers *_djvu.txt, fallback *_text.txt.
    """
    meta_url = f"https://archive.org/metadata/{urllib.parse.quote(item)}"
    meta = fetch_json(meta_url)

    files = meta.get("files") or []
    if not isinstance(files, list):
        raise RuntimeError(f"Unexpected metadata format for item={item}")

    candidates = []
    for f in files:
        name = f.get("name")
        if not name or not isinstance(name, str):
            continue
        lname = name.lower()
        if lname.endswith("_djvu.txt"):
            candidates.append((0, name))
        elif lname.endswith("_text.txt"):
            candidates.append((1, name))

    if not candidates:
        raise RuntimeError(f"No *_djvu.txt or *_text.txt found for item={item}")

    candidates.sort(key=lambda x: (x[0], len(x[1])))
    _, filename = candidates[0]
    url = f"https://archive.org/stream/{item}/{urllib.parse.quote(filename)}"
    return url, filename


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--djvu-txt", action="append", default=[], help="Direct URL to IA *_djvu.txt or *_text.txt")
    ap.add_argument("--item", action="append", default=[], help="Internet Archive item identifier (archive.org/details/<item>)")
    ap.add_argument("--out", default="warcry_quotes_audit.json")
    ap.add_argument("--min-len", type=int, default=45)
    ap.add_argument("--max-len", type=int, default=220)
    args = ap.parse_args(argv)

    if not args.djvu_txt and not args.item:
        ap.error("Provide at least one --item or --djvu-txt URL")

    urls: List[str] = []
    for item in args.item:
        print(f"[META] {item}")
        try:
            url, fn = best_text_file_for_item(item)
            print(f"[TXT]  {fn}")
            urls.append(url)
        except Exception as e:
            print(f"[SKIP] item={item} -> {type(e).__name__}: {e}", file=sys.stderr)

    urls.extend(args.djvu_txt)

    all_hits: List[QuoteHit] = []
    for u in urls:
        print(f"[FETCH] {u}")
        try:
            t = fetch_text(u)
        except urllib.error.HTTPError as e:
            print(f"[SKIP] {u} -> HTTP {e.code}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"[SKIP] {u} -> {type(e).__name__}: {e}", file=sys.stderr)
            continue

        hits = extract_candidates(t, u, args.min_len, args.max_len)
        print(f"[HITS] {len(hits)}")
        all_hits.extend(hits)

    all_hits = dedupe(all_hits)
    payload = [h.__dict__ for h in all_hits]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[DONE] unique={len(all_hits)} wrote={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

