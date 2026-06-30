#!/usr/bin/env python3
"""enrich_universe.py — add `sector` and `industry` columns to the cohort.

Reads each company's screener page from the build_universe cache
(.cache/screener/{bse_scrip}.html) and parses its sector + industry, so that
when you review the extraction output you can reject sector-mismatched targets
(real-estate pre-sales, lender AUM, etc.) by eye. No network calls — purely
from the cache already produced by build_universe.py.

Rewrites universe_with_concalls.csv in place with the two columns appended
(idempotent — safe to re-run).

Usage:  python enrich_universe.py
"""
from __future__ import annotations
import csv
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
COHORT = HERE / "universe_with_concalls.csv"
CACHE = HERE / ".cache" / "screener"


def main() -> None:
    rows = list(csv.DictReader(open(COHORT, encoding="utf-8")))
    base_cols = ["company_name", "nse_ticker", "slug", "bse_scrip",
                 "market_cap_cr", "concall_date", "attachment", "headline"]
    hit = miss = 0
    for r in rows:
        fp = CACHE / f"{r['bse_scrip']}.html"
        if fp.exists() and fp.stat().st_size > 500:
            sector, industry = B.screener_sector_industry(
                fp.read_text(encoding="utf-8", errors="replace"))
            r["sector"], r["industry"] = sector or "", industry or ""
            hit += 1 if (sector or industry) else 0
            if not (sector or industry):
                miss += 1
        else:
            r["sector"], r["industry"] = "", ""
            miss += 1

    with open(COHORT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=base_cols + ["sector", "industry"])
        w.writeheader()
        w.writerows(rows)

    print(f"enriched {len(rows)} companies: {hit} with sector/industry, "
          f"{miss} missing (no cache / unparsed)  -> {COHORT.name}")
    # quick sector tally so you can see what's in the universe
    from collections import Counter
    tally = Counter(r["sector"] for r in rows if r["sector"])
    print("\ntop sectors:")
    for sec, n in tally.most_common(15):
        print(f"  {n:4}  {sec}")


if __name__ == "__main__":
    main()
