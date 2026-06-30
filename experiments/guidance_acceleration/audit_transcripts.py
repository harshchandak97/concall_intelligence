#!/usr/bin/env python3
"""audit_transcripts.py — finalize/quarantine pass over a transcripts folder.

The download step (download_screener.py) already validates on the way in via
lib_bse.validate_transcript_pdf and only keeps files that pass. This tool is the
SWEEP for files already on disk (e.g. from an older download run): it re-checks
every PDF with the SAME shared validator, then

  * keeps OK files in place (the "correct" set),
  * moves rejects (cover letter / annual report / deck / wrong file) to
    transcripts/_rejected/,
  * moves image-only scans to transcripts/_needs_ocr/ (recoverable, NOT wrong),
  * writes validation_status.csv — one row per file, CORRECT on top and
    INCORRECT grouped at the bottom, with the detected vs expected quarter.

Identity is trusted from the source-keyed download link, so this does NOT gate on
the company name; it gates only on "is this the actual spoken earnings call?" and
flags (never deletes) a quarter that disagrees with the filename — maximising
company coverage. There is ONE validation logic, in lib_bse, used both here and by
the downloader, so the two can never drift.

  python audit_transcripts.py                 # sweep transcripts/, move rejects
  python audit_transcripts.py --dry-run       # report only, move nothing
  python audit_transcripts.py --limit 30      # first 30 PDFs (smoke test)
  python audit_transcripts.py path/to/dir
"""
from __future__ import annotations
import argparse
import csv
import re
import sys
from pathlib import Path

import pdfplumber

import lib_bse as B

HERE = Path(__file__).parent
RESULTS = HERE / "results"
STATUS_CSV = RESULTS / "validation_status.csv"
# how each validator status maps to a human verdict + destination subfolder
VERDICT = {  # status -> (verdict, subfolder or None=keep in place)
    "OK": ("CORRECT", None),
    "NEEDS_OCR": ("NEEDS_OCR", "_needs_ocr"),
    "COVER?": ("INCORRECT", "_rejected"),
    "NOTTRANSCRIPT": ("INCORRECT", "_rejected"),
    "BADPDF": ("INCORRECT", "_rejected"),
    "MISSING": ("INCORRECT", "_rejected"),
}
# sort order for the CSV: correct first, recoverable next, incorrect last
VERDICT_ORDER = {"CORRECT": 0, "NEEDS_OCR": 1, "INCORRECT": 2}


# ----------------------------------------------------------------- quarter parse
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
          "december": 12}
ORDINAL_Q = {"first": 1, "second": 2, "third": 3, "fourth": 4}
QEND = {3: "Q4", 6: "Q1", 9: "Q2", 12: "Q3"}  # quarter-END month -> FY quarter
_FY_SEP = r"['‘’`´°\-.\s]*"
# capture the LAST year, so a fiscal-year RANGE 'FY23-24' / 'FY 2023-24' (which
# means FY24) reads as 24, not 23. A plain 'FY24' / "FY'24" still reads as 24.
_FY_RE = re.compile(
    r"\bf\.?\s*y\.?" + _FY_SEP + r"(?:\d{2,4}\s*[-/]\s*)?(\d{2,4})\b", re.I)


def _fy_two(year: str) -> str:
    return f"FY{year[-2:]}"


def _parse_q(t: str) -> tuple[str | None, str | None]:
    """Run the quarter patterns on a (lowercased) text span."""
    m = re.search(r"\bq([1-4])\b\s*(?:&|and)?\s*" + _FY_RE.pattern, t, re.I)
    if m:
        return f"Q{m.group(1)}", _fy_two(m.group(2))
    qnum = None
    mo = re.search(r"\b(first|second|third|fourth)\s+quarter", t)
    if mo:
        qnum = ORDINAL_Q[mo.group(1)]
    me = re.search(r"ended\s+(?:on\s+)?(\w+)\s+\d{0,2},?\s*(\d{4})", t)
    if me and me.group(1) in MONTHS:
        month, yr = MONTHS[me.group(1)], int(me.group(2))
        if QEND.get(month):
            fy = yr if month == 3 else yr + 1
            return (f"Q{qnum}" if qnum else QEND[month]), _fy_two(str(fy))
    if qnum:
        fm = _FY_RE.search(t)
        if fm:
            return f"Q{qnum}", _fy_two(fm.group(1))
    return None, None


def detect_quarter(page_blocks: list[str]) -> tuple[str | None, str | None]:
    """Read the quarter off the TRANSCRIPT TITLE, which sits at the very top of
    the transcript body (page 2-4, after the cover letter). Parsing the title
    block — not the whole page — avoids both the cover letter (no quarter) and
    prior-year comparatives in the moderator's speech ('vs Q4 FY23')."""
    for blk in page_blocks[1:4]:          # pages 2,3,4
        q = _parse_q(blk[:400].lower())   # the title sits in the first lines
        if q[0]:
            return q
    # fallback: anywhere in the first few pages
    return _parse_q(" ".join(page_blocks[:4]).lower())


def expected_quarter(filename: str) -> str:
    """'Q4 FY24' from '{slug}_Q4_FY24.pdf' (the downloader's assigned quarter)."""
    m = re.search(r"_Q([1-4])_FY(\d{2})", filename)
    return f"Q{m.group(1)} FY{m.group(2)}" if m else ""


