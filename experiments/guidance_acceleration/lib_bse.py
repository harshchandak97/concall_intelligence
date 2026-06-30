#!/usr/bin/env python3
"""lib_bse.py — self-contained data helpers for the guidance-acceleration experiment.

Everything this experiment needs to (a) enumerate the Q4-FY24 concall cohort and
(b) read current market cap, in one place, using only the Python standard library.

The HTTP / PDF / quarter helpers are duplicated verbatim from the repo's
`scripts/download_transcripts.py` ON PURPOSE — the experiment must stay isolated in
this folder and not import from the production pipeline (per the experiment plan).

Two pieces are new and specific to this experiment:
  * bse_transcript_sweep()  — MARKET-WIDE BSE announcements sweep for every
    "Earnings Call Transcript" filing in a date window (the concall universe).
  * screener_market_cap()   — current market cap (₹ crore) from a screener page.
"""
from __future__ import annotations
from pathlib import Path
import datetime, json, re, sys, time, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# canonical results-announcement month per quarter, used to pick among duplicates
CANON = {"Q1": 8, "Q2": 11, "Q3": 2, "Q4": 5}


# ---------------------------------------------------------------- http (stdlib)
def get(url: str, headers: dict | None = None, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_text(url: str, headers: dict | None = None) -> str:
    try:
        return get(url, headers).decode("utf-8", "replace")
    except Exception as e:
        print(f"    ! fetch failed {url[:70]}: {e}", file=sys.stderr)
        return ""


def quarter_of(year: int, month: int) -> tuple[str, int]:
    """Indian FY quarter from announcement month. Apr-Jun=Q4, FY ends next Mar."""
    if month in (4, 5, 6):    return "Q4", year
    if month in (7, 8, 9):    return "Q1", year + 1
    if month in (10, 11, 12): return "Q2", year + 1
    return "Q3", year  # Jan-Mar


def slugify(name: str) -> str:
    name = re.sub(r"\b(Ltd|Limited)\.?\b", "", name, flags=re.I)  # drop suffix
    name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return name


# ---------------------------------------------------------------- BSE sweep
# Market-wide announcements feed, filtered to earnings-call transcripts. Unlike
# the per-scrip query in scripts/download_transcripts.py, this passes an empty
# strScrip plus the category/subcategory NAMES (verified: empty scrip + "-1"
# category returns nothing; the names work) to fetch the whole market at once.
_BSE_ANN = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
_BSE_HEADERS = {"Origin": "https://www.bseindia.com",
                "Referer": "https://www.bseindia.com/corporates/ann.html",
                "Accept": "application/json, text/plain, */*"}


def _nsurl_ticker_slug(nsurl: str) -> tuple[str | None, str | None]:
    """Parse NSE ticker + slug from a BSE NSURL like
    https://www.bseindia.com/stock-share-price/asian-paints-ltd/asianpaint/500820/
    -> ('asianpaint', 'asian-paints-ltd')."""
    m = re.search(r"/stock-share-price/([^/]+)/([^/]+)/\d+/?", nsurl or "")
    if not m:
        return None, None
    return m.group(2), m.group(1)  # (nse_ticker, slug)


def _date_chunks(frm: str, to: str, days: int = 28):
    """Yield ('YYYYMMDD','YYYYMMDD') sub-windows of <= `days`. BSE's announcements
    API silently returns NOTHING for windows wider than ~1 month, so we must
    split the requested range and sweep each piece."""
    d0 = datetime.datetime.strptime(frm, "%Y%m%d").date()
    d1 = datetime.datetime.strptime(to, "%Y%m%d").date()
    step = datetime.timedelta(days=days - 1)
    cur = d0
    while cur <= d1:
        end = min(cur + step, d1)
        yield cur.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        cur = end + datetime.timedelta(days=1)


def _sweep_window(frm: str, to: str, max_pages: int, pause: float) -> list[dict]:
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        # quote (not quote_plus): BSE needs spaces as %20, not '+'
        q = urllib.parse.urlencode({
            "pageno": page, "strCat": "Company Update",
            "strPrevDate": frm, "strToDate": to, "strScrip": "",
            "strSearch": "P", "strType": "C",
            "subcategory": "Earnings Call Transcript",
        }, quote_via=urllib.parse.quote)
        txt = get_text(f"{_BSE_ANN}?{q}", _BSE_HEADERS)
        if len(txt) < 40:
            break
        try:
            batch = json.loads(txt).get("Table", [])
        except Exception:
            break
        if not batch:
            break
        for r in batch:
            if "transcript" not in (r.get("SUBCATNAME") or "").lower():
                continue
            att = r.get("ATTACHMENTNAME")
            scrip = r.get("SCRIP_CD")
            if not att or not scrip:
                continue
            ticker, slug = _nsurl_ticker_slug(r.get("NSURL") or "")
            out.append({
                "scrip": str(scrip),
                "name": r.get("SLONGNAME") or "",
                "news_dt": r.get("NEWS_DT") or "",
                "attachment": att,
                "nse_ticker": ticker,
                "slug": slug,
                "headline": r.get("HEADLINE") or "",
            })
        if len(batch) < 50:
            break
        time.sleep(pause)
    return out


def bse_transcript_sweep(frm: str, to: str, max_pages: int = 80,
                         pause: float = 0.25) -> list[dict]:
    """Every 'Earnings Call Transcript' filing across ALL companies in [frm, to].

    frm/to are 'YYYYMMDD'. The window is split into <=1-month chunks (BSE limit).
    Returns one dict per filing (not yet deduped):
      {scrip, name, news_dt, attachment, nse_ticker, slug, headline}
    """
    out: list[dict] = []
    for cf, ct in _date_chunks(frm, to):
        chunk = _sweep_window(cf, ct, max_pages, pause)
        out += chunk
        print(f"    sweep {cf}..{ct}: {len(chunk)} transcript filings "
              f"(cumulative {len(out)})")
    return out


def dedup_earliest(rows: list[dict]) -> list[dict]:
    """One row per scrip, keeping the EARLIEST filing (the concall, not a
    re-upload). Assumes news_dt is ISO-ish so string compare == time compare."""
    best: dict[str, dict] = {}
    for r in rows:
        k = r["scrip"]
        if k not in best or r["news_dt"] < best[k]["news_dt"]:
            best[k] = r
    return sorted(best.values(), key=lambda r: r["name"].lower())


def attachment_url(attachment: str) -> str:
    return f"https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname={attachment}"


# ---------------------------------------------------------------- screener
_MCAP_RE = re.compile(
    r"Market Cap.*?<span[^>]*class=\"number\"[^>]*>\s*([\d,]+(?:\.\d+)?)\s*</span>",
    re.S)


def screener_market_cap(html: str) -> float | None:
    """Current market cap in ₹ crore from a screener company page (#top-ratios).
    Indian-formatted '2,53,727' -> 253727.0."""
    m = _MCAP_RE.search(html)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def screener_name(html: str) -> str | None:
    """Canonical company name from a screener page <h1> (fallback when the BSE
    feed's SLONGNAME is blank)."""
    m = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", html or "")
    return m.group(1).strip() if m else None


def screener_sector_industry(html: str) -> tuple[str | None, str | None]:
    """(sector, industry) from a screener company page. Screener marks these as
    e.g. ...Sector">Commodities, ...Sector">Metals & Mining, ...Industry">Diversified
    Metals — the macro sector first, the granular sector second. We keep the
    granular (last) Sector and the first Industry. Used to let a human reject
    sector-mismatched outputs (real-estate pre-sales, lender AUM, etc.)."""
    import html as _html
    secs = re.findall(r"Sector\">\s*([^<]{1,60})", html or "")
    inds = re.findall(r"Industry\">\s*([^<]{1,60})", html or "")
    sector = _html.unescape(secs[-1].strip()) if secs else None
    industry = _html.unescape(inds[0].strip()) if inds else None
    return sector, industry


def screener_url(scrip: str) -> str:
    # screener resolves a BSE scrip code straight to the company page
    return f"https://www.screener.in/company/{scrip}/"


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
            return -1


def download_pdf(url: str, path: str) -> tuple[str, int, int]:
    """Return (status, size, pages). status: OK | COVER? | NOTPDF | FAIL."""
    ref = "https://www.bseindia.com/" if "bseindia" in url else url
    try:
        data = get(url, {"Referer": ref}, timeout=60)
    except Exception as e:
        return f"FAIL:{e}".replace("\n", " ")[:40], 0, 0
    if not data.startswith(b"%PDF"):
        return "NOTPDF", len(data), 0
    with open(path, "wb") as f:
        f.write(data)
    pages = pdf_page_count(path)
    if 0 <= pages < 5:
        return "COVER?", len(data), pages  # likely a 1-page cover letter
    return "OK", len(data), pages


# ============================================================================
# EXHAUSTIVE (enumeration-driven) approach — used by build_universe_screener.py.
# The market-wide BSE sweep above is high-precision but leaks recall (late /
# mistagged filings). These helpers instead enumerate EVERY listed company from
# the exchange master lists, then ask screener per company "does it do concalls,
# and is the transcript downloadable?" — completeness can't be defeated by a tag.
# ============================================================================

# ---------------------------------------------------------------- exchange masters
_BSE_SCRIPS = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?"
               "Group=&Scripcode=&industry=&segment=Equity&status=Active")
