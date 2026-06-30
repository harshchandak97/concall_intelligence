#!/usr/bin/env python3
"""forward_growth.py — deterministic 4-field -> implied annual growth (no LLM).

Turns one extracted target {metric, value, unit, timeframe} into an implied
annual growth rate (a fraction, e.g. 0.26 = 26%). The LLM only read the words;
ALL arithmetic is here. Shared by the step-3 gate (validate_extraction.py) and
the later step-5 score.py.

Call baseline is Q4 FY24 (the call was ~April–May 2024, i.e. inside FY24), so a
"FY27" target is ~3 years out.

Returns a dict:
  {"status": "ok",         "low": float, "high": float}  # annualised, fraction
  {"status": "needs_base"}        # absolute ₹ target — needs current revenue (step 5)
  {"status": "none"}              # metric == "none" / no target
  {"status": "unparseable", "reason": str}

For ranking, use `rank_key(item)`: returns the lower-bound growth (`low`) for
ok items, and -inf for none/needs_base/unparseable so they sink out of the top.
"""
from __future__ import annotations
import math
import re

CALL_FY = 24  # FY24 baseline (call held ~May 2024)

USDINR = 83          # rough USD->INR, only for the sanity magnitude check
ABSURD_CRORE = 500_000  # a revenue target above ~₹5 lakh crore in this sub-₹50k-cr-mcap
                        # universe is almost certainly a mis-parse (e.g. "$1bn" read as
                        # "1000 billion"). Flag it rather than feed garbage downstream.

_WORDNUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _floats(value: str) -> tuple[float, float] | None:
    """'2'->(2,2); '3-4'->(3,4); '18-20'->(18,20); '1,000'->(1000,1000)."""
    s = str(value).strip().replace(",", "").replace("–", "-").replace("x", "")
    parts = [p for p in s.split("-") if p.strip()]
    try:
        nums = sorted(float(p) for p in parts)
    except ValueError:
        return None
    if not nums:
        return None
    return nums[0], nums[-1]


def _years(timeframe: str) -> tuple[float, float] | None:
    """Horizon -> (years_min, years_max) from the FY24 call baseline.

    Handles 'FY27'/'2026-27', 'by FY29-FY30', 'next year', 'in 3 years',
    'over the next three to four years', 'in 2-3 years'."""
    if not timeframe:
        return None
    t = timeframe.lower().replace("–", "-")

    # explicit fiscal years -> horizon = FY - 24 (each, so a range yields a range)
    fys = [int(m) for m in re.findall(r"fy\s*'?(\d{2})\b", t)]
    # also catch 4-digit fiscal years: 'FY2027' / '2027'
    for m in re.findall(r"\b(20\d{2})\b", t):
        fys.append(int(m) % 100)
    if fys:
        horizons = [max(0.5, fy - CALL_FY) for fy in fys]
        return min(horizons), max(horizons)

    if "next year" in t or "next fiscal" in t or "coming year" in t:
        return 1.0, 1.0

    # numeric years: digits or number-words, optionally a range
    nums: list[float] = [float(x) for x in re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:year|yr)", t)]
    if not nums:
        # word numbers near 'year(s)'  e.g. 'three to four years'
        words = re.findall(r"\b(" + "|".join(_WORDNUM) + r")\b", t)
        if words and ("year" in t or "yr" in t):
            nums = [float(_WORDNUM[w]) for w in words]
    # also a bare range like 'in 2-3 years' -> both endpoints captured above as
    # separate digit matches only if both precede 'years'; handle '2-3 years':
    if not nums:
        rng = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(?:year|yr)", t)
        if rng:
            nums = [float(rng.group(1)), float(rng.group(2))]
    if nums:
        return min(nums), max(nums)
    return None


