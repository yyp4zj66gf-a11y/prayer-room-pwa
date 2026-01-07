# tools/clean_handbook_1923_quotes.py
"""
Clean and dedupe mined quotes from handbook_1923_quotes.json.

This removes OCR junk (section headings, hyphen artifacts), splits multi-statement blobs,
and emits both:
  - handbook_1923_quotes_clean.json (metadata preserved)
  - quotes.json (PWA-ready [{author,text}])

Usage:
  cd ~/Desktop/PrayerRoomPWA
  python3 tools/clean_handbook_1923_quotes.py \
    --in handbook_1923_quotes.json \
    --out-clean handbook_1923_quotes_clean.json \
    --out-pwa quotes.json

Optional tuning:
  --min-len 90 --max-len 320
  --no-split-we-believe
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SOFT_HYPHEN = "\u00ad"

# Common OCR garbage patterns seen in your sample:
# - "Sec. IV.—", "Section I.—", "Section X.—"
# - leading roman numeral headings "I.—", "II.—", etc.
# - trailing "Section I.—..." "1." etc.
LEADING_JUNK_RE = re.compile(
    r"^(?:"
    r"(?:Sec\.|Section)\s+[IVXLC]+\s*\.?\s*[—\-–]\s*.*?\s+|"
    r"(?:[IVXLC]+)\s*\.?\s*[—\-–]\s*.*?\s+|"
    r"(?:[IVXLC]+\.)\s*|"
    r")",
    re.IGNORECASE,
)

TRAILING_JUNK_RE = re.compile(
    r"(?:\s+"
    r"(?:Section|Sec\.)\s+[IVXLC]+\s*\.?\s*[—\-–].*?$|"
    r"\s+Section\s+\w+\s*\.?\s*[—\-–].*?$|"
    r"\s+\d+\.\s*$"
    r")",
    re.IGNORECASE,
)

PAREN_NOTE_RE = re.compile(r"\(\s*see\s+[^)]{0,80}\)", re.IGNORECASE)

WHITESPACE_RE = re.compile(r"\s+")

# Split on repeated doctrinal statements.
WE_BELIEVE_RE = re.compile(r"\b(?:We believe that|We believe in|We believe)\b", re.IGNORECASE)

# Quotes normalization
OPEN_QUOTES = ["“", '"', "‘", "'"]
CLOSE_QUOTES = ["”", '"', "’", "'"]

SCRIPTUREISH_RE = re.compile(r"\b\d{1,3}:\d{1,3}\b")


def normalize_text(s: str) -> str:
    s = (s or "").replace(SOFT_HYPHEN, "")
    # Join OCR broken words with "¬" marker, removing adjacent whitespace.
    s = re.sub(r"\s*¬\s*", "", s)
    # Normalize curly quotes to straight quotes (optional)
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = WHITESPACE_RE.sub(" ", s).strip()
    # Fix common OCR spaced fragments like "Gov ernor" if they were caused by marker removal.
    s = re.sub(r"(\w)\s+(\w)", lambda m: m.group(0), s)  # noop; keep readable
    return s


def strip_boilerplate(s: str) -> str:
    s = normalize_text(s)

    # If there is a doctrinal anchor, cut everything before it.
    m = WE_BELIEVE_RE.search(s)
    if m:
        s = s[m.start() :].strip()

    # Remove parenthetical cross references (optional—keeps quotes cleaner)
    s = PAREN_NOTE_RE.sub("", s)

    # Remove leading headings repeatedly
    # (do this in a loop because OCR can stack multiple headings)
    for _ in range(5):
        new = LEADING_JUNK_RE.sub("", s).strip()
        if new == s:
            break
        s = new

    # Remove trailing headings / section labels
    s = TRAILING_JUNK_RE.sub("", s).strip()

    # Remove stray leftover 'Section I.—...' fragments anywhere near the end
    s = re.sub(r"\s+(Section|Sec\.)\s+[IVXLC]+\s*\.?\s*[—\-–].*$", "", s, flags=re.IGNORECASE).strip()

    # Trim unmatched leading/trailing quotes
    if s and s[0] in OPEN_QUOTES:
        s = s[1:].lstrip()
    if s and s[-1] in CLOSE_QUOTES:
        s = s[:-1].rstrip()

    # Final whitespace normalize
    return normalize_text(s)


def split_we_believe_blocks(s: str) -> List[str]:
    s = strip_boilerplate(s)
    matches = list(WE_BELIEVE_RE.finditer(s))
    if len(matches) <= 1:
        return [s] if s else []

    parts: List[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(s)
        chunk = s[start:end].strip(" ;:-–—")
        chunk = strip_boilerplate(chunk)
        if chunk:
            parts.append(chunk)
    return parts


def make_key(s: str) -> str:
    s = normalize_text(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = WHITESPACE_RE.sub(" ", s).strip()
    return s


@dataclass
class CleanRecord:
    author: str
    text: str
    doctrine: Optional[int]
    doctrine_label: Optional[str]
    source: Dict[str, Any]
    score: float


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="handbook_1923_quotes.json")
    ap.add_argument("--out-clean", default="handbook_1923_quotes_clean.json")
    ap.add_argument("--out-pwa", default="quotes.json")
    ap.add_argument("--min-len", type=int, default=90)
    ap.add_argument("--max-len", type=int, default=320)
    ap.add_argument("--no-split-we-believe", action="store_true")
    args = ap.parse_args()

    inp_path = Path(args.inp).expanduser().resolve()
    data = json.loads(inp_path.read_text(encoding="utf-8"))

    produced: List[CleanRecord] = []
    split_count = 0
    dropped_empty = 0
    dropped_len = 0

    for item in data:
        raw_text = str(item.get("text", "") or "")
        author = str(item.get("author", "Handbook of Salvation Army Doctrine (1923)") or "")
        doctrine = item.get("doctrine")
        doctrine_label = item.get("doctrine_label")
        score = float(item.get("score", 0.0) or 0.0)
        source = item.get("source") or {
            "title": item.get("source_title"),
            "year": item.get("source_year"),
            "page": item.get("page"),
            "file": item.get("source_file"),
            "chapter": item.get("chapter"),
        }

        if args.no_split_we_believe:
            chunks = [strip_boilerplate(raw_text)]
        else:
            chunks = split_we_believe_blocks(raw_text)
            if len(chunks) > 1:
                split_count += 1

        for ch in chunks:
            ch = strip_boilerplate(ch)
            if not ch:
                dropped_empty += 1
                continue
            if not (args.min_len <= len(ch) <= args.max_len):
                dropped_len += 1
                continue

            produced.append(
                CleanRecord(
                    author=author,
                    text=ch,
                    doctrine=doctrine if isinstance(doctrine, int) else None,
                    doctrine_label=str(doctrine_label) if doctrine_label else None,
                    source=source,
                    score=score,
                )
            )

    # Dedupe by cleaned text, keep highest score (then earliest page)
    best_by_key: Dict[str, CleanRecord] = {}
    for rec in produced:
        key = make_key(rec.text)
        if not key:
            continue
        keep = best_by_key.get(key)
        if keep is None:
            best_by_key[key] = rec
            continue

        keep_page = int(keep.source.get("page") or 10**9)
        rec_page = int(rec.source.get("page") or 10**9)

        if (rec.score, -rec_page) > (keep.score, -keep_page):
            best_by_key[key] = rec

    cleaned = list(best_by_key.values())
    cleaned.sort(key=lambda r: (-r.score, int(r.source.get("page") or 10**9)))

    # Write clean metadata file
    out_clean = Path(args.out_clean).expanduser().resolve()
    out_clean.write_text(
        json.dumps([rec.__dict__ for rec in cleaned], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Write PWA-ready quotes.json
    out_pwa = Path(args.out_pwa).expanduser().resolve()
    pwa = [{"author": rec.author, "text": rec.text} for rec in cleaned]
    out_pwa.write_text(json.dumps(pwa, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "[OK]",
        {
            "input_items": len(data),
            "produced_before_dedupe": len(produced),
            "split_sources": split_count,
            "dropped_empty": dropped_empty,
            "dropped_len": dropped_len,
            "final_unique": len(cleaned),
            "wrote_clean": str(out_clean),
            "wrote_pwa": str(out_pwa),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

