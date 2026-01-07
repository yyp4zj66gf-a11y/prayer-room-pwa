#!/usr/bin/env python3
"""
tools/filter_non_scripture_quotes.py

Filter quotes_audit.json into non-scripture theology quotes.

Keeps:
- non-scripture-ish (heuristics)
- optionally only method=colon (rank-attributed lines)
- optionally drop Unknown authors

Outputs:
- quotes_theology.json (PWA format)
- quotes_theology_audit.json (keeps metadata)
"""

from __future__ import annotations

import argparse
import json
import re
from typing import List, Dict


SCRIPTUREISH = re.compile(
    r"\b("
    r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|"
    r"Job|Psalms?|Proverbs|Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|"
    r"Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    r"Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|"
    r"Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|"
    r"1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation"
    r")\b|\b\d{1,3}:\d{1,3}\b|\b(NIV|KJV|NKJV|ESV|NLT|CEV)\b",
    re.IGNORECASE,
)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="quotes_audit.json")
    ap.add_argument("--out", dest="outp", default="quotes_theology.json")
    ap.add_argument("--out-audit", dest="outa", default="quotes_theology_audit.json")
    ap.add_argument("--max-len", type=int, default=200)
    ap.add_argument("--min-len", type=int, default=25)
    ap.add_argument("--only-method", choices=["quoted", "colon", "blockquote"], default=None)
    ap.add_argument("--drop-unknown", action="store_true")
    args = ap.parse_args()

    audit: List[Dict] = json.load(open(args.inp, "r", encoding="utf-8"))

    kept = []
    for q in audit:
        text = (q.get("text") or "").strip()
        if not text:
            continue
        if len(text) < args.min_len or len(text) > args.max_len:
            continue
        if SCRIPTUREISH.search(text):
            continue
        if args.only_method and q.get("method") != args.only_method:
            continue
        if args.drop_unknown and (q.get("author") == "Unknown" or not q.get("author")):
            continue
        kept.append(q)

    # Dedupe by author+text
    seen = set()
    deduped = []
    for q in kept:
        key = ((q.get("author") or "").strip(), (q.get("text") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)

    # Write PWA format
    pwa = [{"author": q.get("author","Unknown"), "text": q.get("text","")} for q in deduped]
    json.dump(pwa, open(args.outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(deduped, open(args.outa, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("input:", len(audit))
    print("kept:", len(deduped))
    print("wrote:", args.outp)
    print("wrote:", args.outa)

if __name__ == "__main__":
    main()

