#!/usr/bin/env python3
"""build_universe_screener.py — EXHAUSTIVE, enumeration-driven cohort build.

Supersedes build_universe.py's market-wide BSE sweep. The sweep was high-precision
but leaked recall (late / mistagged filings — see check_missed.py). This instead
enumerates EVERY listed company from the exchange masters and asks screener, one
company at a time, "do you do concalls, and is the transcript downloadable?" —
so a wrong BSE subcategory tag can no longer hide a company.

Flow:
  1. Master = BSE active-equity list ∪ NSE EQUITY_L (deduped by ISIN). ~5,200 names.
  2. Pre-filter by the BSE-reported market cap to <= --cap-max (keeps blanks, and
     keeps all NSE-only rows, which have no BSE mcap) — avoids crawling the few
     hundred giant-caps the experiment doesn't care about.
  3. For each survivor: fetch (and cache) its screener page once, reading in a
     SINGLE request — current mcap, sector/industry, and the full Concalls list.
     This folds the old build_universe + concall lookup into one pass.
  4. Classify against --target-fy / --target-quarter (default Q4 FY24):
       does_concalls   — screener shows ANY concall row (even with no link)
       transcript_url  — link for the target quarter, if screener exposes one
       transcript_src  — screener | none
     Cohort = does concalls AND in cap. download_screener.py then prefers the
     screener link and falls back to a targeted per-scrip BSE lookup; only a
     company with NEITHER is ignored. nolink (concalls but no screener link) is
     logged to universe_screener_nolink.csv so it's visible which rows rely on
     the BSE fallback.

Resumable: every screener page is cached under .cache/screener (shared with
build_universe.py), and outputs are rewritten after each batch, so a stop/restart
re-reads from cache instead of re-fetching. Self-heals through 429s with backoff.

Outputs (this folder):
  universe_screener.csv      cohort: mcap<=cap AND does_concalls, sorted by mcap
  universe_screener_all.csv  EVERY crawled company + status (audit / recall proof)
  universe_screener_nolink.csv  does-concalls-but-no-screener-link (BSE fallback)

Usage:
  python build_universe_screener.py --limit 50        # smoke test
  python build_universe_screener.py                   # full crawl (~1-2 h)
  python build_universe_screener.py --cap-max 50000 --target-fy 2024 --target-quarter Q4
"""
from __future__ import annotations
import argparse, csv, sys, time, urllib.error, urllib.request
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
COHORT_CSV = HERE / "universe_screener.csv"
ALL_CSV = HERE / "universe_screener_all.csv"
NOLINK_CSV = HERE / "universe_screener_nolink.csv"
CACHE = HERE / ".cache" / "screener"

COHORT_FIELDS = ["company_name", "ticker", "scrip", "isin", "exchanges",
                 "market_cap_cr", "sector", "industry", "concall_date",
                 "transcript_url", "transcript_src", "concall_count"]
ALL_FIELDS = ["company_name", "ticker", "scrip", "isin", "exchanges",
              "market_cap_cr", "does_concalls", "has_target_call",
              "transcript_src", "status"]