# ----------------------------------------------------------------- pdf read
def read_pdf(path: Path, n: int = 6) -> tuple[int, list[str]]:
    """(page_count, first-n page texts). One open per file — the text feeds both
    the doc-type classifier and the quarter parser."""
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        blocks = [(pdf.pages[i].extract_text() or "") for i in range(min(n, pages))]
    return pages, blocks


def validate(path: Path, min_pages: int = 5) -> tuple[str, int, list[str]]:
    """(status, pages, page_blocks) using the SHARED lib_bse classifier."""
    with open(path, "rb") as f:
        if f.read(4) != b"%PDF":
            return "BADPDF", 0, []
    try:
        pages, blocks = read_pdf(path)
    except Exception:
        return "BADPDF", 0, []
    if pages < min_pages:
        return "COVER?", pages, blocks
    text = "\n".join(blocks).lower()
    return B.classify_transcript(text, pages), pages, blocks


# ----------------------------------------------------------------- manifest
def load_company_names() -> dict[str, str]:
    """slug -> company name, from whichever universe CSVs are present."""
    out: dict[str, str] = {}
    for csv_name, slug_col, name_col in [
            ("universe_screener.csv", "ticker", "company_name"),
            ("universe_with_concalls.csv", "slug", "company_name"),
            ("download_log.csv", None, "company")]:
        fp = HERE / csv_name
        if not fp.exists():
            continue
        for r in csv.DictReader(open(fp, encoding="utf-8")):
            if csv_name == "download_log.csv":
                fn = r.get("file", "")
                slug = fn.rsplit("_Q", 1)[0] if "_Q" in fn else fn[:-4]
            else:
                slug = (r.get(slug_col) or B.slugify(r.get(name_col, ""))).lower()
            out.setdefault(slug, r.get(name_col, ""))
    return out


# ----------------------------------------------------------------- main
FIELDS = ["verdict", "company", "slug", "file", "pages", "expected_quarter",
          "detected_quarter", "quarter_match", "status", "moved_to"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Finalize/quarantine a transcripts folder.")
    ap.add_argument("directory", nargs="?", default=str(HERE / "transcripts"))
    ap.add_argument("--dry-run", action="store_true", help="report only; move nothing")
    ap.add_argument("--limit", type=int, help="process only the first N PDFs")
    ap.add_argument("--min-pages", type=int, default=5)
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    src = Path(args.directory)
    pdfs = sorted(p for p in src.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[:args.limit]
    if not pdfs:
        ap.error(f"no PDFs in {src}")
    names = load_company_names()
    RESULTS.mkdir(exist_ok=True)
    print(f"validating {len(pdfs)} PDFs in {src}\n")

    rows = []
    for i, pdf in enumerate(pdfs, 1):
        slug = pdf.name.rsplit("_Q", 1)[0] if "_Q" in pdf.name else pdf.stem
        status, pages, blocks = validate(pdf, args.min_pages)
        verdict, subdir = VERDICT.get(status, ("INCORRECT", "_rejected"))
        exp_q = expected_quarter(pdf.name)
        dq, dfy = detect_quarter(blocks) if blocks else (None, None)
        det_q = f"{dq} {dfy}" if dq else ""
        if exp_q and dq:
            qmatch = "MATCH" if det_q == exp_q else "MISMATCH"
        else:
            qmatch = "UNPARSED" if exp_q else ""
        rows.append({"verdict": verdict, "company": names.get(slug, ""), "slug": slug,
                     "file": pdf.name, "pages": pages, "expected_quarter": exp_q,
                     "detected_quarter": det_q, "quarter_match": qmatch,
                     "status": status, "moved_to": subdir or "",
                     "_path": pdf, "_subdir": subdir})
        if i % 50 == 0 or i == len(pdfs):
            print(f"  [{i}/{len(pdfs)}] ...")

    # move rejects / needs-ocr out of the folder
    moved = {"_rejected": 0, "_needs_ocr": 0}
    if not args.dry_run:
        for r in rows:
            sub = r["_subdir"]
            if sub:
                d = src / sub
                d.mkdir(exist_ok=True)
                r["_path"].rename(d / r["file"])
                moved[sub] += 1

    # write CSV: correct on top, incorrect at the bottom
    rows.sort(key=lambda r: (VERDICT_ORDER[r["verdict"]], r["slug"]))
    with open(STATUS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in FIELDS})

    from collections import Counter
    vc = Counter(r["verdict"] for r in rows)
    sc = Counter(r["status"] for r in rows if r["verdict"] == "INCORRECT")
    qm = Counter(r["quarter_match"] for r in rows if r["verdict"] == "CORRECT")
    print(f"\n{'='*56}\nVALIDATION SUMMARY ({len(rows)} files)")
    print(f"  CORRECT   {vc['CORRECT']:4}  (kept in folder)")
    print(f"  NEEDS_OCR {vc['NEEDS_OCR']:4}  ({'moved to _needs_ocr/' if not args.dry_run else 'dry-run'})")
    print(f"  INCORRECT {vc['INCORRECT']:4}  ({'moved to _rejected/' if not args.dry_run else 'dry-run'})")
    print(f"  INCORRECT by reason: " + ", ".join(f"{k}={v}" for k, v in sc.most_common()))
    print(f"  quarter of CORRECT files: " + ", ".join(f"{k or 'na'}={v}" for k, v in qm.most_common()))
    print(f"  -> {STATUS_CSV}")


if __name__ == "__main__":
    main()
