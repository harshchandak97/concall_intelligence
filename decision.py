#!/usr/bin/env python3
"""
decision.py — Convert extracted guidance into implied PAT CAGR ranked table.
Pure Python, zero LLM. Reads output/*_guidance.json + Screener.in financials.
Outputs output/ranked_table.csv and prints to terminal.

Usage: python decision.py
"""

import json
import csv
import re
from pathlib import Path
from typing import Optional

from screener import fetch_screener, TICKER_MAP

OUTPUT_DIR = Path("output")

# Indian fiscal year starts April 1. A Q4 FY26 call = March/April 2026.
# Call FY is derived per-transcript: primary source is the filename (e.g. ...Q4_FY26),
# cross-checked against the call_period the LLM emits from the transcript header.
DEFAULT_CALL_FY = 2026  # last-resort fallback only — used (with a warning) if neither source parses


def call_period_to_fy(period: Optional[str]) -> Optional[int]:
    """'Q4 FY26', 'Q4_FY26', or 'FY26' → 2026 (the fiscal year the call reports)."""
    if not period:
        return None
    m = re.search(r"FY\s*(\d{2,4})", period, re.IGNORECASE)
    if not m:
        return None
    yr = int(m.group(1))
    return yr if yr > 100 else 2000 + yr


def fy_to_year(fy_str: str) -> Optional[int]:
    """'FY27' or 'FY2027' → 2027"""
    m = re.search(r"(\d{2,4})$", fy_str.strip())
    if not m:
        return None
    yr = int(m.group(1))
    return yr if yr > 100 else (2000 + yr)