def _approx_crore(value: float, unit: str, currency: str) -> float | None:
    """Rough ₹-crore magnitude of an absolute money target, for the sanity check
    only (NOT used for the real CAGR — that uses the Screener base in step 5)."""
    u = unit.lower().replace("mn", "million").replace("bn", "billion")
    usd = (currency or "").upper() == "USD"
    if u in ("crore", "cr"):
        return value                              # Indian unit -> already crore
    if u == "lakh":
        return value * 0.01
    if u == "million":
        return value * (USDINR / 10 if usd else 0.1)   # $1m=₹8.3cr ; ₹1m=₹0.1cr
    if u == "billion":
        return value * (USDINR * 100 if usd else 100)  # $1bn=₹8300cr ; ₹1bn=₹100cr
    return None


def forward_growth(item: dict) -> dict:
    """Implied annual growth for one extracted target. See module docstring."""
    metric = (item.get("metric") or "none").strip().lower()
    if metric in ("none", "", None):
        return {"status": "none"}

    unit = (item.get("unit") or "").strip().lower()
    vals = _floats(item.get("value"))
    if vals is None:
        return {"status": "unparseable", "reason": f"value={item.get('value')!r}"}
    v_low, v_high = vals

    # Percentage growth is already an annual rate — timeframe doesn't annualise it.
    if unit in ("%", "percent", "pct"):
        return {"status": "ok", "low": v_low / 100.0, "high": v_high / 100.0}

    # Multiples must be annualised over the horizon.
    if unit in ("times", "x", "multiple", "fold"):
        yrs = _years(item.get("timeframe"))
        if yrs is None:
            return {"status": "unparseable",
                    "reason": f"timeframe={item.get('timeframe')!r}"}
        y_min, y_max = yrs
        if v_low <= 0 or y_min <= 0 or y_max <= 0:
            return {"status": "unparseable", "reason": "non-positive value/years"}
        # conservative low = smallest multiple over the longest horizon;
        # optimistic high = largest multiple over the shortest horizon.
        low = v_low ** (1.0 / y_max) - 1.0
        high = v_high ** (1.0 / y_min) - 1.0
        return {"status": "ok", "low": low, "high": high}

    # Absolute money targets need a base revenue to become a CAGR — that base
    # comes from Screener in step 5. The gate compares these on raw fields only.
    if unit in ("crore", "cr", "lakh", "million", "mn", "billion", "bn"):
        approx = _approx_crore(v_high, unit, item.get("currency"))
        if approx is not None and approx > ABSURD_CRORE:
            return {"status": "unparseable",
                    "reason": f"absurd magnitude ~₹{approx:,.0f}cr "
                              f"({item.get('value')} {unit} {item.get('currency')})"}
        return {"status": "needs_base"}

    return {"status": "unparseable", "reason": f"unit={unit!r}"}


def rank_key(item: dict) -> float:
    """Lower-bound growth for ranking; -inf for items with no usable number."""
    g = forward_growth(item)
    return g["low"] if g.get("status") == "ok" else float("-inf")


if __name__ == "__main__":
    cases = [
        ({"metric": "revenue", "value": "2", "unit": "times",
          "timeframe": "over the next three years"}, "double in 3y ~26%"),
        ({"metric": "revenue", "value": "3-4", "unit": "times",
          "timeframe": "in 4 years"}, "3-4x in 4y ~32-41%"),
        ({"metric": "revenue", "value": "18-20", "unit": "%",
          "timeframe": "next year"}, "18-20% -> 0.18-0.20"),
        ({"metric": "revenue", "value": "2000", "unit": "crore",
          "timeframe": "by FY28"}, "absolute -> needs_base"),
        ({"metric": "revenue", "value": "3", "unit": "times",
          "timeframe": "by FY27"}, "3x by FY27 (3y) ~44%"),
        ({"metric": "none", "value": None, "unit": None,
          "timeframe": None}, "none"),
    ]
    for item, label in cases:
        g = forward_growth(item)
        if g["status"] == "ok":
            print(f"  {label:32} -> low={g['low']*100:5.1f}%  high={g['high']*100:5.1f}%")
        else:
            print(f"  {label:32} -> {g['status']}")
