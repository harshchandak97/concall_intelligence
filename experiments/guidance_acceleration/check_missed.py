#!/usr/bin/env python3
"""check_missed.py — recall audit for the concall cohort built by build_universe.py.

The cohort comes from one BSE call: market-wide announcements in [Apr-Jun 2024]
tagged subcategory == "Earnings Call Transcript". That can under-count in two
ways this script tests independently against universe_all.csv (the COMPLETE
swept set — kept + over-cap + unresolved, so a hit here is a genuine miss, not a
market-cap drop):

  --mode window   blind spot: DATE WINDOW. Re-sweep transcripts over a WIDER
                  window (default ..Aug 31) and report scrips not already swept.
                  Catches late / lagged Q4 FY24 transcript filings.

  --mode subcat   blind spot: SUBCATEGORY MISTAGGING. Sweep ALL "Company Update"
                  filings (NO subcategory filter) in the original window, keep
                  rows whose HEADLINE/SUBCATNAME looks like a concall transcript
                  but were NOT caught by the strict "Earnings Call Transcript"
                  tag. Catches transcripts filed under the wrong subcategory.

  --mode both     run both (default).

Outputs (this folder):
  missed_by_window.csv   scrip, name, nse_ticker, concall_date, subcatname, headline
  missed_by_subcat.csv   scrip, name, nse_ticker, news_dt, subcatname, headline

Read-only: it does NOT touch the cohort CSVs. Inspect a few hits by hand, then
decide whether to widen build_universe's window / loosen its filter.

Usage:
  python check_missed.py                      # both modes, default windows
  python check_missed.py --mode window --to 20240930
  python check_missed.py --mode subcat
"""
from __future__ import annotations
import argparse, csv, json, re, sys, time, urllib.parse
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
ALL_CSV = HERE / "universe_all.csv"          # complete swept set (the baseline)
MISSED_WINDOW_CSV = HERE / "missed_by_window.csv"
MISSED_SUBCAT_CSV = HERE / "missed_by_subcat.csv"

# headlines/subcats that mean "this IS a concall transcript" but may sit under a
# different subcategory than the canonical "Earnings Call Transcript".
CONCALL_RE = re.compile(
    r"(earnings\s*call|concall|con[\s-]*call|conference\s*call|"
    r"analyst\s*(call|meet)|investor\s*(call|conference)|transcript)",
    re.I)
# the exact tag build_universe already keeps — exclude so subcat mode shows ONLY
# the leak (things the strict filter would have missed).
STRICT_TAG = "earnings call transcript"


def known_scrips() -> set[str]:
    """Every scrip already seen by the build (kept + over-cap + unresolved)."""
    if not ALL_CSV.exists():
        sys.exit(f"missing {ALL_CSV.name} — run build_universe.py first")
    with open(ALL_CSV, encoding="utf-8") as f:
        return {r["bse_scrip"].strip() for r in csv.DictReader(f)
                if r.get("bse_scrip", "").strip()}


def sweep_raw(frm: str, to: str, subcategory: str | None,
              pause: float, max_pages: int = 80) -> list[dict]:
    """Market-wide 'Company Update' announcements in [frm,to].

    subcategory=None -> ALL Company Update filings (for subcat-leak detection).
    subcategory='Earnings Call Transcript' -> only the canonical transcript tag.
    Returns raw rows incl. SUBCATNAME + HEADLINE so the caller can classify.
    """
    out: list[dict] = []
    for cf, ct in B._date_chunks(frm, to):
        got = 0
        for page in range(1, max_pages + 1):
            params = {"pageno": page, "strCat": "Company Update",
                      "strPrevDate": cf, "strToDate": ct, "strScrip": "",
                      "strSearch": "P", "strType": "C"}
            if subcategory:
                params["subcategory"] = subcategory
            q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            txt = B.get_text(f"{B._BSE_ANN}?{q}", B._BSE_HEADERS)
            if len(txt) < 40:
                break
            try:
                batch = json.loads(txt).get("Table", [])
            except Exception:
                break
            if not batch:
                break
            for r in batch:
                scrip = r.get("SCRIP_CD")
                if not scrip:
                    continue
                ticker, slug = B._nsurl_ticker_slug(r.get("NSURL") or "")
                out.append({
                    "scrip": str(scrip),
                    "name": (r.get("SLONGNAME") or "").strip(),
                    "news_dt": (r.get("NEWS_DT") or "")[:10],
                    "nse_ticker": ticker or "",
                    "subcatname": (r.get("SUBCATNAME") or "").strip(),
                    "headline": (r.get("HEADLINE") or "").strip(),
                })
            got += len(batch)
            if len(batch) < 50:
                break
            time.sleep(pause)
        print(f"    sweep {cf}..{ct}: {got} rows "
              f"({'all Company Update' if not subcategory else subcategory})")
    return out


