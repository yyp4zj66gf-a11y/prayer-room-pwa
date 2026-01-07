# tools/collect_official_sa_quotes.py
"""
Collect quotes from a small allowlist of official Salvation Army pages.

Outputs a quotes.json compatible with Prayer Room PWA:
    [{"author":"...","text":"..."}, ...]

Safety:
- This script does NOT crawl. It only fetches URLs you pass in.
- You should still check the site's terms/permissions and keep attribution metadata for auditing.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Quote:
    author: str
    text: str
    source_url: str


CURly_QUOTE_RE = re.compile(r"‘([^’]{5,500})’")  # grabs text between ‘ ’
FOUNDERS_ITEM_RE = re.compile(r"^'(.+?)'\s*-\s*(.+?)\s*$")


def robots_allows(url: str, user_agent: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # If robots can't be read, fail closed or open? I prefer open for small allowlists,
        # but you can change to False if you want strict behavior.
        return True


def fetch_html(url: str, user_agent: str, timeout_s: int = 25) -> str:
    headers = {"User-Agent": user_agent}
    r = requests.get(url, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    return r.text


def extract_from_generals_page(html: str, source_url: str) -> List[Quote]:
    """
    Page has repeated pattern:
      ‘QUOTE’
      General Name (years)
    We'll parse text blocks and pair quote with next "General ..." line.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    quotes: List[Quote] = []

    i = 0
    while i < len(lines):
        m = CURly_QUOTE_RE.search(lines[i])
        if m:
            qtext = m.group(1).strip()
            # Look ahead for next line starting with "General "
            author = "The Salvation Army"
            j = i + 1
            while j < min(i + 6, len(lines)):
                if lines[j].startswith("General "):
                    author = lines[j].split("(")[0].strip()
                    break
                j += 1
            quotes.append(Quote(author=author, text=qtext, source_url=source_url))
        i += 1

    # Deduplicate exact matches
    seen = set()
    out: List[Quote] = []
    for q in quotes:
        key = (q.author, q.text)
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def extract_from_founders_day_page(html: str, source_url: str) -> List[Quote]:
    """
    Page contains a numbered list:
      1. '...' - Catherine Booth
    We'll scan lines and match that pattern.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    quotes: List[Quote] = []
    for ln in lines:
        # Strip leading "1. " / "10. "
        ln2 = re.sub(r"^\d+\.\s*", "", ln)
        m = FOUNDERS_ITEM_RE.match(ln2)
        if not m:
            continue
        qtext = m.group(1).strip()
        author = m.group(2).strip()
        quotes.append(Quote(author=author, text=qtext, source_url=source_url))

    return quotes


def to_pwa_quotes(quotes: Iterable[Quote]) -> List[dict]:
    return [{"author": q.author, "text": q.text} for q in quotes]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="quotes.json")
    ap.add_argument(
        "--url",
        action="append",
        required=True,
        help="Repeatable. e.g. --url https://www.salvationarmy.org/generals-salvation-army",
    )
    ap.add_argument("--user-agent", default="PrayerRoomQuoteCollector/1.0 (+respectful allowlist)")
    args = ap.parse_args()

    all_quotes: List[Quote] = []

    for url in args.url:
        if not robots_allows(url, args.user_agent):
            raise SystemExit(f"Blocked by robots.txt: {url}")

        html = fetch_html(url, args.user_agent)

        if "generals-salvation-army" in url:
            all_quotes.extend(extract_from_generals_page(html, url))
        elif "founders-day-quotes-william-and-catherine-booth" in url:
            all_quotes.extend(extract_from_founders_day_page(html, url))
        else:
            raise SystemExit(
                f"No extractor registered for: {url}\n"
                f"Add a site-specific extractor for this page."
            )

    # Write PWA format
    payload = to_pwa_quotes(all_quotes)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(payload)} quotes -> {args.out}")


if __name__ == "__main__":
    main()