_NSE_EQUITY = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"


def _f(x) -> float | None:
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def bse_active_equity() -> list[dict]:
    """Every ACTIVE BSE equity scrip. Each: scrip, ticker, isin, name, nsurl,
    bse_mcap_cr (₹ cr, may be None). This is the primary enumerator — ~5,000
    names, and it already carries ISIN (the union key) and current mcap."""
    import json as _json
    rows = _json.loads(get(_BSE_SCRIPS, _BSE_HEADERS).decode("utf-8", "replace"))
    out = []
    for r in rows:
        out.append({
            "scrip": str(r.get("SCRIP_CD") or "").strip(),
            "ticker": (r.get("scrip_id") or "").strip(),
            "isin": (r.get("ISIN_NUMBER") or "").strip().upper(),
            "name": (r.get("Issuer_Name") or r.get("Scrip_Name") or "").strip(),
            "nsurl": r.get("NSURL") or "",
            "bse_mcap_cr": _f(r.get("Mktcap")),
        })
    return [r for r in out if r["scrip"]]


def nse_equity_list() -> list[dict]:
    """Every NSE EQ-series symbol. Each: ticker, isin, name. Used only to ADD
    NSE-only listings (no BSE scrip) the BSE master can't see — dedup by ISIN."""
    import csv as _csv, io as _io
    txt = get(_NSE_EQUITY, {"Referer": "https://www.nseindia.com/"}).decode(
        "utf-8", "replace")
    out = []
    for r in _csv.DictReader(_io.StringIO(txt)):
        r = {k.strip(): (v or "").strip() for k, v in r.items()}
        out.append({"ticker": r.get("SYMBOL", ""),
                    "isin": r.get("ISIN NUMBER", "").upper(),
                    "name": r.get("NAME OF COMPANY", "")})
    return [r for r in out if r["ticker"]]


