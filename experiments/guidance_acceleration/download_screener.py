#!/usr/bin/env python3
"""download_screener.py — download + VALIDATE transcripts for the screener cohort.

Reads universe_screener.csv (from build_universe_screener.py) and downloads each
company's target-quarter transcript, preferring screener's own link and falling
back to a TARGETED per-scrip BSE query (never the random market sweep).

Validation (two gates, both required for OK):
  1. page count  — a real transcript is ~15-25 pages; < --min-pages is COVER?
  2. content     — first few pages must read like a transcript (moderator, Q&A,
                   "conference call", … via lib_bse.looks_like_transcript), else
                   NOTTRANSCRIPT (catches cover letters, decks, wrong attachments
                   that still pass the page-count gate).

Idempotent / no needless re-downloads: before fetching, an existing file is
RE-VALIDATED (page count + content). If it is already a valid transcript it is
SKIPped — the bytes are not pulled again. Only missing / cover-only / non-
transcript / corrupt files are (re)downloaded. So reruns converge: good files are
left alone, bad ones are retried (incl. via the BSE fallback). This replaces the
blunt "skip if the path exists" check, which can't tell a real transcript from a
1-page cover that happens to occupy the same filename.

  python download_screener.py --limit 20            # smoke test
  python download_screener.py                        # full cohort, resumable
  python download_screener.py --revalidate-only      # audit existing files, no fetch

Outputs:
  transcripts/{slug}_{Q}_FY{yy}.pdf
  download_screener_log.csv   status per company
"""
from __future__ import annotations
import argparse, csv, sys, time
from pathlib import Path

import lib_bse as B

HERE = Path(__file__).parent
COHORT_CSV = HERE / "universe_screener.csv"
OUT_DIR = HERE / "transcripts"
LOG_CSV = HERE / "download_screener_log.csv"

BAD = ("COVER?", "NOTTRANSCRIPT", "NOTPDF", "BADPDF", "FAIL", "NOLINK")
# fy -> "FY24" tag in the filename
QFY = lambda q, fy: f"{q}_FY{fy % 100:02d}"


def _candidate_urls(row: dict, fy: int, q: str, pause: float) -> list[tuple[str, str]]:
    """(url, src) candidates in priority order: screener's own link first, then a
    targeted per-scrip BSE lookup. The BSE candidate also rescues a screener link
    that 404s / serves a cover, not just a missing one."""
    cands = []
    if row.get("transcript_url"):
        cands.append((row["transcript_url"], row.get("transcript_src") or "screener"))
    if row.get("scrip"):
        url = B.bse_transcript_for_scrip(row["scrip"], fy, q, pause=pause)
        if url and url not in {c[0] for c in cands}:
            cands.append((url, "bse_fallback"))
    return cands


def _fetch_and_validate(url: str, path: Path, min_pages: int,
                        content_pages: int) -> tuple[str, int, int]:
    """Download `url` to `path`, then validate. (status, size_kb, pages).
    Writes to a temp path first so a bad fetch never clobbers a good existing PDF."""
    ref = "https://www.bseindia.com/" if "bseindia" in url else url
    try:
        data = B.get(url, {"Referer": ref}, timeout=60)
    except Exception as e:
        return f"FAIL:{e}".replace("\n", " ")[:40], 0, 0
    if not data.startswith(b"%PDF"):
        return "NOTPDF", len(data) // 1024, 0
    tmp = path.with_suffix(".pdf.tmp")
    tmp.write_bytes(data)
    status, pages = B.validate_transcript_pdf(str(tmp), min_pages, content_pages)
    if status == "OK":
        tmp.replace(path)
        return "OK", len(data) // 1024, pages
    if status == "COVER?":
        # a cover letter usually LINKS to the real transcript — follow that link
        # (validated) before giving up on this candidate and re-searching.
        link_status, link_pages = B.follow_cover_link(
            str(tmp), str(path), min_pages, content_pages)
        tmp.unlink(missing_ok=True)
        if link_status == "OK":
            return "OK:coverlink", len(data) // 1024, link_pages
        return status, len(data) // 1024, pages
    tmp.unlink(missing_ok=True)
    return status, len(data) // 1024, pages


