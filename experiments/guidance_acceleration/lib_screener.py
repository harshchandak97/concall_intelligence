#!/usr/bin/env python3
"""lib_screener.py — fetch the FULL annual P&L series from Screener.in, anchored
at the call's fiscal year (FY24 for this Q4-FY24 cohort).

Why not reuse the repo's screener.py as-is: that helper reads only the LAST
column of the P&L (today's latest FY) and Screener's own pre-computed "3yr CAGR"
also ends at the latest reported year. For this experiment the calls are Q4 FY24,
so BOTH the forward base (current revenue/PAT/margins) AND the trailing PAT CAGR
must be anchored at **FY24** — not at FY25/FY26 which Screener now shows. The fix
is to parse every year column Screener exposes (~10-12 years) and pick FY24
ourselves, then compute trailing CAGR (FY21->FY24) from the series.

Public API:
  fetch_series(scrip, ticker=None)  -> {basis, url, fy_series:{fy:{sales,net_profit,opm_pct,pbt}}, pe, market_cap_cr, name}
  base_and_trailing(series, base_fy=2024, lookback=3) -> per-company base + trailing CAGR dict

Screener is free, no login. We hit it politely (one page per company, UA header).
"""
from __future__ import annotations
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0 Safari/537.36")}

# P&L row labels we care about -> our key
_PNL_ROWS = {
    "Sales": "sales",
    "Net Profit": "net_profit",
    "OPM %": "opm_pct",
    "Profit before tax": "pbt",
}
# "Mar 2024" / "Mar 2024 TTM" -> fiscal year ending that March (FY24 == 2024)
_FY_RE = re.compile(r"Mar\s+(\d{4})")


_CALL_RE = re.compile(r"Q([1-4])\s*FY\s*(\d{2,4})", re.I)


def base_fy_from_call_period(call_period: str, default: int = 2024) -> int:
    """Last COMPLETED fiscal year as of the call, from its call_period.
      Q4 FYxx -> xx      (the year just ended at the call)
      Q1-3 FYxx -> xx-1  (last fully reported annual; the current FY is incomplete)
    Anchors base figures + the trailing window consistently for any call quarter,
    which Screener's annual series (10-12y) supports but its ~13-quarter table
    cannot reach 3 years back for. Returns a 4-digit year (FY24 -> 2024)."""
    m = _CALL_RE.search(call_period or "")
    if not m:
        return default
    q, yy = int(m.group(1)), int(m.group(2))
    fy = yy + 2000 if yy < 100 else yy
    return fy if q == 4 else fy - 1


def _num(text: str):
    clean = re.sub(r"[₹,%\s]", "", (text or "").strip())
    clean = clean.replace("−", "-")  # screener sometimes uses a unicode minus
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_pnl(soup: BeautifulSoup) -> dict:
    """Return {fy(int): {sales, net_profit, opm_pct, pbt}} from the annual P&L
    section. Maps each 'Mar YYYY' column header to its fiscal year; ignores any
    column that isn't a fiscal year (Screener has no stray ones here, but be safe)."""
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2 or "Profit" not in h2.get_text():
            continue
        table = section.find("table")
        if not table:
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        # col index -> fiscal year (skip col 0, the row-label column)
        col_fy = {}
        for idx, h in enumerate(header_cells):
            m = _FY_RE.search(h)
            if m:
                col_fy[idx] = int(m.group(1))
        if not col_fy:
            continue
        fy_series = {fy: {} for fy in col_fy.values()}
        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if not cells:
                continue
            label = cells[0].replace("+", "").strip()
            key = _PNL_ROWS.get(label)
            if not key:
                continue
            for idx, fy in col_fy.items():
                if idx < len(cells):
                    fy_series[fy][key] = _num(cells[idx])
        return fy_series
    return {}


def _top_ratios(soup: BeautifulSoup) -> tuple:
    pe = market_cap = None
    ul = soup.find("ul", {"id": "top-ratios"})
    if ul:
        for li in ul.find_all("li"):
            t = li.get_text(separator=" ", strip=True)
            if "Stock P/E" in t:
                pe = _num(t.split()[-1])
            elif "Market Cap" in t:
                m = re.search(r"[\d,]+\.?\d*", t.replace("₹", ""))
                if m:
                    market_cap = _num(m.group())
    return pe, market_cap


