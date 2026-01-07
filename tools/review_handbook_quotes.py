# tools/review_handbook_quotes.py
"""
Review and triage mined handbook quotes to avoid out-of-context / inflammatory / OCR-fragment excerpts.

Reads:  handbook_1923_quotes.json (or *_clean.json if you have it)
Writes:
  - handbook_review_report.json
  - handbook_quotes_safe.json
  - handbook_quotes_flagged.json
  - handbook_quotes_dropped.json   (obvious junk/incomplete)

Usage:
  cd ~/Desktop/PrayerRoomPWA
  python3 tools/review_handbook_quotes.py --in handbook_1923_quotes.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


WS_RE = re.compile(r"\s+")
SOFT_HYPHEN = "\u00ad"

OCR_HEADER_MARKERS = [
    "HANDBOOK OF DOCTRINE",
    "THE BIBLE",
    "[chap",
    "chap.",
]
STRUCTURE_MARKERS = [
    "Sec.",
    "Section",
    "I.—",
    "II.—",
    "III.—",
    "IV.—",
    "V.—",
    "VI.—",
    "VII.—",
    "VIII.—",
    "IX.—",
    "X.—",
    "XI.—",
]

# “Footnote-ish” endings and dangling OCR fragments
DANGLING_END_RE = re.compile(r"(?:\b[i-vx]{1,6}\.\s*$)|(?:\b\d+\.\s*$)", re.IGNORECASE)

# Verse refs (often OK, but can make excerpt scripture-heavy)
SCRIPTURE_REF_RE = re.compile(r"\b\d{1,3}:\d{1,3}\b")

# Potentially polemical / inflammatory triggers (review, not auto-ban)
POLEMIC_TERMS = [
    "impostor",
    "self-deceived",
    "wrath of god",
    "everlasting punishment",
    "wicked",
]

SENSITIVE_GROUP_TERMS = [
    "jewish",
    "jews",
    "heathen",
    "infidel",
    "pagan",
    "mohammedan",  # old term appears in older texts sometimes
]

# “Needs context” starters
NEEDS_CONTEXT_STARTS = [
    "according to this view",
    "however",
    "therefore",
    "thus",
    "but",
    "and",
    "or",
    "this means",
    "hence",
]

GOOD_ANCHORS = [
    "we believe",
    "this means",
    "the word",
    "god is",
    "jesus christ",
    "the holy spirit",
]


def normalize(s: str) -> str:
    s = (s or "").replace(SOFT_HYPHEN, "")
    s = re.sub(r"\s*¬\s*", "", s)
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = WS_RE.sub(" ", s).strip()
    return s


def norm_key(s: str) -> str:
    s = normalize(s).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = WS_RE.sub(" ", s).strip()
    return s


def has_any(hay: str, needles: List[str]) -> bool:
    h = hay.lower()
    return any(n.lower() in h for n in needles)


def is_incomplete(text: str) -> bool:
    t = normalize(text)
    if not t:
        return True
    # Very short or no sentence punctuation
    if len(t) < 70:
        return True
    if not re.search(r"[.!?][\"']?\s*$", t):
        # allow semicolon endings sometimes, but still weak
        if not t.endswith(";"):
            return True
    if DANGLING_END_RE.search(t):
        return True
    return False


def scripture_density(text: str) -> int:
    return len(SCRIPTURE_REF_RE.findall(text))


def starts_needing_context(text: str) -> bool:
    t = normalize(text).lower()
    return any(t.startswith(p) for p in NEEDS_CONTEXT_STARTS)


@dataclass
class ReviewRow:
    author: str
    text: str
    doctrine: Any
    doctrine_label: Any
    source: Dict[str, Any]
    flags: List[str]


def classify(item: Dict[str, Any]) -> Tuple[str, ReviewRow]:
    raw = str(item.get("text", "") or "")
    text = normalize(raw)

    author = str(item.get("author") or "Handbook of Salvation Army Doctrine (1923)")
    doctrine = item.get("doctrine")
    doctrine_label = item.get("doctrine_label")
    source = item.get("source") or {
        "title": item.get("source_title"),
        "year": item.get("source_year"),
        "page": item.get("page"),
        "file": item.get("source_file"),
        "chapter": item.get("chapter"),
    }

    flags: List[str] = []

    if has_any(text, OCR_HEADER_MARKERS):
        flags.append("ocr_header")
    if has_any(text, STRUCTURE_MARKERS):
        flags.append("structure_marker")
    if "¬" in raw or SOFT_HYPHEN in raw:
        flags.append("ocr_hyphen_artifact")

    if is_incomplete(text):
        flags.append("incomplete_or_fragment")

    if starts_needing_context(text):
        flags.append("needs_context_opening")

    # Tone / sensitivity flags (review manually)
    if has_any(text, POLEMIC_TERMS):
        flags.append("polemical_language")
    if has_any(text, SENSITIVE_GROUP_TERMS):
        flags.append("sensitive_group_term")

    dens = scripture_density(text)
    if dens >= 2:
        flags.append("scripture_heavy")
    elif dens == 1:
        flags.append("scripture_present")

    # Promote if doctrinally anchored (reduces risk, but doesn't override flags)
    if has_any(text, GOOD_ANCHORS):
        flags.append("doctrinal_anchor")

    row = ReviewRow(
        author=author,
        text=text,
        doctrine=doctrine,
        doctrine_label=doctrine_label,
        source=source,
        flags=flags,
    )

    # Decision buckets
    if "incomplete_or_fragment" in flags and ("ocr_header" in flags or "structure_marker" in flags):
        return "drop", row

    if any(f in flags for f in ["polemical_language", "sensitive_group_term", "needs_context_opening", "ocr_header", "structure_marker"]):
        return "flag", row

    return "safe", row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="handbook_1923_quotes.json")
    ap.add_argument("--out-safe", default="handbook_quotes_safe.json")
    ap.add_argument("--out-flagged", default="handbook_quotes_flagged.json")
    ap.add_argument("--out-dropped", default="handbook_quotes_dropped.json")
    ap.add_argument("--out-report", default="handbook_review_report.json")
    args = ap.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))

    safe: List[ReviewRow] = []
    flagged: List[ReviewRow] = []
    dropped: List[ReviewRow] = []

    seen = set()
    dup_count = 0

    for item in data:
        bucket, row = classify(item)

        k = norm_key(row.text)
        if k in seen:
            dup_count += 1
            continue
        seen.add(k)

        if bucket == "safe":
            safe.append(row)
        elif bucket == "flag":
            flagged.append(row)
        else:
            dropped.append(row)

    def count_flags(rows: List[ReviewRow]) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for r in rows:
            for f in r.flags:
                c[f] = c.get(f, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

    report = {
        "input_items": len(data),
        "deduped_duplicates_skipped": dup_count,
        "safe": len(safe),
        "flagged": len(flagged),
        "dropped": len(dropped),
        "safe_flag_counts": count_flags(safe),
        "flagged_flag_counts": count_flags(flagged),
        "dropped_flag_counts": count_flags(dropped),
    }

    Path(args.out_safe).write_text(json.dumps([asdict(r) for r in safe], ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_flagged).write_text(json.dumps([asdict(r) for r in flagged], ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_dropped).write_text(json.dumps([asdict(r) for r in dropped], ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK]", report)
    print("wrote:", args.out_safe)
    print("wrote:", args.out_flagged)
    print("wrote:", args.out_dropped)
    print("wrote:", args.out_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