def _download_best(row: dict, path: Path, fy: int, q: str, pause: float,
                   min_pages: int, content_pages: int) -> tuple[str, str, int, int]:
    """Try each candidate URL until one validates OK. Returns
    (status, src, size_kb, pages) — the OK result, or the last failure."""
    cands = _candidate_urls(row, fy, q, pause)
    if not cands:
        return "NOLINK", "none", 0, 0
    last = ("FAIL", "none", 0, 0)
    for url, src in cands:
        status, size, pages = _fetch_and_validate(url, path, min_pages, content_pages)
        time.sleep(pause)
        if status.split(":")[0] == "OK":  # "OK" or "OK:coverlink"
            return status, src, size, pages
        last = (status, src, size, pages)
    return last[0], last[1], last[2], last[3]


def main() -> None:
    ap = argparse.ArgumentParser(description="Download + validate cohort transcripts.")
    ap.add_argument("--universe", default=str(COHORT_CSV))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--target-fy", type=int, default=2024)
    ap.add_argument("--target-quarter", default="Q4")
    ap.add_argument("--min-pages", type=int, default=5)
    ap.add_argument("--content-pages", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--revalidate-only", action="store_true",
                    help="only re-check existing PDFs; never download")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    rows = list(csv.DictReader(open(args.universe, encoding="utf-8")))
    if args.limit:
        rows = rows[:args.limit]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fy, q = args.target_fy, args.target_quarter
    n = len(rows)
    nbatches = (n + args.batch_size - 1) // args.batch_size
    print(f"{'Re-validating' if args.revalidate_only else 'Downloading'} {n} "
          f"{q} FY{fy % 100:02d} transcripts -> {out_dir} "
          f"({nbatches} batches)\n")

    log, counts, failures = [], {}, []
    for b in range(nbatches):
        lo, hi = b * args.batch_size, min((b + 1) * args.batch_size, n)
        bc = {}
        for i in range(lo, hi):
            r = rows[i]
            slug = (r.get("slug") or r.get("ticker")
                    or B.slugify(r["company_name"])).lower()
            path = out_dir / f"{slug}_{QFY(q, fy)}.pdf"
            src, size, pages = r.get("transcript_src", ""), 0, -1

            # 1. idempotent: an already-valid transcript is left untouched.
            pre, prepages = B.validate_transcript_pdf(
                str(path), args.min_pages, args.content_pages)
            if pre == "OK":
                status, pages, src = "SKIP", prepages, "cached"
            elif args.revalidate_only:
                status, pages = pre, prepages  # report the defect, don't fetch
            else:
                # 2. (re)download — existing file missing/cover/not-a-transcript.
                #    Tries screener link then BSE fallback until one validates.
                status, src, size, pages = _download_best(
                    r, path, fy, q, args.pause, args.min_pages, args.content_pages)

            kind = status.split(":")[0]
            counts[kind] = counts.get(kind, 0) + 1
            bc[kind] = bc.get(kind, 0) + 1
            mark = ("  " if kind in ("OK", "SKIP")
                    else "❌" if kind in ("FAIL", "NOLINK", "BADPDF") else "⚠ ")
            print(f"  {mark}[{i+1}/{n}] {r['company_name'][:34]:34} "
                  f"{status:14} {pages:>3}p  [{src}]")
            rec = {"company": r["company_name"], "ticker": r.get("ticker", ""),
                   "scrip": r.get("scrip", ""), "file": path.name,
                   "status": status, "src": src, "pages": pages, "size_kb": size}
            log.append(rec)
            if kind in BAD:
                failures.append(rec)

        _write_log(log)
        summ = " ".join(f"{k}={v}" for k, v in sorted(bc.items()))
        print(f"--- batch {b+1}/{nbatches} [{lo+1}-{hi}]: {summ} | "
              f"total good(OK+SKIP)={counts.get('OK',0)+counts.get('SKIP',0)}\n")

    _write_log(log)
    print("Done. " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if failures:
        print(f"\n⚠ {len(failures)} need attention (also in {LOG_CSV.name}):")
        for r in failures[:60]:
            print(f"   {r['status']:14} {r['scrip']:>7}  {r['company']}")
        if len(failures) > 60:
            print(f"   … and {len(failures) - 60} more")
    else:
        print("\nAll transcripts valid.")


def _write_log(log: list[dict]) -> None:
    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company", "ticker", "scrip", "file",
                                          "status", "src", "pages", "size_kb"])
        w.writeheader()
        w.writerows(log)


if __name__ == "__main__":
    main()