def dedup_earliest(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for r in rows:
        k = r["scrip"]
        if k not in best or r["news_dt"] < best[k]["news_dt"]:
            best[k] = r
    return sorted(best.values(), key=lambda r: r["name"].lower())


def _write(path: Path, rows: list[dict]) -> None:
    cols = ["scrip", "name", "nse_ticker", "news_dt", "subcatname", "headline"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def mode_window(frm: str, to: str, pause: float) -> None:
    print(f"[window] transcript sweep {frm}..{to} (cohort built ..20240630)")
    known = known_scrips()
    rows = dedup_earliest(sweep_raw(frm, to, "Earnings Call Transcript", pause))
    missed = [r for r in rows if r["scrip"] not in known]
    _write(MISSED_WINDOW_CSV, missed)
    print(f"  {len(rows)} transcript companies in window; "
          f"{len(missed)} NOT in cohort -> {MISSED_WINDOW_CSV.name}")
    for r in missed[:25]:
        print(f"    + {r['scrip']} {r['name'][:40]:40} {r['news_dt']}")
    if len(missed) > 25:
        print(f"    … and {len(missed) - 25} more")


def mode_subcat(frm: str, to: str, pause: float) -> None:
    print(f"[subcat] ALL Company-Update filings {frm}..{to}, "
          f"concall-like but wrongly tagged")
    known = known_scrips()
    rows = sweep_raw(frm, to, None, pause)  # NO subcategory filter
    # concall-like text, but NOT the strict tag, and scrip not already swept
    hits = {}
    for r in rows:
        blob = f"{r['subcatname']} {r['headline']}"
        if r["subcatname"].lower() == STRICT_TAG:
            continue                       # already covered by the strict build
        if not CONCALL_RE.search(blob):
            continue
        if r["scrip"] in known:
            continue                       # company already in cohort anyway
        k = r["scrip"]
        if k not in hits or r["news_dt"] < hits[k]["news_dt"]:
            hits[k] = r
    missed = sorted(hits.values(), key=lambda r: r["name"].lower())
    _write(MISSED_SUBCAT_CSV, missed)
    print(f"  scanned {len(rows)} Company-Update filings; "
          f"{len(missed)} concall-like companies missed by the strict tag "
          f"-> {MISSED_SUBCAT_CSV.name}")
    for r in missed[:25]:
        print(f"    + {r['scrip']} {r['name'][:34]:34} "
              f"[{r['subcatname'][:22]:22}] {r['headline'][:30]}")
    if len(missed) > 25:
        print(f"    … and {len(missed) - 25} more")


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit concall-cohort recall.")
    ap.add_argument("--mode", choices=["window", "subcat", "both"],
                    default="both")
    ap.add_argument("--from", dest="frm", default="20240401")
    ap.add_argument("--to", default="20240831",
                    help="window-mode end (default 20240831; build used 0630)")
    ap.add_argument("--subcat-to", default="20240630",
                    help="subcat-mode end (default 20240630 = original window)")
    ap.add_argument("--pause", type=float, default=0.25)
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    if args.mode in ("window", "both"):
        mode_window(args.frm, args.to, args.pause)
    if args.mode in ("subcat", "both"):
        mode_subcat(args.frm, args.subcat_to, args.pause)


if __name__ == "__main__":
    main()
