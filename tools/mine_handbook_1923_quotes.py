# tools/mine_handbook_1923_quotes.py
"""
Mine doctrine-aligned quote candidates from the 1923 Salvation Army doctrine handbook PDF
and output a curated set (default 365) with page attribution.

Input:
  - A single PDF (1923 handbook) with OCR/text layer.

Outputs:
  - handbook_1923_quotes_audit.json  (rich metadata; review this)
  - handbook_1923_quotes.json        (PWA-ready [{author,text,source,doctrine}] )

How it works (high level):
  - Extract text per page.
  - Detect CHAPTER roman numerals (I..XI) to determine topic region.
  - Split into sentence windows (1–3 sentences), score by doctrine keywords, and exclude scripture-heavy.
  - Select balanced quotes across 11 doctrines.

Install dependency if needed:
  python3 -m pip install --upgrade pdfplumber
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# ------------------------ Extraction ------------------------


def extract_pages_text(pdf_path: Path) -> List[str]:
    try:
        import pdfplumber  # type: ignore
    except Exception as e:
        raise SystemExit(
            "Missing dependency: pdfplumber\n"
            "Install it with:\n"
            "  python3 -m pip install --upgrade pdfplumber\n"
            f"Error: {type(e).__name__}: {e}"
        )

    texts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return texts


# ------------------------ Normalization ------------------------


WS_RE = re.compile(r"\s+")
HARD_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")  # e.g. "Out¬\nstanding" after OCR
LINE_BREAK_RE = re.compile(r"\n+")
PAGE_FURNITURE_RE = re.compile(r"^\s*\d+\s*$")  # standalone page numbers


def norm(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00ad", "")  # soft hyphen
    s = HARD_HYPHEN_BREAK_RE.sub(r"\1\2", s)
    s = s.replace("\r", "\n")
    s = LINE_BREAK_RE.sub("\n", s)
    # drop standalone page-number lines
    lines = []
    for line in s.splitlines():
        if PAGE_FURNITURE_RE.match(line):
            continue
        lines.append(line)
    s = "\n".join(lines)
    s = WS_RE.sub(" ", s).strip()
    return s


# ------------------------ Chapter detection ------------------------


CHAPTER_RE = re.compile(r"\bCHAPTER\s+([IVXLC]+)\b", re.IGNORECASE)

ROMAN_TO_INT: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
    "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
}

# Primary chapter-to-topic mapping (1923 table of contents style)
# We'll further split ambiguous chapters by keywords (e.g., God vs Trinity; Salvation vs Justification).
CHAPTER_TO_DOCTRINE_DEFAULT: Dict[int, int] = {
    2: 1,   # Bible -> Doctrine 1
    3: 2,   # God -> Doctrine 2 (Trinity may appear; we split by keywords)
    4: 4,   # Jesus Christ -> Doctrine 4
    5: 5,   # Man -> Doctrine 5
    6: 6,   # Redemption -> Doctrine 6
    7: 3,   # Holy Spirit -> Doctrine 3
    8: 7,   # Salvation -> Doctrine 7/8 (split)
    9: 9,   # Spiritual life -> Doctrine 9
    10: 10, # Entire sanctification -> Doctrine 10
    11: 11, # Last things -> Doctrine 11
}


# ------------------------ Doctrine scoring ------------------------


DOCTRINE_LABELS: Dict[int, str] = {
    1: "Scriptures",
    2: "One God",
    3: "Trinity",
    4: "Jesus Christ (God & Man)",
    5: "Fall / Depravity",
    6: "Atonement (for all)",
    7: "Repentance / Faith / Regeneration",
    8: "Justification by grace through faith",
    9: "Continuance in saving faith",
    10: "Sanctification",
    11: "Resurrection / Judgment / Eternity",
}

# Keyword signals to split ambiguous chapters:
KW_TRINITY = ["trinity", "father", "son", "holy spirit", "three persons", "triune"]
KW_JUSTIFICATION = ["justify", "justification", "righteousness imputed", "accounted righteous"]
KW_REGENERATION = ["regenerat", "new birth", "born again"]
KW_REPENT_FAITH = ["repent", "repentance", "faith", "believe", "conversion"]
KW_CONTINUANCE = ["continue", "persever", "keep", "abide", "backslid", "apostasy", "endure"]
KW_SANCTIFICATION = ["sanctif", "holiness", "entire sanctification", "perfect love"]
KW_ATONEMENT = ["atonement", "redeem", "redemption", "propitiation", "reconcile", "sacrifice"]
KW_FALL = ["fall", "deprav", "sinful", "guilty", "corrupt", "lost"]
KW_SCRIPTURE = ["scripture", "bible", "inspiration", "revelation", "testament"]
KW_LAST_THINGS = ["resurrection", "judgment", "eternal", "immortal", "heaven", "hell", "second coming"]


# Exclude scripture-heavy excerpts (we want doctrinal prose, not mostly Bible quotation)
BOOKS = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges","Ruth",
    "1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles","Ezra","Nehemiah","Esther",
    "Job","Psalms","Psalm","Proverbs","Ecclesiastes","Song of Solomon","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel",
    "Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk","Zephaniah","Haggai","Zechariah","Malachi",
    "Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians","Galatians","Ephesians","Philippians",
    "Colossians","1 Thessalonians","2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews","James",
    "1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
]
BOOK_RE = r"(?:[1-3]\s*)?(?:" + "|".join(re.escape(b) for b in BOOKS) + r")"
SCRIPTUREISH_RE = re.compile(
    rf"(\b\d{{1,3}}:\d{{1,3}}\b)|(\b{BOOK_RE}\b)",
    re.IGNORECASE,
)

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")


def contains_any(text: str, needles: Sequence[str]) -> bool:
    t = text.lower()
    return any(n in t for n in needles)


def doctrine_from_chapter_and_text(chapter: Optional[int], text: str) -> Optional[int]:
    if chapter is None:
        return None

    base = CHAPTER_TO_DOCTRINE_DEFAULT.get(chapter)
    if base is None:
        return None

    # Chapter III: God vs Trinity
    if chapter == 3 and contains_any(text, KW_TRINITY):
        return 3

    # Chapter VIII: Salvation vs Justification
    if chapter == 8:
        if contains_any(text, KW_JUSTIFICATION):
            return 8
        if contains_any(text, KW_REGENERATION) or contains_any(text, KW_REPENT_FAITH):
            return 7
        # fallback to 7
        return 7

    # Chapter IX: continuance/perseverance emphasis
    if chapter == 9 and contains_any(text, KW_CONTINUANCE):
        return 9

    return base


def score_excerpt(doctrine: int, excerpt: str) -> float:
    t = excerpt.lower()
    score = 0.0

    # Prefer definitional / doctrinal claims
    if any(k in t for k in ["we believe", "therefore", "means", "signifies", "is the", "are the", "must", "cannot"]):
        score += 1.8

    # Doctrine-specific boosts
    boosts: Dict[int, List[str]] = {
        1: KW_SCRIPTURE,
        2: ["one god", "god", "creator", "sovereign", "holy"],
        3: KW_TRINITY,
        4: ["jesus", "christ", "incarn", "deity", "human", "god and man"],
        5: KW_FALL,
        6: KW_ATONEMENT,
        7: KW_REPENT_FAITH + KW_REGENERATION,
        8: KW_JUSTIFICATION,
        9: KW_CONTINUANCE,
        10: KW_SANCTIFICATION,
        11: KW_LAST_THINGS,
    }

    for kw in boosts.get(doctrine, []):
        if kw in t:
            score += 0.35

    # Penalties
    if SCRIPTUREISH_RE.search(excerpt):
        score -= 2.5
    if len(excerpt) < 110:
        score -= 0.6
    if len(excerpt) > 320:
        score -= 0.6

    return score


# ------------------------ Candidate building ------------------------


@dataclass(frozen=True)
class Candidate:
    doctrine: Optional[int]
    doctrine_label: str
    text: str
    author: str
    source_title: str
    source_year: int
    source_file: str
    page: int
    chapter: Optional[int]
    score: float


def windows_from_sentences(sentences: List[str], max_sents: int) -> List[str]:
    out: List[str] = []
    n = len(sentences)
    for i in range(n):
        for w in range(1, max_sents + 1):
            if i + w > n:
                continue
            chunk = " ".join(sentences[i : i + w]).strip()
            if chunk:
                out.append(chunk)
    return out


def extract_candidates_from_page(
    page_text: str,
    page_number: int,
    chapter: Optional[int],
    source_title: str,
    source_year: int,
    source_file: str,
    min_len: int,
    max_len: int,
    max_sents: int,
) -> List[Candidate]:
    t = norm(page_text)
    if not t:
        return []

    # break into rough paragraphs then sentences
    # (OCR often comes as one long paragraph; this still works)
    sentences = [s.strip() for s in SENT_SPLIT_RE.split(t) if s.strip()]
    windows = windows_from_sentences(sentences, max_sents=max_sents)

    out: List[Candidate] = []
    for ex in windows:
        ex = ex.strip().strip(" -–—")
        if not (min_len <= len(ex) <= max_len):
            continue

        d = doctrine_from_chapter_and_text(chapter, ex)
        if d is None:
            continue

        sc = score_excerpt(d, ex)
        if sc < 1.8:
            continue

        out.append(
            Candidate(
                doctrine=d,
                doctrine_label=DOCTRINE_LABELS.get(d, f"Doctrine {d}"),
                text=ex,
                author=f"{source_title} ({source_year}), p. {page_number}",
                source_title=source_title,
                source_year=source_year,
                source_file=source_file,
                page=page_number,
                chapter=chapter,
                score=sc,
            )
        )

    return out


def dedupe(cands: Iterable[Candidate]) -> List[Candidate]:
    seen = set()
    out: List[Candidate] = []
    for c in sorted(cands, key=lambda x: (-x.score, x.page)):
        key = re.sub(r"[^a-z0-9]+", " ", c.text.lower()).strip()
        key = re.sub(r"\s+", " ", key)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def select_balanced(cands: List[Candidate], total: int) -> List[Candidate]:
    """
    Balanced selection across 11 doctrines. If some doctrines have fewer candidates,
    redistribute remaining slots to those with more.
    """
    buckets: Dict[int, List[Candidate]] = {d: [] for d in range(1, 12)}
    for c in cands:
        if c.doctrine in buckets:
            buckets[int(c.doctrine)].append(c)

    for d in buckets:
        buckets[d].sort(key=lambda x: (-x.score, x.page))

    base = total // 11
    remainder = total - base * 11

    selected: List[Candidate] = []
    # first pass: base per doctrine
    for d in range(1, 12):
        selected.extend(buckets[d][:base])

    # second pass: distribute remainder by best-available next candidates
    pointers = {d: base for d in range(1, 12)}
    while len(selected) < total:
        # pick doctrine that has best next candidate available
        best_d = None
        best_c = None
        for d in range(1, 12):
            idx = pointers[d]
            if idx < len(buckets[d]):
                c = buckets[d][idx]
                if best_c is None or c.score > best_c.score:
                    best_c = c
                    best_d = d
        if best_c is None:
            break
        selected.append(best_c)
        pointers[int(best_d)] += 1

    return selected[:total]


# ------------------------ CLI ------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to 1923 handbook PDF (handbookofsalvat00unse.pdf).")
    ap.add_argument("--out-audit", default="handbook_1923_quotes_audit.json")
    ap.add_argument("--out", default="handbook_1923_quotes.json")
    ap.add_argument("--min-len", type=int, default=120)
    ap.add_argument("--max-len", type=int, default=280)
    ap.add_argument("--max-sents", type=int, default=3, help="Max sentences per excerpt window (1-3 recommended).")
    ap.add_argument("--target", type=int, default=365, help="How many quotes to select for final output.")
    args = ap.parse_args(argv)

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    source_title = "Handbook of Salvation Army Doctrine"
    source_year = 1923

    pages = extract_pages_text(pdf_path)

    all_cands: List[Candidate] = []
    current_chapter: Optional[int] = None

    for i, raw in enumerate(pages, start=1):
        txt = raw or ""
        m = CHAPTER_RE.search(txt)
        if m:
            roman = m.group(1).upper()
            current_chapter = ROMAN_TO_INT.get(roman, current_chapter)

        all_cands.extend(
            extract_candidates_from_page(
                page_text=txt,
                page_number=i,
                chapter=current_chapter,
                source_title=source_title,
                source_year=source_year,
                source_file=pdf_path.name,
                min_len=args.min_len,
                max_len=args.max_len,
                max_sents=args.max_sents,
            )
        )

    all_cands = dedupe(all_cands)
    selected = select_balanced(all_cands, total=args.target)

    # Write audit (all candidates, so you can widen/curate later)
    audit_path = Path(args.out_audit).expanduser().resolve()
    audit_path.write_text(json.dumps([asdict(c) for c in all_cands], ensure_ascii=False, indent=2), encoding="utf-8")

    # Write final (selected)
    out_path = Path(args.out).expanduser().resolve()
    final = [
        {
            "author": c.author,
            "text": c.text,
            "doctrine": c.doctrine,
            "doctrine_label": c.doctrine_label,
            "source": {
                "title": c.source_title,
                "year": c.source_year,
                "page": c.page,
                "file": c.source_file,
                "chapter": c.chapter,
            },
        }
        for c in selected
    ]
    out_path.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary counts
    counts: Dict[str, int] = {}
    for c in selected:
        k = str(c.doctrine)
        counts[k] = counts.get(k, 0) + 1

    print(f"[OK] candidates_total={len(all_cands)} selected={len(selected)}")
    print(f"  wrote audit: {audit_path}")
    print(f"  wrote final: {out_path}")
    print(f"  selected_by_doctrine: {dict(sorted(counts.items(), key=lambda kv: int(kv[0])))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