def union_masters(bse: list[dict], nse: list[dict]) -> list[dict]:
    """BSE ∪ NSE-only, deduped by ISIN. BSE rows win (they carry scrip+mcap);
    NSE rows lacking a matching ISIN are appended as NSE-only (no scrip)."""
    seen = {r["isin"] for r in bse if r["isin"]}
    merged = [dict(r, exchanges="BSE") for r in bse]
    for r in nse:
        if r["isin"] and r["isin"] in seen:
            continue
        merged.append({"scrip": "", "ticker": r["ticker"], "isin": r["isin"],
                       "name": r["name"], "nsurl": "", "bse_mcap_cr": None,
                       "exchanges": "NSE"})
    return merged


# ---------------------------------------------------------------- screener concalls
_CONCALL_LI = re.compile(r'<li class="flex flex-gap-8[^"]*">(.*?)</li>', re.S)
_CONCALL_DATE = re.compile(
    r'>\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d\d)\s*<')
_CONCALL_TA = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>\s*Transcript\s*</a>', re.S)
_MONTHS = {m: i for i, m in enumerate(
    ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
     "Oct", "Nov", "Dec"])}


def screener_concalls(html: str) -> list[dict]:
    """Parse the Concalls section of a screener page into one row per call:
      {date 'YYYY-MM', fy, quarter, transcript_url|None}
    A row with a date but transcript_url=None means the company DOES concalls
    but screener has no downloadable link (inert <div>Transcript</div>) — caller
    should fall back to BSE. Empty list = no concall section at all."""
    start = html.find(">Concalls<")
    if start < 0:
        return []
    chunk = html[start:start + 25000]
    rows = []
    for li in _CONCALL_LI.finditer(chunk):
        block = li.group(1)
        d = _CONCALL_DATE.search(block)
        if not d:
            continue
        mon, yr = _MONTHS[d.group(1)], int(d.group(2))
        q, fy = quarter_of(yr, mon)
        a = _CONCALL_TA.search(block)
        rows.append({"date": f"{yr:04d}-{mon:02d}", "fy": fy, "quarter": q,
                     "transcript_url": a.group(1) if a else None})
    return rows


