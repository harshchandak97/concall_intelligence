#!/usr/bin/env python3
"""build_universe.py — STEPS 1-2 of the guidance-acceleration experiment.

Produces the cohort: every company that held a Q4 FY24 earnings concall AND has a
current market cap at or below the cap (default ₹50,000 cr).

Flow (this is the cheap ordering — same cohort, far fewer requests than scanning
the whole ~5,000-name exchange through screener):
  1. MARKET-WIDE BSE sweep of "Earnings Call Transcript" filings in the Q4 FY24
     results window (Apr 1 – Jun 30 2024) -> every company with a Q4 FY24 concall,
     with scrip, filing date (~the call date), NSE ticker and the PDF attachment.
  2. For each, read CURRENT market cap from its screener page and keep it if
     market_cap_cr <= --cap-max. (Per the owner: current screener mcap, ≤50,000cr.)

Outputs (in this folder):
  universe_with_concalls.csv  — the cohort, fed to download_concalls.py
  universe_unresolved.csv     — concall companies whose mcap couldn't be read
                                (delisted / screener miss) — logged, not dropped.

Usage:
  python build_universe.py                       # full Q4 FY24 build
  python build_universe.py --limit 30            # quick slice for testing
  python build_universe.py --cap-max 50000 --from 20240401 --to 20240630
"""
from __future__ import annotations
import argparse, csv, sys, time, urllib.error, urllib.request
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
COHORT_CSV = HERE / "universe_with_concalls.csv"
UNRESOLVED_CSV = HERE / "universe_unresolved.csv"
ALL_CSV = HERE / "universe_all.csv"
CACHE = HERE / ".cache" / "screener"

FIELDS = ["company_name", "nse_ticker", "slug", "bse_scrip",
          "market_cap_cr", "concall_date", "attachment", "headline"]
ALL_FIELDS = ["company_name", "nse_ticker", "bse_scrip", "market_cap_cr",
              "status", "concall_date"]


