#!/usr/bin/env python3
"""Download Indian earnings-call (concall) transcripts to transcripts/new_transcripts/.

Source order per quarter:
  1. screener.in concall list (public; real link is <a>Transcript</a>, an inert
     <div>Transcript</div> means screener has no link for that quarter).
  2. BSE announcements API (AnnSubCategoryGetData) -> "Earnings Call Transcript".
Download URL is always AnnPdfOpen.aspx?Pname=... (works for filings of any age).
Each PDF is page-count checked: a real transcript is ~15-25 pages; <5 pages is
almost always a 1-page cover letter (the real transcript may be on the company IR
site) and is flagged COVER?.

Usage:
  python scripts/download_transcripts.py FCL                  # last 4 quarters
  python scripts/download_transcripts.py APCOTEXIND BALAMINES --quarters 4
  python scripts/download_transcripts.py IPL:india_pesticides # force a file slug

Quarter mapping (Indian FY, by announcement month):
  Jul-Sep -> Q1, Oct-Dec -> Q2, Jan-Mar -> Q3, Apr-Jun -> Q4
  (FY = the fiscal year ending the following March; e.g. Aug-2025 -> Q1 FY26).
"""
from __future__ import annotations
import argparse, json, os, re, sys, time, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "transcripts", "new_transcripts")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
# canonical results-announcement month per quarter, used to pick among duplicates
CANON = {"Q1": 8, "Q2": 11, "Q3": 2, "Q4": 5}