def pick_concall(concalls: list[dict], fy: int, quarter: str) -> dict | None:
    """The concall row matching (fy, quarter); the one with a transcript_url
    wins if duplicated. None if the company never held that quarter's call."""
    cand = [c for c in concalls if c["fy"] == fy and c["quarter"] == quarter]
    if not cand:
        return None
    cand.sort(key=lambda c: c["transcript_url"] is None)  # linked first
    return cand[0]


def bse_transcript_for_scrip(scrip: str, fy: int, quarter: str,
                             frm: str = "20240101", to: str = "20271231",
                             pause: float = 0.2) -> str | None:
    """TARGETED per-scrip BSE fallback (not the market sweep): the AnnPdfOpen URL
    of the 'Earnings Call Transcript' this scrip filed for (fy, quarter), or None.
    Used when screener shows the concall but exposes no transcript link."""
    best = None
    for page in range(1, 12):
        url = (f"{_BSE_ANN}?pageno={page}&strCat=-1&strPrevDate={frm}"
               f"&strToDate={to}&strScrip={scrip}&strSearch=P&strType=C"
               f"&subcategory=-1")
        txt = get_text(url, _BSE_HEADERS)
        if len(txt) < 60:
            break
        try:
            batch = json.loads(txt).get("Table", [])
        except Exception:
            break
        if not batch:
            break
        for r in batch:
            # accept the canonical "Earnings Call Transcript" subcategory OR any
            # filing whose HEADLINE says "transcript" — the latter recovers
            # transcripts mis-filed under "Analyst / Investor Meeting" etc.
            sub = (r.get("SUBCATNAME") or "").lower()
            head = (r.get("HEADLINE") or "").lower()
            if "transcript" not in sub and "transcript" not in head:
                continue
            dt = (r.get("NEWS_DT") or "")[:10]
            att = r.get("ATTACHMENTNAME")
            if len(dt) < 7 or not att:
                continue
            q, f = quarter_of(int(dt[:4]), int(dt[5:7]))
            if (f, q) != (fy, quarter):
                continue
            if best is None or dt < best[0]:  # earliest filing in the quarter
                best = (dt, attachment_url(att))
        if len(batch) < 50:
            break
        time.sleep(pause)
    return best[1] if best else None


# ---------------------------------------------------------------- pdf content check
# markers that a PDF really is an earnings-call transcript, not a cover letter,
# investor presentation, or wrong attachment. Kept broad on purpose: transcripts
# vary in wording ("earnings call" / "earnings meet" / "analyst meet"; "moderator"
# / "speaker" / "management"), and the page-count gate + the fact the link came
# from a "Transcript" anchor already bias toward correctness — this is a guard
# against cover-only PDFs and 404-HTML, not a strict classifier.
# Positive markers — dialogue/call phrases a spoken earnings call contains. Note
# what is DELIBERATELY ABSENT: "management discussion", "speaker", "good morning"
# — those appear in annual reports / management lists too and were the main way a
# non-transcript slipped through. Identity is confirmed by the source-keyed link,
# so the only job here is "is this the actual spoken call?".
_TRANSCRIPT_MARKERS = re.compile(
    r"(earnings\s*(?:call|meet|conference)|conference\s*call|con\s*call|concall|"
    r"analyst\s*(?:call|meet)|investor\s*(?:call|conference|meet)|"
    r"ladies\s+and\s+gentlemen|\bmoderator\b|"
    r"\bq&a\b|question[\s-]and[\s-]answer|question\s+session|"
    r"floor\s+is\s+now\s+open|(?:first|next)\s+question)",
    re.I)
# strong DIALOGUE signal — only a real spoken call has these. The single best
# discriminator from a transcript vs an annual report / deck / press release.
_DIALOGUE_MARKERS = re.compile(
    r"ladies\s+and\s+gentlemen|\bmoderator\b|the\s+operator|floor\s+is\s+now\s+open",
    re.I)
