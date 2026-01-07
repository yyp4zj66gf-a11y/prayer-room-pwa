# tools/mine_handbook_quotes.py
"""
Mine doctrine-aligned, attributed quote candidates from Salvation Army doctrine handbooks (PDFs).

Outputs:
- quotes_audit.json: rich records with doctrine guess + page attribution.
- (optional) quotes.json: PWA-ready minimal [{author,text,source}] list.

Notes:
- This tool extracts *short excerpts*; you still curate before shipping.
- For copyrighted sources (e.g., modern editions), keep excerpts short and attribute clearly.

Usage:
  python3 tools/mine_handbook_quotes.py \
    --pdf "English Handbook of Doctrine web.pdf" \
    --pdf "handbookofsalvat00unse.pdf" \
    --out-audit quotes_audit.json \
    --out quotes.json \
    --min-len 80 --max-len 260 \
    --max-per-doctrine 60

If you don't have dependencies:
  pip install --upgrade pypdf
Optional (better extraction):
  pip install --upgrade pdfplumber
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ---------- PDF text extraction ----------


def extract_pages_text(pdf_path: Path) -> List[str]:
    """
    Return list of page texts (1 item per page).

    Tries pdfplumber first for better layout, falls back to pypdf.
    """
    try:
        import pdfplumber  # type: ignore

        texts: List[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
        return texts
    except Exception:
        pass

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as e:
        raise SystemExit(
            f"Failed to read PDF: {pdf_path}\n"
            f"Install dependencies:\n"
            f"  pip install --upgrade pypdf pdfplumber\n"
            f"Error: {type(e).__name__}: {e}"
        )


# ---------- Doctrine detection ----------


CHAPTER_2010_RE = re.compile(r"\bChapter\s+(\d{1,2})\b", re.IGNORECASE)
CHAPTER_ROMAN_1923_RE = re.compile(r"\bCHAPTER\s+([IVXLC]+)\b", re.IGNORECASE)

ROMAN_MAP: Dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
}

# A pragmatic mapping for 1923 chapters -> doctrine buckets.
# It's not perfect, but gets you very close for curation.
CHAPTER_1923_TO_DOCTRINE: Dict[int, int] = {
    2: 1,   # The Bible -> Doctrine 1
    3: 2,   # God -> Doctrine 2 (and contains Trinity too)
    4: 4,   # Jesus Christ -> Doctrine 4
    5: 5,   # Man -> Doctrine 5
    6: 6,   # Redemption -> Doctrine 6
    7: 3,   # Holy Spirit -> Doctrine 3 emphasis (also supports 7)
    8: 7,   # Salvation -> Doctrine 7/8; bucket under 7 by default
    9: 9,   # The Spiritual Life -> Doctrine 9
    10: 10, # Entire Sanctification -> Doctrine 10
    11: 11, # Last Things -> Doctrine 11
}


def guess_source_meta(pdf_path: Path) -> Tuple[str, Optional[int]]:
    """
    Infer title + year from filename.
    """
    name = pdf_path.name.lower()
    if "2010" in name or "english handbook" in name:
        return ("The Salvation Army Handbook of Doctrine", 2010)
    if "handbookofsalvat" in name or "1923" in name:
        return ("Handbook of Salvation Army Doctrine", 1923)
    return (pdf_path.stem, None)


def guess_doctrine_from_page(
    pdf_title: str,
    pdf_year: Optional[int],
    page_text: str,
    last_doctrine: Optional[int],
    last_chapter_roman: Optional[int],
) -> Tuple[Optional[int], Optional[int]]:
    """
    Returns:
      (doctrine_number_guess, chapter_roman_guess_for_1923)
    """
    text = page_text or ""

    # 2010 edition: chapters are numbered to doctrines (1-11).
    m = CHAPTER_2010_RE.search(text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 11:
            return n, last_chapter_roman

    # 1923 edition: chapters are roman numerals.
    mr = CHAPTER_ROMAN_1923_RE.search(text)
    chapter_roman = last_chapter_roman
    if mr:
        roman = mr.group(1).upper()
        chapter_roman = ROMAN_MAP.get(roman, chapter_roman)

    if pdf_year == 1923 and chapter_roman:
        return CHAPTER_1923_TO_DOCTRINE.get(chapter_roman, last_doctrine), chapter_roman

    # fallback: keep previous
    return last_doctrine, chapter_roman


# ---------- Quote mining ----------


SCRIPTURE_REF_RE = re.compile(
    r"\b("
    r"Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"1\s*Samuel|2\s*Samuel|1\s*Kings|2\s*Kings|1\s*Chronicles|2\s*Chronicles|"
    r"Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song of Solomon|"
    r"Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|"
    r"Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    r"Matthew|Mark|Luke|John|Acts|Romans|1\s*Corinthians|2\s*Corinthians|"
    r"Galatians|Ephesians|Philippians|Colossians|1\s*Thessalonians|2\s*Thessalonians|"
    r"1\s*Timothy|2\s*Timothy|Titus|Philemon|Hebrews|James|1\s*Peter|2\s*Peter|"
    r"1\s*John|2\s*John|3\s*John|Jude|Revelation"
    r")\b",
    re.IGNORECASE,
)

# detect “quoted blocks” and "..."
QUOTED_BLOCK_RE = re.compile(r"[“\"]([^”\"]{40,400}?)[”\"]", re.DOTALL)

AUTHOR_LINE_RE = re.compile(
    r"^\s*([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s*$"
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def looks_like_scripture_heavy(s: str) -> bool:
    # too many refs or verse-like patterns
    if SCRIPTURE_REF_RE.search(s):
        return True
    if re.search(r"\b\d{1,3}:\d{1,3}\b", s):
        return True
    return False


def score_sentence(s: str) -> float:
    """
    Heuristic score for 'theological / doctrinal' sentences.
    Higher = more likely quote-worthy for doctrine reflections.
    """
    base = 0.0
    t = s.lower()

    if any(k in t for k in ["we believe", "therefore", "means", "signifies", "is the", "are the", "must", "cannot"]):
        base += 2.0
    if any(k in t for k in ["holiness", "sanctif", "atonement", "grace", "faith", "repent", "justif", "regenerat", "resurrection", "judgment"]):
        base += 1.5
    if looks_like_scripture_heavy(s):
        base -= 2.0
    if len(s) < 80:
        base -= 1.0
    if len(s) > 320:
        base -= 1.0
    return base


@dataclass(frozen=True)
class QuoteCandidate:
    doctrine: Optional[int]
    author: str
    text: str
    source_title: str
    source_year: Optional[int]
    source_file: str
    page: int  # 1-based
    kind: str  # "quoted" | "sentence"
    confidence: float


def extract_candidates_from_page(
    page_text: str,
    doctrine: Optional[int],
    source_title: str,
    source_year: Optional[int],
    source_file: str,
    page_number: int,
    min_len: int,
    max_len: int,
) -> List[QuoteCandidate]:
    txt = page_text or ""
    if not txt.strip():
        return []

    lines = [normalize_text(x) for x in txt.splitlines() if normalize_text(x)]
    joined = "\n".join(lines)

    out: List[QuoteCandidate] = []

    # 1) Quoted blocks
    for m in QUOTED_BLOCK_RE.finditer(joined):
        q = normalize_text(m.group(1))
        if not (min_len <= len(q) <= max_len):
            continue

        # Try to find author line immediately after quote by looking at subsequent lines
        # near the quote's end position.
        author = source_title
        tail = joined[m.end() : m.end() + 220]
        tail_lines = [normalize_text(x) for x in tail.splitlines() if normalize_text(x)]
        if tail_lines:
            am = AUTHOR_LINE_RE.match(tail_lines[0])
            if am:
                author = am.group(1)

        conf = 0.75 if author != source_title else 0.55
        out.append(
            QuoteCandidate(
                doctrine=doctrine,
                author=author,
                text=q,
                source_title=source_title,
                source_year=source_year,
                source_file=source_file,
                page=page_number,
                kind="quoted",
                confidence=conf,
            )
        )

    # 2) Strong doctrinal sentences
    # Convert to sentences but keep only those that read like teaching statements.
    sentences: List[str] = []
    for para in re.split(r"\n{1,}", joined):
        para = normalize_text(para)
        if not para:
            continue
        sentences.extend(SENTENCE_SPLIT_RE.split(para))

    for s in sentences:
        s = normalize_text(s)
        if not (min_len <= len(s) <= max_len):
            continue
        sc = score_sentence(s)
        if sc < 1.75:
            continue
        out.append(
            QuoteCandidate(
                doctrine=doctrine,
                author=source_title,
                text=s,
                source_title=source_title,
                source_year=source_year,
                source_file=source_file,
                page=page_number,
                kind="sentence",
                confidence=min(0.9, 0.5 + sc / 4.0),
            )
        )

    return out


def dedupe_candidates(items: Sequence[QuoteCandidate]) -> List[QuoteCandidate]:
    seen: set[str] = set()
    out: List[QuoteCandidate] = []
    for it in sorted(items, key=lambda x: (-x.confidence, x.page, x.kind)):
        key = normalize_text(it.text).lower()
        key = re.sub(r"[^a-z0-9 ]+", "", key)
        key = re.sub(r"\s+", " ", key).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def cap_per_doctrine(items: Sequence[QuoteCandidate], max_per_doctrine: int) -> List[QuoteCandidate]:
    by: Dict[str, List[QuoteCandidate]] = {}
    for it in items:
        d = str(it.doctrine or "unknown")
        by.setdefault(d, []).append(it)

    out: List[QuoteCandidate] = []
    for d, arr in by.items():
        arr_sorted = sorted(arr, key=lambda x: (-x.confidence, x.page))
        out.extend(arr_sorted[:max_per_doctrine])
    return out


# ---------- CLI ----------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", action="append", required=True, help="Path to PDF (repeatable).")
    p.add_argument("--out-audit", default="quotes_audit.json", help="Audit JSON output path.")
    p.add_argument("--out", default=None, help="Optional minimal quotes.json output path.")
    p.add_argument("--min-len", type=int, default=80, help="Minimum candidate length.")
    p.add_argument("--max-len", type=int, default=260, help="Maximum candidate length.")
    p.add_argument("--max-per-doctrine", type=int, default=80, help="Cap candidates per doctrine bucket.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    pdf_paths = [Path(x).expanduser().resolve() for x in args.pdf]
    for p in pdf_paths:
        if not p.exists():
            raise SystemExit(f"PDF not found: {p}")

    all_candidates: List[QuoteCandidate] = []

    for pdf_path in pdf_paths:
        title, year = guess_source_meta(pdf_path)
        pages = extract_pages_text(pdf_path)

        last_doctrine: Optional[int] = None
        last_chapter_roman: Optional[int] = None

        for idx, page_text in enumerate(pages):
            doctrine, last_chapter_roman = guess_doctrine_from_page(
                pdf_title=title,
                pdf_year=year,
                page_text=page_text,
                last_doctrine=last_doctrine,
                last_chapter_roman=last_chapter_roman,
            )
            last_doctrine = doctrine

            cands = extract_candidates_from_page(
                page_text=page_text,
                doctrine=doctrine,
                source_title=title,
                source_year=year,
                source_file=str(pdf_path.name),
                page_number=idx + 1,
                min_len=args.min_len,
                max_len=args.max_len,
            )
            all_candidates.extend(cands)

    all_candidates = dedupe_candidates(all_candidates)
    all_candidates = cap_per_doctrine(all_candidates, args.max_per_doctrine)

    audit_path = Path(args.out_audit).expanduser().resolve()
    audit_payload = [asdict(x) for x in all_candidates]
    audit_path.write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        minimal = [
            {
                "author": x.author,
                "text": x.text,
                "source": {
                    "title": x.source_title,
                    "year": x.source_year,
                    "page": x.page,
                    "file": x.source_file,
                    "doctrine": x.doctrine,
                },
            }
            for x in all_candidates
        ]
        out_path.write_text(json.dumps(minimal, ensure_ascii=False, indent=2), encoding="utf-8")

    # small terminal summary
    doctrine_counts: Dict[str, int] = {}
    for x in all_candidates:
        key = str(x.doctrine or "unknown")
        doctrine_counts[key] = doctrine_counts.get(key, 0) + 1

    print(f"[OK] candidates_written={len(all_candidates)}")
    print(f"  audit: {audit_path}")
    if args.out:
        print(f"  quotes: {Path(args.out).expanduser().resolve()}")
    print(f"  by_doctrine: {dict(sorted(doctrine_counts.items(), key=lambda kv: kv[0]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