def get(url: str, headers: dict | None = None, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_text(url: str, headers: dict | None = None) -> str:
    try:
        return get(url, headers).decode("utf-8", "replace")
    except Exception as e:
        print(f"    ! fetch failed {url[:60]}: {e}", file=sys.stderr)
        return ""


def quarter_of(year: int, month: int) -> tuple[str, int]:
    if month in (4, 5, 6):   return "Q4", year
    if month in (7, 8, 9):   return "Q1", year + 1
    if month in (10, 11, 12):return "Q2", year + 1
    return "Q3", year  # Jan-Mar


def slugify(name: str) -> str:
    name = re.sub(r"\b(Ltd|Limited)\.?\b", "", name, flags=re.I)  # drop corporate suffix
    name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return name


# ---------------------------------------------------------------- screener
_LI = re.compile(r'<li class="flex flex-gap-8[^"]*">(.*?)</li>', re.S)
_DATE = re.compile(r'>\s*((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d\d))\s*<')
_TA = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>\s*Transcript\s*</a>')


def screener_company(html: str) -> tuple[str | None, str | None]:
    """Return (company_slug, bse_scrip_code) parsed from the screener page."""
    code = None
    m = re.search(r'/stock-share-price/[^/]+/[^/]+/(\d+)/', html)
    if m:
        code = m.group(1)
    name = None
    m = re.search(r'<h1[^>]*>\s*([^<]+?)\s*</h1>', html)
    if m:
        name = slugify(m.group(1))
    return name, code


def screener_transcripts(html: str) -> dict[tuple[int, str], str]:
    """{(fy, quarter): url} for quarters where screener exposes a real link."""
    out: dict[tuple[int, str], tuple] = {}  # value: (dist, url)
    start = html.find(">Concalls<")
    chunk = html[start:start + 20000] if start >= 0 else ""
    for li in _LI.finditer(chunk):
        block = li.group(1)
        d = _DATE.search(block)
        a = _TA.search(block)
        if not d or not a:
            continue
        mon, yr = MONTHS[d.group(2)], int(d.group(3))
        q, fy = quarter_of(yr, mon)
        dist = abs(mon - CANON[q])
        key = (fy, q)
        if key not in out or dist < out[key][0]:
            out[key] = (dist, a.group(1))
    return {k: v[1] for k, v in out.items()}


# ---------------------------------------------------------------- BSE
def bse_transcripts(scrip: str, frm="20240101", to="20271231") -> dict[tuple[int, str], str]:
    """{(fy, quarter): AnnPdfOpen_url} from BSE 'Earnings Call Transcript' filings."""
    headers = {"Origin": "https://www.bseindia.com",
               "Referer": "https://www.bseindia.com/corporates/ann.html",
               "Accept": "application/json, text/plain, */*"}
    rows = []
    for page in range(1, 12):
        url = ("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?"
               f"pageno={page}&strCat=-1&strPrevDate={frm}&strToDate={to}"
               f"&strScrip={scrip}&strSearch=P&strType=C&subcategory=-1")
        txt = get_text(url, headers)
        if len(txt) < 60:
            break
        try:
            batch = json.loads(txt).get("Table", [])
        except Exception:
            break
        if not batch:
            break
        rows += batch
        if len(batch) < 50:
            break
        time.sleep(0.2)
    out: dict[tuple[int, str], tuple] = {}
    for r in rows:
        if "transcript" not in (r.get("SUBCATNAME") or "").lower():
            continue
        dt = r.get("NEWS_DT") or ""
        m = re.match(r'(\d{4})-(\d{2})', dt)
        att = r.get("ATTACHMENTNAME")
        if not m or not att:
            continue
        q, fy = quarter_of(int(m.group(1)), int(m.group(2)))
        url = f"https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname={att}"
        key = (fy, q)
        if key not in out or dt < out[key][0]:  # earliest filing in the quarter
            out[key] = (dt, url)
    return {k: v[1] for k, v in out.items()}


# ---------------------------------------------------------------- pdf check
def pdf_page_count(path: str) -> int:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        try:
            from pypdf import PdfReader
            return len(PdfReader(path).pages)
        except Exception:
            return -1  # unknown


def download_pdf(url: str, path: str) -> tuple[str, int, int]:
    """Return (status, size, pages). status: OK | COVER? | NOTPDF | FAIL."""
    ref = "https://www.bseindia.com/" if "bseindia" in url else url
    try:
        data = get(url, {"Referer": ref}, timeout=50)
    except Exception as e:
        return f"FAIL:{e}".replace("\n", " ")[:40], 0, 0
    if not data.startswith(b"%PDF"):
        return "NOTPDF", len(data), 0
    with open(path, "wb") as f:
        f.write(data)
    pages = pdf_page_count(path)
    if 0 <= pages < 5:
        return "COVER?", len(data), pages   # likely a 1-page cover letter
    return "OK", len(data), pages


# ---------------------------------------------------------------- main
def process(token: str, n_quarters: int, out_dir: str) -> None:
    ticker, _, forced_slug = token.partition(":")
    ticker = ticker.upper()
    html = get_text(f"https://www.screener.in/company/{ticker}/")
    if not html:
        print(f"{ticker}: could not load screener page")
        return
    slug, scrip = screener_company(html)
    slug = forced_slug or slug or ticker.lower()

    found = screener_transcripts(html)            # (fy,q) -> url  (screener links)
    if len(found) < n_quarters and scrip:         # fill gaps from BSE
        for k, url in bse_transcripts(scrip).items():
            found.setdefault(k, url)

    targets = sorted(found, reverse=True)[:n_quarters]   # most recent N quarters
    if not targets:
        print(f"{ticker} ({slug}): NO transcripts found on screener or BSE "
              f"(may not hold concalls / files only on company site).")
        return

    line = [f"{ticker} -> {slug} (scrip {scrip or '?'})"]
    os.makedirs(out_dir, exist_ok=True)
    for fy, q in targets:
        fname = f"{slug}_{q}_FY{fy % 100:02d}.pdf"
        status, size, pages = download_pdf(found[(fy, q)], os.path.join(out_dir, fname))
        tag = f"{q} FY{fy % 100:02d}: {status}"
        if status in ("OK", "COVER?"):
            tag += f" ({pages}p, {size // 1024}KB)"
        line.append("  " + tag)
        time.sleep(0.3)
    print("\n".join(line))


def main() -> None:
    ap = argparse.ArgumentParser(description="Download concall transcripts from screener.in / BSE.")
    ap.add_argument("tickers", nargs="+",
                    help="NSE/screener tickers, optionally TICKER:file_slug (e.g. IPL:india_pesticides)")
    ap.add_argument("--quarters", type=int, default=4, help="number of most-recent quarters (default 4)")
    ap.add_argument("--out", default=os.path.normpath(DEFAULT_OUT), help="output directory")
    args = ap.parse_args()
    print(f"Saving to {args.out}\n")
    for tok in args.tickers:
        try:
            process(tok, args.quarters, args.out)
        except Exception as e:
            print(f"{tok}: ERROR {e}")
        print()


if __name__ == "__main__":
    main()