# HARD-NEGATIVE markers — structural / statutory language that means the document
# is an AGM transcript, annual report, or financial statement, NOT an earnings
# call. These override even strong transcript wording (e.g. an AGM transcript has
# dialogue too). Deliberately NOT here: the bare phrase "annual report", which
# occurs INSIDE real calls ("as you'll see in our annual report") and was causing
# genuine transcripts (eClerx) to be wrongly rejected.
_NONTRANSCRIPT_MARKERS = re.compile(
    r"notice\s+is\s+hereby\s+given|"
    r"(?:notice\s+of\s+the\s+|convening\s+the\s+)?annual\s+general\s+meeting|"
    r"\b(?:board'?s?|directors?'?)\s+report|independent\s+auditor|"
    r"balance\s+sheet\s+as\s+at|statement\s+of\s+profit\s+and\s+loss|"
    r"notes\s+to\s+the\s+(?:standalone\s+|consolidated\s+)?financial\s+statements|"
    r"cash\s+flow\s+statement|corporate\s+governance\s+report",
    re.I)
# real transcripts in this universe top out ~57 pages; annual reports run 100-300.
# A 70-page ceiling catches long non-transcripts (UPL's 79p summary) with margin.
_MAX_TRANSCRIPT_PAGES = 70


def pdf_first_text(path: str, pages: int = 6) -> str:
    """Concatenated text of the first `pages` pages (lower-cased), or '' on
    failure. Six pages by default so the moderator's opening (usually page 2-3,
    after the cover letter + management list) is reliably in the sample."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "")
                             for p in pdf.pages[:pages]).lower()
    except Exception:
        try:
            from pypdf import PdfReader
            rdr = PdfReader(path)
            return "\n".join((pg.extract_text() or "")
                             for pg in rdr.pages[:pages]).lower()
        except Exception:
            return ""


def classify_transcript(text: str, pages: int, sampled_pages: int = 6) -> str:
    """Decide what a downloaded PDF actually is from its first-pages text + length.
    Returns one of: OK | NOTTRANSCRIPT | NEEDS_OCR.
      * NEEDS_OCR     — multi-page but no extractable text (image-only scan).
      * NOTTRANSCRIPT — annual report / deck / press release / wrong attachment.
      * OK            — reads like the actual spoken earnings call.
    Recall-leaning: a real call is kept whenever it shows dialogue OR a call name
    in dense prose; only clear statutory/long/empty docs are rejected."""
    chars = len(text.strip())
    if pages >= 3 and chars < 400:
        return "NEEDS_OCR"  # image-only scan — recoverable, not "wrong"

    dialogue = bool(_DIALOGUE_MARKERS.search(text))
    markers = len({m.group(0).lower() for m in _TRANSCRIPT_MARKERS.finditer(text)})
    nontranscript = bool(_NONTRANSCRIPT_MARKERS.search(text))
    density = chars / max(min(pages, sampled_pages), 1)

    # only the page ceiling is absolute (a 100-page PDF is never a transcript).
    if pages > _MAX_TRANSCRIPT_PAGES:
        return "NOTTRANSCRIPT"            # far too long to be a transcript (AR)

    # STRONG positive wins next: a real call has dialogue or >=2 call markers.
    # This must beat the negatives, because real transcripts routinely mention
    # "balance sheet" / "cash flow statement" / "AGM" in their opening — rejecting
    # on those wrongly drops genuine calls (bandhan-bank, dhanuka, vedant, …).
    if dialogue or markers >= 2:
        return "OK"

    # WEAK positive: a structural/statutory marker now decides. Pure AGM minutes
    # or a financial-results PDF (no call dialogue, <2 markers) are rejected here.
    if nontranscript:
        return "NOTTRANSCRIPT"            # AGM / financial statements / report
    if markers >= 1 and density > 1500:  # unusual wording but clearly prose (BEML)
        return "OK"
    return "NOTTRANSCRIPT"


def looks_like_transcript(text: str, min_markers: int = 2) -> bool:
    """Back-compat boolean wrapper. Page count unknown here, so length-only —
    callers that have the page count should prefer classify_transcript()."""
    return classify_transcript(text, pages=10) == "OK"


def validate_transcript_pdf(path: str, min_pages: int = 5,
                            content_pages: int = 6) -> tuple[str, int]:
    """Validate an EXISTING local PDF. Returns (status, pages):
      OK            real transcript (>= min_pages AND content reads like a call)
      COVER?        too few pages (likely a 1-page cover letter / announcement)
      NOTTRANSCRIPT enough pages but content is a deck / annual report / wrong file
      NEEDS_OCR     multi-page but image-only (no text) — recoverable via OCR
      MISSING       file absent
      BADPDF        unreadable / not a PDF
    Page count is the cheap gate; content is the confirmation. The downloader
    uses this to skip re-downloading a file that is already a valid transcript."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return "MISSING", 0
    with open(p, "rb") as f:
        if f.read(4) != b"%PDF":
            return "BADPDF", 0
    pages = pdf_page_count(str(p))
    if pages < 0:
        return "BADPDF", 0
    if pages < min_pages:
        return "COVER?", pages
    # sample == content_pages so density normalizes by what was actually read
    return (classify_transcript(pdf_first_text(str(p), content_pages), pages,
                                sampled_pages=content_pages), pages)


