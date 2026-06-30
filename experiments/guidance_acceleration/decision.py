#!/usr/bin/env python3
"""decision.py — forward PAT-CAGR cascade for the guidance-acceleration experiment.

Ported from the repo-root decision.py (compute_block_cagr), with three changes so
it runs self-contained in this experiment:
  * field names match the experiment schema — `value`/`unit`/`scope` (not the
    repo's guidance_value/guidance_unit/level);
  * `horizon` is DERIVED here from `timeline` + the call FY (Step 2 of the plan),
    since the cheap extractor doesn't emit it;
  * the Screener base comes from lib_screener (FY24-anchored), keyed exactly as the
    cascade expects (current_revenue_cr, current_pat_cr, trailing_net_margin_pct,
    current_ebitda_margin_pct, current_pbt_margin_pct).

The cascade itself (the four-option PAT bridge) is unchanged in spirit — Python
does ALL arithmetic, the LLM never does.
"""
from __future__ import annotations
import re
from typing import Optional

YEARS_FLOOR = 0.25  # avoid div-by-zero / explosive CAGR for same-FY guidance
MAX_PLAUSIBLE_REV_CAGR = 1.00  # an absolute "revenue" target implying >100%/yr is
                               # almost always a mislabelled order-book/AUM/capex figure


# ----------------------------------------------------------- timeline parsing
def fy_to_year(fy_str: str) -> Optional[int]:
    m = re.search(r"(\d{2,4})$", (fy_str or "").strip())
    if not m:
        return None
    yr = int(m.group(1))
    return yr if yr > 100 else 2000 + yr


def parse_fy_range(timeline: str) -> tuple[Optional[int], Optional[int]]:
    """'FY27'->(2027,2027); 'FY28-FY29'/'FY28-29'->(2028,2029); 'H1 FY27'->(2027,2027)."""
    cleaned = re.sub(r"\b(H[12]|Q[1-4])\s*", "", timeline or "", flags=re.IGNORECASE).strip()
    rng = re.search(r"FY\s*(\d{2,4})\s*[-–]\s*(?:FY\s*)?(\d{2,4})", cleaned, re.IGNORECASE)
    if rng:
        a, b = int(rng.group(1)), int(rng.group(2))
        a = a if a > 100 else 2000 + a
        b = b if b > 100 else 2000 + b
        return (min(a, b), max(a, b))
    fy = fy_to_year(cleaned)
    return (fy, fy) if fy else (None, None)


def sub_year_offset(timeline: str) -> float:
    t = (timeline or "").upper()
    return {"H1": 0.5, "H2": 0.0, "Q1": 0.75, "Q2": 0.5, "Q3": 0.25, "Q4": 0.0}.get(
        next((k for k in ("H1", "H2", "Q1", "Q2", "Q3", "Q4") if k in t), ""), 0.0)


def years_from_fy(fy: int, call_fy: int, timeline: str = "") -> float:
    return max(float(fy - call_fy) - sub_year_offset(timeline), YEARS_FLOOR)


def derive_horizon(timeline: str, call_fy: int) -> str:
    """Step 2: near (<=1Y) | medium (~2Y) | long (3Y+), from the timeline's latest
    FY vs the call FY. Undated/unparseable timelines default to 'near' (treated as
    next-FY guidance) so they still feed the near block rather than vanish."""
    _, fy_hi = parse_fy_range(timeline)
    if fy_hi is None:
        return "near"
    dy = fy_hi - call_fy
    if dy <= 1:
        return "near"
    if dy == 2:
        return "medium"
    return "long"


