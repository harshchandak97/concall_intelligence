#!/usr/bin/env python3
"""lib_extract.py — self-contained extraction helpers for steps 3-4.

Two jobs, no imports from the production pipeline (the experiment stays isolated
in this folder — see README):
  * extract_text()       — PDF -> plain text (pdfplumber), copied from the repo's
                           run.py so the cheap model and the Opus-4.8 reference
                           read text produced exactly the same way.
  * usable_transcripts() — the cohort rows whose transcript actually downloaded
                           cleanly (download_log status OK/SKIP), joined to the
                           universe so each carries market_cap_cr for sampling.
"""
from __future__ import annotations
import csv
import re
from pathlib import Path

import pdfplumber

HERE = Path(__file__).parent
COHORT_CSV = HERE / "universe_with_concalls.csv"
LOG_CSV = HERE / "download_log.csv"
TRANSCRIPTS = HERE / "transcripts"

# download_log statuses that mean "a real transcript is on disk".
# OK = downloaded & page-count looked like a transcript; SKIP = already present.
USABLE = {"OK", "SKIP"}


def _slugify(name: str) -> str:
    """Mirror of download_concalls/lib_bse slugify, used only as a fallback when
    a cohort row has no slug (so the derived filename matches what was saved)."""
    name = re.sub(r"\b(Ltd|Limited)\.?\b", "", name, flags=re.I)
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()


def extract_text(pdf_path: Path | str) -> str:
    """All page text, each page prefixed '[Page N]'. Copied from run.py:extract_text."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages.append(f"[Page {i + 1}]\n{text}")
    return "\n\n".join(pages)


def _usable_files() -> set[str]:
    """Filenames (e.g. 'foo_Q4_FY24.pdf') whose download_log status is usable."""
    if not LOG_CSV.exists():
        return set()
    out = set()
    for r in csv.DictReader(open(LOG_CSV, encoding="utf-8")):
        # status can be 'OK', 'COVER?', 'SKIP', 'NOTPDF', or 'FAIL:<reason>'
        if r["status"].split(":")[0] in USABLE:
            out.add(r["file"])
    return out


def usable_transcripts() -> list[dict]:
    """Cohort rows with a cleanly-downloaded transcript present on disk.

    Each dict is the universe row (company_name, slug, market_cap_cr, ...) plus:
      slug  — resolved slug (cohort slug, or slugified name as fallback)
      file  — '{slug}_Q4_FY24.pdf'
      path  — Path to the PDF under transcripts/
    Rows whose PDF is missing from disk are dropped (belt-and-suspenders over the
    status filter). Sorted by market_cap_cr ascending for stable sampling.
    """
    usable = _usable_files()
    rows = []
    for r in csv.DictReader(open(COHORT_CSV, encoding="utf-8")):
        slug = r.get("slug") or _slugify(r["company_name"])
        fname = f"{slug}_Q4_FY24.pdf"
        path = TRANSCRIPTS / fname
        if fname not in usable or not path.exists():
            continue
        try:
            mcap = float(r["market_cap_cr"])
        except (TypeError, ValueError):
            mcap = float("inf")  # sort unknowns last; shouldn't happen for the cohort
        rows.append({**r, "slug": slug, "file": fname, "path": path,
                     "market_cap_cr": mcap})
    rows.sort(key=lambda x: x["market_cap_cr"])
    return rows


def sample(rows: list[dict], n: int) -> list[dict]:
    """Deterministic stride sample of `n` rows spanning the (mcap-sorted) range.
    Picks evenly-spaced indices so the sample covers ₹-small -> ₹-large, a proxy
    for sector/style diversity (no sector tags available)."""
    if n >= len(rows):
        return rows
    step = len(rows) / n
    idx = sorted({min(len(rows) - 1, int(i * step)) for i in range(n)})
    return [rows[i] for i in idx]


if __name__ == "__main__":
    rows = usable_transcripts()
    print(f"usable transcripts: {len(rows)}")
    if rows:
        lo, hi = rows[0], rows[-1]
        print(f"  mcap range: ₹{lo['market_cap_cr']:,.0f}cr ({lo['slug']}) "
              f"-> ₹{hi['market_cap_cr']:,.0f}cr ({hi['slug']})")
        s = sample(rows, 25)
        print(f"  stride sample of 25: {len(s)} rows")
        for r in s:
            print(f"    ₹{r['market_cap_cr']:>9,.0f}cr  {r['slug']}")