def _fetch(url: str) -> tuple[str, str]:
    """(html, status). status: ok | notfound | throttled | error."""
    req = urllib.request.Request(url, headers={"User-Agent": B.UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.read().decode("utf-8", "replace"), "ok"
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return "", "throttled"
        if e.code == 404:
            return "", "notfound"
        return "", "error"
    except Exception:
        return "", "error"


def cached_screener_html(scrip: str, ticker: str, pause: float,
                         max_retries: int = 5) -> tuple[str, str]:
    """Screener page HTML, cached so reruns resume. status: cached|ok|throttled|
    notfound|error. Tries scrip first (stable id screener resolves directly),
    then NSE ticker (for NSE-only names with no scrip). Cache key = scrip or
    ticker. Self-heals through 429 with exponential backoff (8,16,..s, cap 90)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = scrip or ticker
    fp = CACHE / f"{key}.html"
    if fp.exists() and fp.stat().st_size > 500:
        return fp.read_text(encoding="utf-8", errors="replace"), "cached"
    last = "notfound"
    for attempt in range(max_retries):
        throttled = False
        for ident in (scrip, ticker):
            if not ident:
                continue
            html, status = _fetch(B.screener_url(ident))
            time.sleep(pause)
            if status == "ok" and 'id="top-ratios"' in html:
                fp.write_text(html, encoding="utf-8")
                return html, "ok"
            if status == "throttled":
                throttled = True
                break
            last = status
        if not throttled:
            return "", last
        backoff = min(90, 8 * (2 ** attempt))
        print(f"      …429 throttled, backoff {backoff}s "
              f"(attempt {attempt + 1}/{max_retries})")
        time.sleep(backoff)
    return "", "throttled"


def load_master(cap_max: float) -> list[dict]:
    """BSE ∪ NSE master, pre-filtered to bse_mcap <= cap_max. Rows with no BSE
    mcap (blank, or NSE-only) are KEPT — their real mcap is read from screener."""
    print("[1/3] Fetching exchange masters (BSE active equity + NSE EQUITY_L)")
    bse = B.bse_active_equity()
    nse = B.nse_equity_list()
    master = B.union_masters(bse, nse)
    print(f"      BSE={len(bse)}  NSE={len(nse)}  union={len(master)}")
    kept = [r for r in master
            if r["bse_mcap_cr"] is None or r["bse_mcap_cr"] <= cap_max]
    dropped = len(master) - len(kept)
    print(f"      pre-filter bse_mcap<=₹{cap_max:,.0f}cr: keep {len(kept)}, "
          f"drop {dropped} giant-caps (real cap reconfirmed from screener)")
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description="Exhaustive screener concall crawl.")
    ap.add_argument("--cap-max", type=float, default=50000.0)
    ap.add_argument("--target-fy", type=int, default=2024)
    ap.add_argument("--target-quarter", default="Q4",
                    choices=["Q1", "Q2", "Q3", "Q4"])
    ap.add_argument("--limit", type=int, default=None,
                    help="only crawl the first N companies (smoke test)")
    ap.add_argument("--pause", type=float, default=0.6,
                    help="seconds between live screener fetches (0.6 avoids 429s)")
    ap.add_argument("--batch-size", type=int, default=50)
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    master = load_master(args.cap_max)
    if args.limit:
        master = master[:args.limit]
        print(f"      --limit {args.limit}: crawling first {len(master)}")
    n = len(master)
    nbatches = (n + args.batch_size - 1) // args.batch_size
    fy, q = args.target_fy, args.target_quarter
    print(f"\n[2/3] Crawling screener for {n} companies — concalls + cap + "
          f"sector (target {q} FY{fy % 100:02d}); {nbatches} batches\n")

    cohort, everything, nolink = [], [], []
    for b in range(nbatches):
        lo, hi = b * args.batch_size, min((b + 1) * args.batch_size, n)
        bk = bnocall = bnolink = bovercap = bunres = bcache = bthr = 0
        for i in range(lo, hi):
            c = master[i]
            html, st = cached_screener_html(c["scrip"], c["ticker"], args.pause)
            bcache += st == "cached"
            bthr += st == "throttled"
            name = c["name"] or B.screener_name(html) or c["ticker"] or c["scrip"]

            if not html:
                bunres += 1
                everything.append({**_base(c, name), "market_cap_cr": "",
                                   "does_concalls": "", "has_target_call": "",
                                   "transcript_src": "", "status": f"unresolved:{st}"})
                print(f"  [{i+1}/{n}] {name[:36]:36} UNRESOLVED ({st})")
                continue

            mcap = B.screener_market_cap(html)
            sector, industry = B.screener_sector_industry(html)
            concalls = B.screener_concalls(html)
            does = bool(concalls)
            hit = B.pick_concall(concalls, fy, q)
            url = hit["transcript_url"] if hit else None
            src = "screener" if url else "none"
            over = mcap is not None and mcap > args.cap_max

            # Cohort = does concalls AND in cap. The transcript link may be empty:
            # download_screener.py tries screener first, then a BSE fallback, and
            # only a company with NEITHER is ignored. nolink (no screener link) is
            # recorded so it's visible which rows lean on the BSE fallback.
            if over:
                bovercap += 1
                status = "over_cap"
                tag = f"drop ₹{mcap:,.0f}cr (>cap)"
            elif not does:
                bnocall += 1
                status = "no_concalls"
                tag = "no concalls"
            else:
                bk += 1
                status = "kept"
                cohort.append({
                    "company_name": name, "ticker": c["ticker"], "scrip": c["scrip"],
                    "isin": c["isin"], "exchanges": c["exchanges"],
                    "market_cap_cr": round(mcap, 1) if mcap is not None else "",
                    "sector": sector or "", "industry": industry or "",
                    "concall_date": hit["date"] if hit else "",
                    "transcript_url": url or "", "transcript_src": src,
                    "concall_count": len(concalls),
                })
                if not url:  # does concalls + in cap, but screener has no link
                    bnolink += 1
                    nolink.append({"company_name": name, "ticker": c["ticker"],
                                   "scrip": c["scrip"], "has_target_call": bool(hit),
                                   "concall_date": hit["date"] if hit else ""})
                tag = (f"KEEP ₹{mcap:,.0f}cr [{src}{'' if url else ' →BSE'}]"
                       if mcap is not None else f"KEEP [{src}]")

            everything.append({**_base(c, name),
                               "market_cap_cr": round(mcap, 1) if mcap is not None else "",
                               "does_concalls": does, "has_target_call": bool(hit),
                               "transcript_src": src, "status": status})
            print(f"  [{i+1}/{n}] {name[:36]:36} {tag}")

        _write(cohort, everything, nolink)
        warn = "  ⚠ THROTTLED — raise --pause" if bthr else ""
        print(f"--- batch {b+1}/{nbatches} [{lo+1}-{hi}]: keep={bk} "
              f"no_concall={bnocall} no_link={bnolink} over_cap={bovercap} "
              f"unresolved={bunres} (cached={bcache}) | cohort={len(cohort)}{warn}\n")

    linked = sum(1 for r in cohort if r["transcript_src"] == "screener")
    print(f"[3/3] Done. crawled={len(everything)}  cohort(concalls, <=cap)="
          f"{len(cohort)}  with screener link={linked}  "
          f"lean on BSE fallback={len(nolink)}")
    print(f"  -> {COHORT_CSV.name}  {ALL_CSV.name}  {NOLINK_CSV.name}")


def _base(c: dict, name: str) -> dict:
    return {"company_name": name, "ticker": c["ticker"], "scrip": c["scrip"],
            "isin": c["isin"], "exchanges": c["exchanges"]}


def _write(cohort: list[dict], everything: list[dict], nolink: list[dict]) -> None:
    with open(COHORT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COHORT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(cohort, key=lambda r: (
            r["market_cap_cr"] if isinstance(r["market_cap_cr"], (int, float))
            else 1e12)))
    with open(ALL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ALL_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(everything)
    with open(NOLINK_CSV, "w", newline="", encoding="utf-8") as f:
        cols = ["company_name", "ticker", "scrip", "has_target_call", "concall_date"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(nolink)


if __name__ == "__main__":
    main()
