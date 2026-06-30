#!/usr/bin/env python3
"""recover_covers.py — multi-pass recovery for COVER? downloads.

Pass 1 — BSE alternates (extended window Apr–Sep 2024):
  Some companies file a 1-page cover letter AND the real transcript separately
  on BSE. The market-wide sweep picks the earliest, which is often the cover.
  Re-query each COVER? scrip for all transcript-ish filings and try every
  candidate, largest first.

Pass 2 — link-letter URL extraction:
  Many Indian companies post a 1-3 page BSE filing that says "please visit
  <URL> for the transcript". Parse the text of the cover PDF already on disk,
  extract any https:// URL, and attempt to download the PDF at that URL.
  One level of HTML link-following is attempted if the URL returns a page
  rather than a PDF (e.g. an IR website that embeds a PDF viewer).

Pass 3 — give up, flag for manual check.

Usage:
    python recover_covers.py              # recover all current COVER?s
    python recover_covers.py --dry-run    # list targets without downloading
"""
from __future__ import annotations
import argparse, csv, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

import lib_bse as B

HERE     = Path(__file__).parent
COHORT   = HERE / "universe_with_concalls.csv"
OUT_DIR  = HERE / "transcripts"
LOG_CSV  = HERE / "recover_log.csv"

# Extended window: catches companies that filed their Q4 FY24 transcript late
BSE_FROM = "20240401"
BSE_TO   = "20240930"

MIN_PAGES = 5   # below this is treated as a cover/stub


# ------------------------------------------------------------------ BSE pass
def _bse_candidates(scrip: str) -> list[dict]:
    """All transcript-ish BSE filings for one scrip in the extended window."""
    out = []
    for frm, to in B._date_chunks(BSE_FROM, BSE_TO):
        q = urllib.parse.urlencode({
            "pageno": 1, "strCat": "-1", "strPrevDate": frm, "strToDate": to,
            "strScrip": scrip, "strSearch": "P", "strType": "C", "subcategory": "-1",
        }, quote_via=urllib.parse.quote)
        txt = B.get_text(f"{B._BSE_ANN}?{q}", B._BSE_HEADERS)
        try:
            rows = json.loads(txt).get("Table", [])
        except Exception:
            rows = []
        for r in rows:
            sub = (r.get("SUBCATNAME") or "").lower()
            hl  = (r.get("HEADLINE")   or "")
            if "transcript" not in sub and "transcript" not in hl.lower():
                continue
            att = r.get("ATTACHMENTNAME")
            if att:
                out.append({"att": att, "size": r.get("Fld_Attachsize") or 0,
                            "hl": hl, "dt": (r.get("NEWS_DT") or "")[:10]})
        time.sleep(0.2)
    # deduplicate by attachment, rank: real transcript headline > audio stub > size
    seen, ranked = set(), []
    def _key(c):
        hl = c["hl"].lower()
        return ("transcript" in hl, "audio" not in hl and "recording" not in hl,
                int(c["size"]))
    for c in sorted(out, key=_key, reverse=True):
        if c["att"] not in seen:
            seen.add(c["att"]); ranked.append(c)
    return ranked


# ------------------------------------------------------------------ candidate fetch
# Link extraction + HTML-follow + the full content validation now live in lib_bse
# (B.pdf_urls / B.fetch_pdf_bytes / B.follow_cover_link), shared with the inline
# cover-follow in download_screener.py so the two paths can never drift.
def _try_attachment(att: str, p: Path) -> tuple[str, int]:
    """Download a BSE attachment to a temp, CONTENT-validate it, and only replace
    the existing file at `p` if it is a real transcript. A failed candidate never
    clobbers the original cover (which Pass 2 still needs). Returns (status, pages)."""
    data = B.fetch_pdf_bytes(B.attachment_url(att), follow_html=False)
    if not data:
        return "FAIL", 0
    tmp = p.with_suffix(".pdf.rtmp")
    tmp.write_bytes(data)
    status, pages = B.validate_transcript_pdf(str(tmp), MIN_PAGES)
    if status == "OK":
        tmp.replace(p)
    else:
        tmp.unlink(missing_ok=True)
    return status, pages