# ----------------------------------------------------------- value parsing
def parse_bounds(value: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """'18-20'->(18,20); '500'/'3,000'->(500,500)/(3000,3000); None->(None,None)."""
    if not value:
        return (None, None)
    clean = str(value).strip().replace(",", "").replace("–", "-").replace("x", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", clean)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.match(r"^(\d+(?:\.\d+)?)$", clean)
    if m:
        v = float(m.group(1))
        return (v, v)
    return (None, None)


DEFAULT_USDINR = 83.4  # only used when no call-date rate is supplied (tests)


def to_crore(value: float, unit: Optional[str], currency: Optional[str],
             usdinr: float = DEFAULT_USDINR) -> Optional[float]:
    """Absolute money target -> ₹ crore, using the call-date USD/INR (`usdinr`).
    The extractor keeps the number next to the unit verbatim ('$1 billion' ->
    value=1, unit='billion', currency='USD'), so the cascade MUST convert before
    using it as a ₹-crore revenue/PAT figure. Without this, '$1bn' is read as ₹1cr
    (the Kaynes bug). FX comes from lib_fx.usdinr_on(concall_date), not a constant."""
    if value is None:
        return None
    u = (unit or "").lower().strip().rstrip(".").replace("mn", "million").replace("bn", "billion")
    # normalise plurals the extractor emits inconsistently (crores/lakhs/millions)
    u = {"crores": "crore", "crs": "crore", "lakhs": "lakh",
         "millions": "million", "billions": "billion"}.get(u, u)
    usd = (currency or "").upper() == "USD"
    if u in ("crore", "cr"):
        return value * (usdinr if usd else 1)          # ₹1cr ; $1cr non-idiomatic but handle
    if u == "lakh":
        return value * (usdinr * 0.01 if usd else 0.01)
    if u == "million":
        return value * (usdinr / 10 if usd else 0.1)   # $1m=usdinr/10 cr ; ₹1m=₹0.1cr
    if u == "billion":
        return value * (usdinr * 100 if usd else 100)  # $1bn=usdinr*100 cr ; ₹1bn=₹100cr
    return value if u in ("", "%", "times") else None  # bare/percent handled elsewhere


def compute_cagr(future_pat: float, current_pat: float, years: float) -> Optional[float]:
    if years <= 0 or current_pat <= 0 or future_pat <= 0:
        return None
    return round(((future_pat / current_pat) ** (1.0 / years) - 1) * 100, 1)


def guided_net_margin_equiv(margin_item: dict, screener: dict) -> Optional[float]:
    """Guided EBITDA/PBT margin -> NET-margin-equivalent fraction, holding the
    company's current below-the-line conversion ratio constant (no fabrication)."""
    _, guided_hi = parse_bounds(margin_item.get("value"))
    if guided_hi is None:
        return None
    trailing_net = screener.get("trailing_net_margin_pct")
    metric = margin_item["metric"]
    if metric == "ebitda_margin_pct":
        current_basis = screener.get("current_ebitda_margin_pct")
    elif metric == "pbt_margin_pct":
        current_basis = screener.get("current_pbt_margin_pct")
    else:
        current_basis = None
    if not current_basis or not trailing_net:
        return trailing_net / 100 if trailing_net else None
    net_equiv_pct = trailing_net * (guided_hi / current_basis)
    return max(net_equiv_pct, trailing_net) / 100


# ----------------------------------------------------------- driver selection
def dedup_items(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for i in items:
        key = (i["metric"], i.get("value"), i.get("timeline"))
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


def _is_full_year(timeline: Optional[str]) -> bool:
    return bool(timeline) and not re.search(r"\b(H[12]|Q[1-4])\b", timeline, re.IGNORECASE)


def _magnitude(item: dict) -> float:
    lo, hi = parse_bounds(item.get("value"))
    return hi if hi is not None else (lo if lo is not None else -1.0)


def _rank_same_metric(items: list[dict]) -> list[dict]:
    # full-year timeline first, then largest magnitude (stable for ties)
    return sorted(items, key=lambda i: (_is_full_year(i.get("timeline")), _magnitude(i)),
                  reverse=True)


def _ranked_by_class(items: list[dict], preferred: str, fallback: str) -> list[dict]:
    deduped = dedup_items([i for i in items if i["metric"] in (preferred, fallback)])
    pref = _rank_same_metric([i for i in deduped if i["metric"] == preferred])
    fall = _rank_same_metric([i for i in deduped if i["metric"] == fallback])
    return pref + fall


def ranked_revenue_items(items): return _ranked_by_class(items, "revenue_absolute", "revenue_growth_pct")
def ranked_margin_items(items):  return _ranked_by_class(items, "ebitda_margin_pct", "pbt_margin_pct")
def ranked_pat_items(items):     return _ranked_by_class(items, "pat_absolute", "pat_growth_pct")


def _short(item: dict) -> str:
    return (f"{item['metric']} = {item.get('value') or '—'} {item.get('unit') or ''} "
            f"{item.get('currency') or ''} | {item.get('timeline') or '—'}").replace("  ", " ").strip()


# ----------------------------------------------------------- the cascade
def compute_block_cagr(block_items: list[dict], screener: dict, call_fy: int,
                       usdinr: float = DEFAULT_USDINR):
    """(base_cagr, bull_cagr, basis, passage) for one horizon block.
    Cascade: pat_absolute -> pat_growth_pct -> revenue+margin -> revenue-only.
    Base = lower bound x trailing net margin; Bull = upper bound x guided margin.
    `usdinr` is the call-date FX used to convert any foreign-currency absolute target."""
    current_pat = screener.get("current_pat_cr")
    current_revenue = screener.get("current_revenue_cr")
    tn = screener.get("trailing_net_margin_pct")
    if not current_pat or not current_revenue or tn is None or current_pat <= 0:
        return None, None, "", ""  # turnaround/missing base — cascade can't run
    trailing_margin = tn / 100

    pat_items = ranked_pat_items(block_items)
    pat_item = pat_items[0] if pat_items else None

    # --- Option 1: direct PAT absolute ---
    if pat_item and pat_item["metric"] == "pat_absolute":
        lo, hi = parse_bounds(pat_item.get("value"))
        lo = to_crore(lo, pat_item.get("unit"), pat_item.get("currency"), usdinr)
        hi = to_crore(hi, pat_item.get("unit"), pat_item.get("currency"), usdinr)
        fy_lo, fy_hi = parse_fy_range(pat_item.get("timeline"))
        if lo is not None and fy_lo is not None:
            tl = pat_item.get("timeline")
            yb, yu = years_from_fy(fy_hi, call_fy, tl), years_from_fy(fy_lo, call_fy, tl)
            base = compute_cagr(lo, current_pat, yb)
            bull = compute_cagr(hi or lo, current_pat, yu)
            if base is not None:
                return base, bull, _short(pat_item), pat_item.get("passage", "")

    # --- Option 2: PAT growth% ---
    if pat_item and pat_item["metric"] == "pat_growth_pct":
        lo, hi = parse_bounds(pat_item.get("value"))
        fy_lo, fy_hi = parse_fy_range(pat_item.get("timeline"))
        if lo is not None and fy_lo is not None:
            tl = pat_item.get("timeline")
            yb, yu = years_from_fy(fy_hi, call_fy, tl), years_from_fy(fy_lo, call_fy, tl)
            fb = current_pat * (1 + lo / 100) ** yb
            fu = current_pat * (1 + (hi or lo) / 100) ** yu
            base, bull = compute_cagr(fb, current_pat, yb), compute_cagr(fu, current_pat, yu)
            if base is not None:
                return base, bull, _short(pat_item), pat_item.get("passage", "")

    # --- Option 3/4: revenue (+margin) ---
    rev_items = ranked_revenue_items(block_items)
    margin_items = ranked_margin_items(block_items)
    margin_item = margin_items[0] if margin_items else None

    # Iterate ranked revenue candidates so an implausible absolute target (an
    # order-book / AUM / capex figure mislabelled as revenue, e.g. ₹25,000cr vs
    # ₹4,500cr current = ~450%/yr) is SKIPPED and falls through to the next
    # candidate (typically a revenue_growth_pct). Generalises without test-fitting.
    for rev_item in rev_items:
        v_lo, v_hi = parse_bounds(rev_item.get("value"))
        fy_lo, fy_hi = parse_fy_range(rev_item.get("timeline"))
        if v_lo is None or fy_lo is None:
            continue
        tl = rev_item.get("timeline")
        yb, yu = years_from_fy(fy_hi, call_fy, tl), years_from_fy(fy_lo, call_fy, tl)
        v_hi = v_hi or v_lo
        if rev_item["metric"] == "revenue_absolute":
            rev_lo = to_crore(v_lo, rev_item.get("unit"), rev_item.get("currency"), usdinr)
            rev_hi = to_crore(v_hi, rev_item.get("unit"), rev_item.get("currency"), usdinr)
            if rev_lo is None:  # unrecognised unit — can't use this candidate
                continue
            implied = (rev_lo / current_revenue) ** (1 / yb) - 1
            if implied > MAX_PLAUSIBLE_REV_CAGR:  # likely a mislabelled big number
                continue
        else:  # revenue_growth_pct — a % rate or a multiple
            unit = (rev_item.get("unit") or "").lower().strip()
            if unit in ("times", "x", "multiple", "fold"):
                rev_lo, rev_hi = current_revenue * v_lo, current_revenue * v_hi
            else:
                rev_lo = current_revenue * (1 + v_lo / 100) ** yb
                rev_hi = current_revenue * (1 + v_hi / 100) ** yu
        bull_margin = guided_net_margin_equiv(margin_item, screener) if margin_item else None
        bull_margin = bull_margin or trailing_margin
        fb = rev_lo * trailing_margin
        fu = rev_hi * max(bull_margin, trailing_margin)
        base, bull = compute_cagr(fb, current_pat, yb), compute_cagr(fu, current_pat, yu)
        if base is not None:
            basis = _short(rev_item) + (f" + {_short(margin_item)} (bull margin)" if margin_item else "")
            passage = rev_item.get("passage", "")
            if margin_item:
                passage += "\n---\n" + margin_item.get("passage", "")
            return base, bull, basis, passage

    return None, None, "", ""