def _fetch_one(url: str) -> BeautifulSoup | None:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return None
    return BeautifulSoup(resp.text, "html.parser")


MAX_OVERLAP_DIV_PCT = 10.0  # consolidated vs standalone Sales divergence (over the
                            # shared FYs) above which the two are different entities
                            # and a standalone prior-FY may NOT be borrowed.


def _overlap_sales_div_pct(a: dict, b: dict) -> float | None:
    """Max |Sales| % divergence between two fy_series over their shared FYs.
    None when there is no overlapping Sales to compare (cannot verify sameness)."""
    divs = []
    for fy in set(a) & set(b):
        sa, sb = a.get(fy, {}).get("sales"), b.get(fy, {}).get("sales")
        if sa and sb:
            divs.append(abs(sa - sb) / sb * 100)
    return round(max(divs), 1) if divs else None


def fetch_series(scrip: str, ticker: str | None = None, base_fy: int = 2024,
                 lookback: int = 3) -> dict:
    """Fetch the annual P&L series. CONSOLIDATED is always the basis; standalone is
    used only to fill a gap, never to replace consolidated.

    Resolution order:
      1. consolidated spans the full trailing window (has FY-`base_fy` AND
         FY-(`base_fy`-lookback) Sales) -> use consolidated as-is.
      2. consolidated has the base FY but NOT the prior FY (recently-started
         consolidation, e.g. Kalyani: consol FY23->, standalone FY20->):
         borrow ONLY the prior-FY row from standalone, and ONLY IF the two series
         agree over their shared FYs (Sales divergence < MAX_OVERLAP_DIV_PCT) — i.e.
         standalone is the same entity, so its prior FY is a valid proxy. Above the
         threshold the prior FY is left absent -> trailing reports `missing`.
      3. no consolidated at all (company reports only standalone) -> standalone.
      4. else the richest series available.
    Annotates the result with `prior_source` and `overlap_div_pct` so every borrow
    decision is auditable in the run output. `scrip` is the BSE scrip code."""
    out = {"scrip": str(scrip), "basis": None, "url": None, "name": None,
           "fy_series": {}, "pe": None, "market_cap_cr": None,
           "prior_source": None, "overlap_div_pct": None}
    candidates = [
        ("consolidated", f"https://www.screener.in/company/{scrip}/consolidated/"),
        ("standalone",   f"https://www.screener.in/company/{scrip}/"),
    ]
    prior_fy = base_fy - lookback
    parsed = {}
    for basis, url in candidates:
        soup = _fetch_one(url)
        if soup is None:
            continue
        pe, mcap = _top_ratios(soup)
        h1 = soup.find("h1")
        parsed[basis] = {"basis": basis, "url": url,
                         "name": h1.get_text(strip=True) if h1 else None,
                         "fy_series": _parse_pnl(soup), "pe": pe, "market_cap_cr": mcap}
        time.sleep(0.3)

    def _has(cand, fy):
        return cand and cand["fy_series"].get(fy, {}).get("sales") is not None

    con, std = parsed.get("consolidated"), parsed.get("standalone")

    # 1) consolidated already spans the trailing window
    if _has(con, base_fy) and _has(con, prior_fy):
        return {"scrip": str(scrip), "prior_source": "consolidated",
                "overlap_div_pct": None, **con}

    # 2) consolidated has the base FY but not the prior FY -> try to borrow it
    if _has(con, base_fy):
        div = _overlap_sales_div_pct(con["fy_series"], std["fy_series"]) if std else None
        if _has(std, prior_fy) and div is not None and div < MAX_OVERLAP_DIV_PCT:
            merged = dict(con)
            fy_series = dict(con["fy_series"]); fy_series[prior_fy] = std["fy_series"][prior_fy]
            merged["fy_series"] = fy_series
            return {"scrip": str(scrip), "prior_source": "standalone_borrowed",
                    "overlap_div_pct": div, **merged}
        # cannot/should-not borrow -> keep consolidated, prior FY stays absent
        return {"scrip": str(scrip), "prior_source": "consolidated_short",
                "overlap_div_pct": div, **con}

    # 3) no consolidated at all -> standalone is the reported basis
    if _has(std, base_fy):
        return {"scrip": str(scrip), "prior_source": "standalone_only",
                "overlap_div_pct": None, **std}

    # 4) richest available
    rich = max(parsed.values(), key=lambda c: len(c["fy_series"]), default=None)
    if rich:
        return {"scrip": str(scrip), "prior_source": "fallback_richest",
                "overlap_div_pct": None, **rich}
    return out