def parse_fy_range(timeline: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parse fiscal year or range from timeline string.
    'FY27' → (2027, 2027)
    'FY28-FY29' or 'FY28-29' → (2028, 2029)
    'H1 FY27' or 'Q2 FY27' → (2027, 2027)
    Returns (fy_low, fy_high) — fy_low is the earlier year (conservative/base uses more years).
    """
    # Remove sub-year markers (H1, Q2, etc.) — treat as the full fiscal year for simplicity
    cleaned = re.sub(r"\b(H[12]|Q[1-4])\s*", "", timeline, flags=re.IGNORECASE).strip()

    # Range: FY28-FY29 or FY28-29
    range_match = re.search(r"FY\s*(\d{2,4})\s*[-–]\s*(?:FY\s*)?(\d{2,4})", cleaned, re.IGNORECASE)
    if range_match:
        a = int(range_match.group(1))
        b = int(range_match.group(2))
        a = a if a > 100 else 2000 + a
        b = b if b > 100 else 2000 + b
        return (min(a, b), max(a, b))

    # Single FY
    fy = fy_to_year(cleaned)
    if fy:
        return (fy, fy)

    return (None, None)


def sub_year_offset(timeline: str) -> float:
    """
    Years to subtract from the FY-end-based count for sub-year markers.
    A fiscal year ends in March. 'H1 FYn' lands mid-year, 'Q2 FYn' mid-year, etc.
    """
    t = timeline.upper()
    if "H1" in t:
        return 0.5
    if "H2" in t:
        return 0.0
    if "Q1" in t:
        return 0.75
    if "Q2" in t:
        return 0.5
    if "Q3" in t:
        return 0.25
    if "Q4" in t:
        return 0.0
    return 0.0


YEARS_FLOOR = 0.25  # avoid div-by-zero / explosive CAGR for same-FY guidance


def years_from_fy(fy: int, call_fy: int, timeline: str = "") -> float:
    """
    FY27 from a FY26 call → 1.0 year. 'H1 FY27' → 0.5 year.
    Floored at YEARS_FLOOR so current-FY guidance isn't silently dropped.
    """
    yrs = float(fy - call_fy) - sub_year_offset(timeline)
    return max(yrs, YEARS_FLOOR)


def guided_net_margin_equiv(margin_item: dict, screener: dict) -> Optional[float]:
    """
    Convert a guided EBITDA or PBT margin into a NET-margin equivalent (fraction).

    Spec requires Future PAT = Revenue x NET margin, but management almost always
    guides EBITDA (or sometimes PBT) margin. We hold the company's current
    below-the-line conversion ratio (net/EBITDA or net/PBT) constant and apply the
    guided margin expansion proportionally to the trailing net margin.
    No fabrication: only the ratio already implied by reported financials is used.
    """
    _, guided_hi = parse_bounds(margin_item["guidance_value"])
    if guided_hi is None:
        return None
    trailing_net = screener["trailing_net_margin_pct"]
    metric = margin_item["metric"]

    if metric == "ebitda_margin_pct":
        current_basis = screener.get("current_ebitda_margin_pct")
    elif metric == "pbt_margin_pct":
        current_basis = screener.get("current_pbt_margin_pct")
    else:
        current_basis = None

    if not current_basis or not trailing_net:
        # Can't convert safely — fall back to trailing net margin (no uplift)
        return trailing_net / 100

    net_equiv_pct = trailing_net * (guided_hi / current_basis)
    # Bull margin should never fall below the trailing net margin (Base floor)
    return max(net_equiv_pct, trailing_net) / 100


def parse_bounds(guidance_value: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    '18-20' → (18.0, 20.0)
    '500' or '3,000' → (500.0, 3000.0)
    None → (None, None)
    """
    if not guidance_value:
        return (None, None)
    clean = guidance_value.strip().replace(",", "")
    # Range
    m = re.match(r"^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)$", clean)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    # Single number
    m = re.match(r"^(\d+(?:\.\d+)?)$", clean)
    if m:
        v = float(m.group(1))
        return (v, v)
    return (None, None)


def compute_cagr(future_pat: float, current_pat: float, years: float) -> Optional[float]:
    if years <= 0 or current_pat <= 0 or future_pat <= 0:
        return None
    return round(((future_pat / current_pat) ** (1.0 / years) - 1) * 100, 1)


def dedup_items(items: list[dict]) -> list[dict]:
    """Collapse items that repeat the same (metric, value, timeline) — the same number
    stated more than once in the call. Keeps first appearance (deterministic)."""
    seen = set()
    out = []
    for i in items:
        key = (i["metric"], i.get("guidance_value"), i.get("timeline"))
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


def _is_full_year(timeline: Optional[str]) -> bool:
    """True for a bare fiscal year ('FY27', 'FY28-FY29'); False for a sub-period (H1/Q2 FY27)."""
    return bool(timeline) and not re.search(r"\b(H[12]|Q[1-4])\b", timeline, re.IGNORECASE)


def _magnitude(item: dict) -> float:
    """Upper bound of the guidance value, for the 'largest headline number' tiebreak."""
    lo, hi = parse_bounds(item.get("guidance_value"))
    return hi if hi is not None else (lo if lo is not None else -1.0)


def _rank_same_metric(items: list[dict]) -> list[dict]:
    """Driver-selection ladder among candidates of one metric:
    full-year timeline first, then largest magnitude, then latest page/mention."""
    return sorted(
        items,
        key=lambda i: (_is_full_year(i.get("timeline")), _magnitude(i), i.get("page_number", 0)),
        reverse=True,
    )


def _ranked_by_class(items: list[dict], preferred: str, fallback: str) -> list[dict]:
    """Dedup, then order so the preferred metric (e.g. *_absolute) leads, each class ranked
    internally. [0] is the CAGR driver; the rest are auditable alternatives."""
    deduped = dedup_items([i for i in items if i["metric"] in (preferred, fallback)])
    pref = _rank_same_metric([i for i in deduped if i["metric"] == preferred])
    fall = _rank_same_metric([i for i in deduped if i["metric"] == fallback])
    return pref + fall


def ranked_revenue_items(items: list[dict]) -> list[dict]:
    return _ranked_by_class(items, "revenue_absolute", "revenue_growth_pct")


def ranked_margin_items(items: list[dict]) -> list[dict]:
    return _ranked_by_class(items, "ebitda_margin_pct", "pbt_margin_pct")


def ranked_pat_items(items: list[dict]) -> list[dict]:
    return _ranked_by_class(items, "pat_absolute", "pat_growth_pct")


def _short_item(item: dict) -> str:
    """Compact 'metric = value unit | timeline' label for an item."""
    val = item.get("guidance_value") or "—"
    unit = item.get("guidance_unit") or ""
    currency = item.get("currency") or ""
    tl = item.get("timeline") or "—"
    return f"{item['metric']} = {val} {unit} {currency} | {tl}".replace("  ", " ").strip()


def format_basis(
    item: dict,
    years_base: float,
    years_bull: float,
    margin_item: Optional[dict] = None,
    alternatives: Optional[list[dict]] = None,
) -> str:
    """One-line summary of what drove the CAGR, plus any same-metric candidates not used."""
    yrs = f"{years_base:.1f}yr base" if years_base == years_bull else f"{years_base:.1f}yr base / {years_bull:.1f}yr bull"
    basis = f"{_short_item(item)} | {yrs}"
    if margin_item:
        m_val = margin_item.get("guidance_value") or "—"
        m_unit = margin_item.get("guidance_unit") or ""
        basis += f" + {margin_item['metric']} = {m_val} {m_unit} (bull margin)"
    if alternatives:
        alts = "; ".join(_short_item(a) for a in alternatives)
        basis += f" || alternatives not used: {alts}"
    return basis


def compute_block_cagr(
    block_items: list[dict],
    screener: dict,
    call_fy: int,
) -> tuple[Optional[float], Optional[float], str, str]:
    """
    Compute (base_cagr, bull_cagr, basis, passage) for a horizon block.

    Strategy (in order of preference):
    1. Direct PAT guidance (absolute) → use directly
    2. PAT growth% guidance → apply to current_pat
    3. Revenue guidance + margin → Future PAT = revenue × margin
    4. Revenue guidance only → proxy using revenue CAGR as PAT CAGR estimate
    """
    current_pat = screener["current_pat_cr"]
    current_revenue = screener["current_revenue_cr"]
    trailing_margin = screener["trailing_net_margin_pct"] / 100  # fraction

    # Deduped, ranked candidates per metric class. [0] is the driver; the rest are
    # surfaced in the basis column as auditable alternatives.
    pat_items = ranked_pat_items(block_items)
    pat_item = pat_items[0] if pat_items else None
    pat_alts = pat_items[1:]

    # --- Option 1: Direct PAT absolute ---
    if pat_item and pat_item["metric"] == "pat_absolute":
        lo, hi = parse_bounds(pat_item["guidance_value"])
        fy_lo, fy_hi = parse_fy_range(pat_item["timeline"])
        if lo is not None and fy_lo is not None:
            tl = pat_item["timeline"]
            years_base = years_from_fy(fy_hi, call_fy, tl)
            years_bull = years_from_fy(fy_lo, call_fy, tl)
            base = compute_cagr(lo, current_pat, years_base)
            bull = compute_cagr(hi if hi else lo, current_pat, years_bull)
            if base is not None:
                return base, bull, format_basis(pat_item, years_base, years_bull, alternatives=pat_alts), pat_item["passage"]

    # --- Option 2: PAT growth% ---
    if pat_item and pat_item["metric"] == "pat_growth_pct":
        lo_pct, hi_pct = parse_bounds(pat_item["guidance_value"])
        fy_lo, fy_hi = parse_fy_range(pat_item["timeline"])
        if lo_pct is not None and fy_lo is not None:
            tl = pat_item["timeline"]
            years_base = years_from_fy(fy_hi, call_fy, tl)
            years_bull = years_from_fy(fy_lo, call_fy, tl)
            future_pat_base = current_pat * (1 + lo_pct / 100) ** years_base
            future_pat_bull = current_pat * (1 + (hi_pct or lo_pct) / 100) ** years_bull
            base = compute_cagr(future_pat_base, current_pat, years_base)
            bull = compute_cagr(future_pat_bull, current_pat, years_bull)
            if base is not None:
                return base, bull, format_basis(pat_item, years_base, years_bull, alternatives=pat_alts), pat_item["passage"]

    # --- Option 3: Revenue + margin ---
    rev_items = ranked_revenue_items(block_items)
    rev_item = rev_items[0] if rev_items else None
    rev_alts = rev_items[1:]
    margin_items = ranked_margin_items(block_items)
    margin_item = margin_items[0] if margin_items else None

    if rev_item:
        rev_lo, rev_hi = parse_bounds(rev_item["guidance_value"])
        fy_lo, fy_hi = parse_fy_range(rev_item["timeline"])

        if rev_lo is not None and fy_lo is not None:
            tl = rev_item["timeline"]
            years_base = years_from_fy(fy_hi, call_fy, tl)
            years_bull = years_from_fy(fy_lo, call_fy, tl)

            if rev_item["metric"] == "revenue_growth_pct":
                unit = (rev_item.get("guidance_unit") or "").lower().strip()
                if unit == "times":
                    rev_lo_abs = current_revenue * rev_lo
                    rev_hi_abs = current_revenue * (rev_hi if rev_hi else rev_lo)
                else:
                    rev_lo_abs = current_revenue * (1 + rev_lo / 100) ** years_base
                    rev_hi_abs = current_revenue * (1 + (rev_hi if rev_hi else rev_lo) / 100) ** years_bull
                rev_lo, rev_hi = rev_lo_abs, rev_hi_abs

            rev_hi = rev_hi if rev_hi else rev_lo

            if margin_item:
                bull_margin = guided_net_margin_equiv(margin_item, screener)
                if bull_margin is None:
                    bull_margin = trailing_margin
            else:
                bull_margin = trailing_margin

            future_pat_base = rev_lo * trailing_margin
            future_pat_bull = rev_hi * max(bull_margin, trailing_margin)

            base = compute_cagr(future_pat_base, current_pat, years_base)
            bull = compute_cagr(future_pat_bull, current_pat, years_bull)

            if base is not None:
                passage = rev_item["passage"]
                if margin_item:
                    passage += "\n---\n" + margin_item["passage"]
                return base, bull, format_basis(rev_item, years_base, years_bull, margin_item if margin_item else None, alternatives=rev_alts), passage

    return None, None, "", ""


def process_company(guidance_path: Path, screener: dict, filename_call_fy: Optional[int]) -> dict:
    with open(guidance_path) as f:
        data = json.load(f)

    # Resolve the call fiscal year: filename is primary (deterministic), the LLM-emitted
    # call_period is a cross-check. Warn loudly on disagreement rather than computing silently.
    llm_call_fy = call_period_to_fy(data.get("call_period"))
    call_fy = filename_call_fy or llm_call_fy or DEFAULT_CALL_FY
    if filename_call_fy and llm_call_fy and filename_call_fy != llm_call_fy:
        print(f"  [WARN] call-period mismatch for {guidance_path.stem}: "
              f"filename=FY{filename_call_fy % 100:02d} vs LLM='{data.get('call_period')}' "
              f"(FY{llm_call_fy % 100:02d}). Using filename FY{call_fy % 100:02d}.")
    elif filename_call_fy is None and llm_call_fy is None:
        print(f"  [WARN] no call period from filename or LLM for {guidance_path.stem}; "
              f"falling back to default FY{DEFAULT_CALL_FY % 100:02d}.")

    items = data.get("items", [])

    # Only company-level items feed the CAGR
    company_items = [i for i in items if i["level"] == "company"]
    other_items = [i for i in items if i["level"] != "company"]

    near_items = [i for i in company_items if i["horizon"] == "near"]
    long_items = [i for i in company_items if i["horizon"] in ("medium", "long")]

    near_base, near_bull, near_basis, near_passage = compute_block_cagr(near_items, screener, call_fy)
    long_base, long_bull, long_basis, long_passage = compute_block_cagr(long_items, screener, call_fy)

    # Other signals: all non-company-level items as short bullets
    signals = []
    for i in other_items:
        unit = i.get("guidance_unit") or ""
        currency = i.get("currency") or ""
        val = i.get("guidance_value") or ""
        metric = i.get("metric", "")
        tl = i.get("timeline", "")
        level = i.get("level", "")
        prefix = f"[{level}] " if level != "company" else ""
        if val:
            signals.append(f"{prefix}{metric}: {val} {unit} {currency} by {tl}".strip())
        else:
            signals.append(f"{prefix}{metric} by {tl}".strip())

    best = max((v for v in [near_base, long_base] if v is not None), default=None)
    forward_pe = screener.get("forward_pe")
    forward_peg = round(forward_pe / best, 2) if (forward_pe and best) else None

    return {
        "company": guidance_path.stem.replace("_guidance", ""),
        "near_cagr_base": near_base,
        "near_cagr_bull": near_bull,
        "near_cagr_basis": near_basis,
        "near_cagr_passage": near_passage,
        "long_cagr_base": long_base,
        "long_cagr_bull": long_bull,
        "long_cagr_basis": long_basis,
        "long_cagr_passage": long_passage,
        "forward_pe": forward_pe,
        "forward_peg": forward_peg,
        "other_signals": " | ".join(signals),
    }


def fmt(val: Optional[float]) -> str:
    return f"{val:.1f}%" if val is not None else "—"


def main():
    guidance_files = sorted(OUTPUT_DIR.glob("*_guidance.json"))
    if not guidance_files:
        print("No guidance JSON files found in output/. Run run.py first.")
        return

    rows = []
    for gf in guidance_files:
        stem = gf.stem.replace("_guidance", "").lower()
        if stem not in TICKER_MAP:
            print(f"[SKIP] {stem} — not in TICKER_MAP in screener.py")
            continue
        print(f"Processing {stem}...")
        try:
            screener = fetch_screener(stem)
        except Exception as e:
            print(f"  [ERROR] Screener fetch failed: {e}")
            continue

        filename_call_fy = call_period_to_fy(stem)  # reads the FY token from e.g. ...q4_fy26
        row = process_company(gf, screener, filename_call_fy)
        rows.append(row)

    if not rows:
        print("No companies processed.")
        return

    # Sort by Forward PEG ascending (lower = better value), nulls last
    rows.sort(key=lambda r: (r["forward_peg"] is None, r["forward_peg"] or 0))

    # Write CSV
    out_csv = OUTPUT_DIR / "ranked_table.csv"
    fieldnames = ["company",
                  "near_cagr_base", "near_cagr_bull", "near_cagr_basis", "near_cagr_passage",
                  "long_cagr_base", "long_cagr_bull", "long_cagr_basis", "long_cagr_passage",
                  "forward_pe", "forward_peg", "other_signals"]
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print table
    print(f"\n{'='*110}")
    print(f"{'COMPANY':<35} {'NEAR CAGR':>14} {'LONG CAGR':>14} {'FWD P/E':>8} {'FWD PEG':>8}")
    print(f"{'':35} {'Base / Bull':>14} {'Base / Bull':>14} {'(Q4×4)':>8} {'↓ lower=better':>8}")
    print(f"{'='*110}")
    for r in rows:
        near = f"{fmt(r['near_cagr_base'])} / {fmt(r['near_cagr_bull'])}"
        long_ = f"{fmt(r['long_cagr_base'])} / {fmt(r['long_cagr_bull'])}"
        fpe = f"{r['forward_pe']:.1f}x" if r["forward_pe"] else "—"
        peg = f"{r['forward_peg']:.2f}" if r["forward_peg"] else "—"
        print(f"{r['company']:<35} {near:>14} {long_:>14} {fpe:>8} {peg:>8}")

    print(f"\nRanked table saved to: {out_csv}")
    print(f"\nOther Signals (segment/geo/binary guidance):")
    for r in rows:
        if r["other_signals"]:
            print(f"  {r['company']}: {r['other_signals'][:120]}")


if __name__ == "__main__":
    main()