# ------------------------------------------------------------------ orchestrator
def recover_one(r: dict, slug: str, p: Path, dry_run: bool) -> dict:
    """Run all passes for one company. Returns a log-row dict."""
    scrip   = r["bse_scrip"]
    company = r["company_name"]

    if dry_run:
        cands = _bse_candidates(scrip)
        urls  = B.pdf_urls(str(p)) if p.exists() else []
        return {"company": company, "scrip": scrip,
                "result": f"dry: {len(cands)} bse-cands, {len(urls)} link-urls",
                "pages": -1, "pass": "dry"}

    # --- Pass 1: BSE alternates (content-validated, so an AR/deck is rejected) ---
    for c in _bse_candidates(scrip):
        status, pg = _try_attachment(c["att"], p)
        time.sleep(0.3)
        if status == "OK":
            return {"company": company, "scrip": scrip, "result": "RECOVERED",
                    "pages": pg, "pass": "bse", "detail": c["hl"][:60]}

    # --- Pass 2: follow the cover letter's embedded link (content-validated) ---
    if p.exists():
        status, pages = B.follow_cover_link(str(p), str(p), MIN_PAGES)
        if status == "OK":
            return {"company": company, "scrip": scrip, "result": "RECOVERED",
                    "pages": pages, "pass": "link-letter", "detail": "cover link"}

    # --- Pass 3: give up ---
    return {"company": company, "scrip": scrip, "result": "still-cover",
            "pages": B.pdf_page_count(str(p)) if p.exists() else -1,
            "pass": "—", "detail": "no usable source found"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-pass recovery for COVER? transcripts.")
    ap.add_argument("--dry-run", action="store_true",
                    help="list targets and candidate counts without downloading")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    rows = list(csv.DictReader(open(COHORT, encoding="utf-8")))
    targets = []
    for r in rows:
        slug = r["slug"] or B.slugify(r["company_name"])
        p = OUT_DIR / f"{slug}_Q4_FY24.pdf"
        if not p.exists() or B.pdf_page_count(str(p)) < MIN_PAGES:
            targets.append((r, slug, p))

    print(f"{len(targets)} COVER?/missing companies — running 2-pass recovery "
          f"(BSE alternates → link-letter URL extraction)\n")

    log = []
    counts = {"RECOVERED": 0, "still-cover": 0}
    for i, (r, slug, p) in enumerate(targets, 1):
        rec = recover_one(r, slug, p, args.dry_run)
        result = rec["result"]
        counts[result] = counts.get(result, 0) + 1
        mark = "✅" if result == "RECOVERED" else ("  " if args.dry_run else "⚠ ")
        pg   = f"({rec['pages']}p)" if rec.get("pages", -1) > 0 else ""
        via  = f"[{rec.get('pass','')}]" if not args.dry_run else ""
        print(f"  {mark}[{i}/{len(targets)}] {r['company_name'][:34]:34}  "
              f"{result} {pg} {via}")
        log.append(rec)

    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company", "scrip", "result", "pages",
                                          "pass", "detail"], extrasaction="ignore")
        w.writeheader(); w.writerows(log)

    if not args.dry_run:
        recovered  = [l for l in log if l["result"] == "RECOVERED"]
        still_bad  = [l for l in log if l["result"] == "still-cover"]
        print(f"\nRecovered {len(recovered)}/{len(targets)} "
              f"({sum(1 for l in recovered if l['pass']=='bse')} via BSE, "
              f"{sum(1 for l in recovered if l['pass']=='link-letter')} via link-letter)")
        if still_bad:
            print(f"\n{len(still_bad)} still cover-only — manual check needed:")
            for l in still_bad:
                print(f"   {l['scrip']:>7}  {l['company']}")
    print(f"\n  -> {LOG_CSV.name}")


if __name__ == "__main__":
    main()