def _cagr(start, end, years):
    if start is None or end is None or start <= 0 or end <= 0 or years <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 1)


def base_and_trailing(series: dict, base_fy: int = 2024, lookback: int = 3) -> dict:
    """From a fetched series, return the FY-`base_fy` base figures plus the
    trailing PAT/revenue CAGR ending FY`base_fy` (over `lookback` years).
    `trailing_status`: ok | base_pat_nonpositive | missing — so a turnaround
    (loss -> profit, where CAGR math is undefined) is flagged, not silently 0."""
    fy = series.get("fy_series", {})
    base = fy.get(base_fy, {})
    prior = fy.get(base_fy - lookback, {})
    rev0, pat0 = base.get("sales"), base.get("net_profit")
    revp, patp = prior.get("sales"), prior.get("net_profit")

    net_margin = round(pat0 / rev0 * 100, 2) if (rev0 and pat0 is not None and rev0) else None
    pbt = base.get("pbt")
    pbt_margin = round(pbt / rev0 * 100, 2) if (pbt is not None and rev0) else None

    if patp is None or pat0 is None:
        tstatus, trail_pat = "missing", None
    elif patp <= 0:
        tstatus, trail_pat = "base_pat_nonpositive", None
    else:
        tstatus, trail_pat = "ok", _cagr(patp, pat0, lookback)

    return {
        "base_fy": base_fy,
        "current_revenue_cr": rev0,
        "current_pat_cr": pat0,
        "trailing_net_margin_pct": net_margin,
        "current_ebitda_margin_pct": base.get("opm_pct"),
        "current_pbt_margin_pct": pbt_margin,
        "trailing_pat_cagr_pct": trail_pat,
        "trailing_revenue_cagr_pct": _cagr(revp, rev0, lookback),
        "trailing_status": tstatus,
        "lookback_years": lookback,
        "prior_fy": base_fy - lookback,
        "prior_revenue_cr": revp,
        "prior_pat_cr": patp,
    }


if __name__ == "__main__":
    # quick live check on the 6 test companies (scrip codes)
    tests = [
        ("advanced-enzyme", "540025"),
        ("kalyani-cast-tech", "544023"),
        ("patel-engineering", "531120"),
        ("kaynes-technology", "543664"),
        ("mallcom", "539400"),
        ("concor", "531344"),
    ]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for label, scrip in tests:
        if only and only not in label:
            continue
        s = fetch_series(scrip)
        bt = base_and_trailing(s)
        yrs = sorted(s["fy_series"])
        print(f"\n=== {label}  (scrip {scrip})  basis={s['basis']}  name={s['name']}")
        print(f"    FY columns: {yrs}")
        print(f"    FY24 base: rev={bt['current_revenue_cr']}  pat={bt['current_pat_cr']}  "
              f"net_margin={bt['trailing_net_margin_pct']}%  opm={bt['current_ebitda_margin_pct']}%  "
              f"pbt_margin={bt['current_pbt_margin_pct']}%")
        print(f"    trailing PAT CAGR FY{bt['prior_fy']%100:02d}->FY24 "
              f"(pat {bt['prior_pat_cr']} -> {bt['current_pat_cr']}): "
              f"{bt['trailing_pat_cagr_pct']}%  [{bt['trailing_status']}]   "
              f"rev CAGR={bt['trailing_revenue_cagr_pct']}%   P/E={s['pe']}")