# ---------------------------------------------------------------- cover-link follow
# A 1-2 page cover letter / BSE announcement often does not contain the call —
# it points to it ("the transcript is available at <URL>"). Rather than re-search
# for the document, follow that link and validate what it returns. Used inline by
# the downloader on a COVER? result, and by recover_covers.py.
def pdf_all_text(path: str) -> str:
    """Full text of a PDF (pdfplumber, pypdf fallback), or '' on failure."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(pg.extract_text() or "" for pg in pdf.pages)
    except Exception:
        try:
            from pypdf import PdfReader
            return "\n".join(pg.extract_text() or "" for pg in PdfReader(path).pages)
        except Exception:
            return ""


def pdf_urls(path: str) -> list[str]:
    """Distinct http(s) URLs in a PDF's text, in order, trailing punctuation
    stripped. The cover letter's link to the real transcript lives here."""
    seen, out = set(), []
    for u in re.findall(r"https?://[^\s\]\)>\"']+", pdf_all_text(path)):
        u = u.rstrip(".,;)")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _href_pdf_in_html(html: str, base: str) -> str | None:
    """First <a href> that points at a .pdf, made absolute against `base`."""
    m = re.search(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.I)
    if not m:
        return None
    href = m.group(1)
    return href if href.startswith("http") else urllib.parse.urljoin(base, href)


def fetch_pdf_bytes(url: str, follow_html: bool = True) -> bytes | None:
    """GET `url` and return PDF bytes. If it serves HTML (an IR page embedding a
    viewer) and follow_html, fetch the first linked .pdf — one level only."""
    ref = "https://www.bseindia.com/" if "bseindia" in url else url
    try:
        data = get(url, {"Referer": ref}, timeout=45)
    except Exception:
        return None
    if data.startswith(b"%PDF"):
        return data
    if follow_html:
        pdf_url = _href_pdf_in_html(data.decode("utf-8", "replace")[:40_000], url)
        if pdf_url and pdf_url != url:
            return fetch_pdf_bytes(pdf_url, follow_html=False)
    return None


def follow_cover_link(cover_pdf: str, dest: str, min_pages: int = 5,
                      content_pages: int = 6) -> tuple[str, int]:
    """Follow a cover letter's embedded link to the real transcript.
    Extract URLs from `cover_pdf`, download each, and validate with
    validate_transcript_pdf (so a link to an annual report / deck is rejected).
    On the first that validates OK, write it to `dest` and return ('OK', pages).
    Returns ('NOLINK', 0) if the cover has no URL or none yields a transcript."""
    urls = pdf_urls(cover_pdf)
    if not urls:
        return "NOLINK", 0
    tmp = Path(dest).with_suffix(".pdf.linktmp")
    last: tuple[str, int] = ("NOLINK", 0)
    for u in urls:
        data = fetch_pdf_bytes(u)
        if not data:
            continue
        tmp.write_bytes(data)
        status, pages = validate_transcript_pdf(str(tmp), min_pages, content_pages)
        if status == "OK":
            tmp.replace(dest)
            return "OK", pages
        last = (status, pages)
        tmp.unlink(missing_ok=True)
    tmp.unlink(missing_ok=True)
    return last