def _fetch(url: str) -> tuple[str, str]:
    """(html, status) for one URL. status: ok | notfound | throttled | error."""
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
    """Fetch a company's screener page, caching to .cache so reruns resume.

    Returns (html, status). status: cached | ok | throttled | notfound | error.
    Tries the NSE ticker first then the BSE scrip: the BSE announcements feed
    sometimes reports a mangled scrip code (e.g. BPCL as 100547 instead of
    500547) that 404s on screener, while the NSE ticker from the NSURL is
    reliable. Cache is keyed by scrip (stable id).

    On HTTP 429 it self-heals: exponential backoff (8,16,32,..s, capped 90s)
    and retry, so a run completes through screener's rate limit instead of
    dropping names."""
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / f"{scrip}.html"
    if fp.exists() and fp.stat().st_size > 500:
        return fp.read_text(encoding="utf-8", errors="replace"), "cached"
    last = "notfound"
    for attempt in range(max_retries):
        throttled = False
        for ident in [ticker, scrip]:
            if not ident:
                continue
            html, status = _fetch(B.screener_url(ident))
            time.sleep(pause)  # be polite on every real fetch
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Q4 FY24 concall cohort.")
    ap.add_argument("--from", dest="frm", default="20240401",
                    help="sweep start YYYYMMDD (default 20240401)")
    ap.add_argument("--to", default="20240630",
                    help="sweep end YYYYMMDD (default 20240630)")
    ap.add_argument("--cap-max", type=float, default=50000.0,
                    help="keep companies with current market cap <= this (₹ cr)")
    ap.add_argument("--limit", type=int, default=None,
                    help="only process the first N concall companies (testing)")
    ap.add_argument("--pause", type=float, default=0.6,
                    help="seconds between live screener fetches (0.6 avoids 429s)")
    ap.add_argument("--batch-size", type=int, default=50,
                    help="companies per batch; a summary prints after each")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # stream batch summaries live

    print(f"[1/2] BSE market-wide transcript sweep {args.frm}..{args.to}")
    rows = B.bse_transcript_sweep(args.frm, args.to)
    companies = B.dedup_earliest(rows)
    print(f"      {len(rows)} filings -> {len(companies)} unique companies "
          f"with a Q4 FY24 concall")
    if args.limit:
        companies = companies[:args.limit]
        print(f"      --limit {args.limit}: processing first {len(companies)}")

    n = len(companies)
    nbatches = (n + args.batch_size - 1) // args.batch_size
    print(f"[2/2] Reading current market cap from screener (cap <= "
          f"₹{args.cap_max:,.0f} cr) — {nbatches} batches of {args.batch_size}\n")

    kept, unresolved, everything = [], [], []
    for b in range(nbatches):
        lo, hi = b * args.batch_size, min((b + 1) * args.batch_size, n)
        bk = bd = bu = bcache = bthrottle = 0
        for i in range(lo, hi):
            c = companies[i]
            ticker = c["nse_ticker"] or ""
            html, status = cached_screener_html(c["scrip"], ticker, args.pause)
            if status == "cached":
                bcache += 1
            if status == "throttled":
                bthrottle += 1
            mcap = B.screener_market_cap(html) if html else None
            call_date = (c["news_dt"] or "")[:10]
            # SLONGNAME is sometimes blank and the NSURL slug "-"; fall back to
            # the screener page <h1>, then the ticker.
            name = (c["name"].strip() or B.screener_name(html)
                    or ticker.upper() or c["scrip"])
            slug = next((s for s in (c["slug"], ticker, B.slugify(name))
                         if s and s != "-"), c["scrip"])
            if mcap is None:
                bu += 1
                row_status = f"unresolved:{status}"
                unresolved.append({"name": name, "scrip": c["scrip"],
                                   "nse_ticker": ticker, "concall_date": call_date,
                                   "reason": status})
                tag = f"UNRESOLVED ({status})"
            elif mcap <= args.cap_max:
                bk += 1
                row_status = "kept"
                kept.append({
                    "company_name": name, "nse_ticker": ticker, "slug": slug,
                    "bse_scrip": c["scrip"], "market_cap_cr": round(mcap, 1),
                    "concall_date": call_date, "attachment": c["attachment"],
                    "headline": c["headline"],
                })
                tag = f"KEEP ₹{mcap:,.0f}cr"
            else:
                bd += 1
                row_status = "over_cap"
                tag = f"drop ₹{mcap:,.0f}cr (> cap)"
            # record EVERY company (kept, over-cap, or unresolved) with its mcap
            everything.append({
                "company_name": name, "nse_ticker": ticker,
                "bse_scrip": c["scrip"],
                "market_cap_cr": round(mcap, 1) if mcap is not None else "",
                "status": row_status, "concall_date": call_date,
            })
            print(f"  [{i + 1}/{n}] {c['scrip']} {name[:36]:36} {tag}")

        _write_outputs(kept, unresolved, everything)  # incremental: stop keeps partials
        warn = "  ⚠ THROTTLED — raise --pause" if bthrottle else ""
        print(f"--- batch {b + 1}/{nbatches} [{lo + 1}-{hi}]: "
              f"keep={bk} drop={bd} unresolved={bu} (cached={bcache} "
              f"throttled={bthrottle}) | cumulative cohort={len(kept)}{warn}\n")

    over = sum(1 for r in everything if r["status"] == "over_cap")
    print(f"Done. all={len(everything)}  cohort(<=cap)={len(kept)}  "
          f"over_cap={over}  unresolved={len(unresolved)}")
    print(f"  -> {ALL_CSV.name} (every company + mcap + status)")
    print(f"  -> {COHORT_CSV.name}")
    print(f"  -> {UNRESOLVED_CSV.name}")


def _write_outputs(kept: list[dict], unresolved: list[dict],
                   everything: list[dict]) -> None:
    with open(COHORT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(kept, key=lambda r: r["market_cap_cr"]))
    with open(UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as f:
        cols = ["name", "scrip", "nse_ticker", "concall_date", "reason"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(unresolved)
    # complete record: kept + over-cap + unresolved, sorted by mcap desc
    with open(ALL_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ALL_FIELDS)
        w.writeheader()
        w.writerows(sorted(everything, key=lambda r: (
            r["market_cap_cr"] if isinstance(r["market_cap_cr"], (int, float))
            else -1), reverse=True))


if __name__ == "__main__":
    main()
