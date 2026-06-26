"""
screener.py — Fetch current financial data from Screener.in.
Publicly accessible, no login required for core P&L data.
URL pattern: https://www.screener.in/company/{TICKER}/consolidated/
"""

import re
import requests
from bs4 import BeautifulSoup

TICKER_MAP = {
    "fineotex_chemical_q4_fy26": "FCL",
    "sandhar_technologies_q4_fy26": "SANDHAR",
    "mold-tek_packaging_q4_fy26": "MOLDTKPAC",
    "asian_paints_q4_fy26": "ASIANPAINT",
    # Add more as needed: "company_stem_lowercase": "TICKER"
}

# Companies where consolidated view lacks recent data — use standalone URL
STANDALONE_OVERRIDES = {
    "MOLDTKPAC",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def _parse_number(text: str) -> float:
    """Parse '₹ 44.6', '17%', '125' → float."""
    clean = re.sub(r"[₹,%\s]", "", text.strip())
    return float(clean) if clean else None


def fetch_screener(company_stem: str) -> dict:
    """
    Fetch key financials for a company from Screener.in.
    company_stem: lowercase PDF stem, e.g. 'fineotex_chemical_q4_fy26'

    Returns dict with:
        ticker, current_revenue_cr, current_pat_cr,
        trailing_net_margin_pct, current_pe, fiscal_year
    """
    ticker = TICKER_MAP.get(company_stem.lower())
    if not ticker:
        raise ValueError(
            f"No ticker found for '{company_stem}'. Add it to TICKER_MAP in screener.py."
        )

    if ticker in STANDALONE_OVERRIDES:
        url = f"https://www.screener.in/company/{ticker}/"
    else:
        url = f"https://www.screener.in/company/{ticker}/consolidated/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Market Cap and P/E from top ratios list ---
    pe = None
    market_cap_cr = None
    ratios_ul = soup.find("ul", {"id": "top-ratios"})
    if ratios_ul:
        for li in ratios_ul.find_all("li"):
            text = li.get_text(separator=" ", strip=True)
            if "Stock P/E" in text:
                parts = text.split()
                pe = float(parts[-1]) if parts else None
            elif "Market Cap" in text:
                # e.g. "Market Cap ₹ 4,807 Cr."
                m = re.search(r"[\d,]+\.?\d*", text.replace("₹", "").replace(",", ""))
                if m:
                    market_cap_cr = float(m.group())

    # --- Annual P&L: Revenue, Net Profit, EBITDA margin, PBT ---
    revenue_cr = None
    pat_cr = None
    pbt_cr = None
    current_ebitda_margin_pct = None
    fiscal_year = None

    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2 or "Profit" not in h2.get_text():
            continue
        table = section.find("table")
        if not table:
            continue

        rows = table.find_all("tr")
        headers_row = rows[0] if rows else None
        if not headers_row:
            continue

        # Get column headers (fiscal years)
        col_headers = [th.get_text(strip=True) for th in headers_row.find_all(["th", "td"])]
        # Last column = most recent year
        last_col_idx = len(col_headers) - 1
        fiscal_year = col_headers[last_col_idx] if col_headers else None

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            if not cells:
                continue
            label = cells[0].replace("+", "").strip()
            val = cells[last_col_idx] if len(cells) > last_col_idx else None

            if label == "Sales" and val:
                try:
                    revenue_cr = float(val.replace(",", ""))
                except ValueError:
                    pass
            elif label == "Net Profit" and val:
                try:
                    pat_cr = float(val.replace(",", ""))
                except ValueError:
                    pass
            elif label == "OPM %" and val:
                try:
                    current_ebitda_margin_pct = float(val.replace("%", "").replace(",", ""))
                except ValueError:
                    pass
            elif label == "Profit before tax" and val:
                try:
                    pbt_cr = float(val.replace(",", ""))
                except ValueError:
                    pass

        break  # first matching section is the annual P&L

    if revenue_cr is None or pat_cr is None:
        raise ValueError(f"Could not parse revenue/PAT from Screener.in for {ticker}")

    trailing_net_margin_pct = round((pat_cr / revenue_cr) * 100, 2) if revenue_cr else None
    current_pbt_margin_pct = round((pbt_cr / revenue_cr) * 100, 2) if (pbt_cr and revenue_cr) else None

    # --- Latest quarter PAT from quarterly results table ---
    latest_quarter_pat_cr = None
    latest_quarter_label = None
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2 or "Quarterly" not in h2.get_text():
            continue
        table = section.find("table")
        if not table:
            continue
        rows = table.find_all("tr")
        col_headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        last_col_idx = len(col_headers) - 1
        latest_quarter_label = col_headers[last_col_idx] if col_headers else None
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            if not cells:
                continue
            if cells[0].replace("+", "").strip() == "Net Profit":
                val = cells[last_col_idx] if len(cells) > last_col_idx else None
                if val:
                    try:
                        latest_quarter_pat_cr = float(val.replace(",", ""))
                    except ValueError:
                        pass
                break
        break

    # Forward PAT = latest quarter PAT × 4 (run-rate annualisation)
    forward_pat_cr = round(latest_quarter_pat_cr * 4, 1) if latest_quarter_pat_cr else None
    forward_pe = round(market_cap_cr / forward_pat_cr, 1) if (market_cap_cr and forward_pat_cr) else None

    return {
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "current_revenue_cr": revenue_cr,
        "current_pat_cr": pat_cr,
        "trailing_net_margin_pct": trailing_net_margin_pct,
        "current_ebitda_margin_pct": current_ebitda_margin_pct,
        "current_pbt_margin_pct": current_pbt_margin_pct,
        "current_pe": pe,
        "market_cap_cr": market_cap_cr,
        "latest_quarter_pat_cr": latest_quarter_pat_cr,
        "latest_quarter_label": latest_quarter_label,
        "forward_pat_cr": forward_pat_cr,
        "forward_pe": forward_pe,
    }


if __name__ == "__main__":
    import sys
    stem = sys.argv[1] if len(sys.argv) > 1 else "fineotex_chemical_q4_fy26"
    data = fetch_screener(stem)
    print(f"\nScreener.in data for {data['ticker']} ({data['fiscal_year']}):")
    print(f"  Revenue:             ₹{data['current_revenue_cr']} Cr")
    print(f"  Annual Net Profit:   ₹{data['current_pat_cr']} Cr")
    print(f"  Net Margin:          {data['trailing_net_margin_pct']}%")
    print(f"  Market Cap:          ₹{data['market_cap_cr']} Cr")
    print(f"  Trailing P/E:        {data['current_pe']}")
    print(f"  Latest Quarter PAT:  ₹{data['latest_quarter_pat_cr']} Cr ({data['latest_quarter_label']})")
    print(f"  Forward PAT (×4):    ₹{data['forward_pat_cr']} Cr")
    print(f"  Forward P/E:         {data['forward_pe']}")
