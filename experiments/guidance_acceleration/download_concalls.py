#!/usr/bin/env python3
"""download_concalls.py — STEP 4 of the guidance-acceleration experiment.

Downloads the Q4 FY24 transcript PDF for every company in the cohort produced by
build_universe.py, into ./transcripts/. Each download is page-count checked
(reusing the repo's logic): a real transcript is ~15-25 pages; <5 pages is flagged
COVER? (usually a 1-page cover letter, real transcript on the company IR site).

Tracking & failure visibility:
  * a summary prints after every batch (OK/COVER?/FAIL counts),
  * any non-OK download is flagged inline with a ❌/⚠ marker, and
  * a final FAILURES block lists every company that did not download cleanly.
Re-runnable: pass --skip-existing to resume; only the missing/failed are retried.

Run a smoke test first, then the full pull:
  python download_concalls.py --limit 20                  # validate ~20 first
  python download_concalls.py --skip-existing             # full cohort, resumable

Outputs:
  transcripts/{slug}_Q4_FY24.pdf
  download_log.csv   — status per company (OK | COVER? | NOTPDF | FAIL | SKIP)
"""
from __future__ import annotations
import argparse, csv, sys, time
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
COHORT_CSV = HERE / "universe_with_concalls.csv"
OUT_DIR = HERE / "transcripts"
LOG_CSV = HERE / "download_log.csv"

# statuses that mean "you should look at this"
BAD = ("COVER?", "NOTPDF", "FAIL")


def _kind(status: str) -> str:
    return status.split(":")[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Download Q4 FY24 cohort transcripts.")
    ap.add_argument("--universe", default=str(COHORT_CSV),
                    help="cohort CSV from build_universe.py")
    ap.add_argument("--out", default=str(OUT_DIR), help="output PDF directory")
    ap.add_argument("--limit", type=int, default=None,
                    help="only download the first N (smoke test)")
    ap.add_argument("--pause", type=float, default=0.3,
                    help="seconds between downloads")
    ap.add_argument("--batch-size", type=int, default=50,
                    help="downloads per batch; a summary prints after each")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip companies whose PDF already exists (resume)")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # stream progress live

    rows = list(csv.DictReader(open(args.universe, encoding="utf-8")))
    if args.limit:
        rows = rows[:args.limit]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(rows)
    nbatches = (n + args.batch_size - 1) // args.batch_size
    print(f"Downloading {n} transcripts -> {out_dir} "
          f"({nbatches} batches of {args.batch_size})\n")

    log, counts, failures = [], {}, []
    for b in range(nbatches):
        lo, hi = b * args.batch_size, min((b + 1) * args.batch_size, n)
        bc = {}
        for i in range(lo, hi):
            r = rows[i]
            slug = r["slug"] or B.slugify(r["company_name"])
            fname = f"{slug}_Q4_FY24.pdf"
            path = out_dir / fname
            if args.skip_existing and path.exists():
                status, size, pages = "SKIP", path.stat().st_size, -1
            else:
                status, size, pages = B.download_pdf(B.attachment_url(r["attachment"]),
                                                     str(path))
                time.sleep(args.pause)
            kind = _kind(status)
            counts[kind] = counts.get(kind, 0) + 1
            bc[kind] = bc.get(kind, 0) + 1
            mark = "❌" if kind == "FAIL" else ("⚠ " if kind in ("COVER?", "NOTPDF") else "  ")
            info = f"({pages}p, {size // 1024}KB)" if status in ("OK", "COVER?", "SKIP") else ""
            print(f"  {mark}[{i + 1}/{n}] {r['company_name'][:36]:36} {status} {info}")
            row = {"company": r["company_name"], "ticker": r["nse_ticker"],
                   "scrip": r["bse_scrip"], "file": fname, "status": status,
                   "pages": pages, "size_kb": size // 1024}
            log.append(row)
            if kind in BAD:
                failures.append(row)

        _write_log(log)  # incremental: a stop keeps the log so far
        summ = " ".join(f"{k}={v}" for k, v in sorted(bc.items()))
        bad = sum(v for k, v in bc.items() if k in BAD)
        flag = f"  ⚠ {bad} need attention" if bad else ""
        print(f"--- batch {b + 1}/{nbatches} [{lo + 1}-{hi}]: {summ}{flag} "
              f"| total OK={counts.get('OK', 0)}\n")

    _write_log(log)
    print("Done. " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"  -> {LOG_CSV.name}")
    if failures:
        print(f"\n⚠ {len(failures)} did NOT download cleanly "
              f"(also in download_log.csv, status != OK):")
        for r in failures:
            print(f"   {r['status']:8} {r['scrip']:>7}  {r['company']}")
    else:
        print("\nAll downloads OK — no failures.")


def _write_log(log: list[dict]) -> None:
    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company", "ticker", "scrip", "file",
                                          "status", "pages", "size_kb"])
        w.writeheader()
        w.writerows(log)


if __name__ == "__main__":
    main()
