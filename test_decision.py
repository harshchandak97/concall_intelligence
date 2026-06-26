#!/usr/bin/env python3
"""
test_decision.py — Adversarial unit tests for the decision-layer arithmetic.
Run: python test_decision.py
No network, no LLM — synthetic screener + guidance inputs only.
"""

import math
from decision import (
    parse_bounds,
    parse_fy_range,
    years_from_fy,
    sub_year_offset,
    compute_cagr,
    guided_net_margin_equiv,
    compute_block_cagr,
)

PASS, FAIL = 0, 0


def check(name, got, want, tol=0.1):
    global PASS, FAIL
    ok = (got == want) if not isinstance(want, float) else (
        got is not None and abs(got - want) <= tol
    )
    if want is None:
        ok = got is None
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got={got} want={want}")
    PASS += ok
    FAIL += not ok


# --- parse_bounds ---
print("parse_bounds")
check("range", parse_bounds("18-20"), (18.0, 20.0))
check("single", parse_bounds("500"), (500.0, 500.0))
check("comma", parse_bounds("3,000"), (3000.0, 3000.0))
check("none", parse_bounds(None), (None, None))
check("garbage", parse_bounds("high single digit"), (None, None))

# --- parse_fy_range ---
print("parse_fy_range")
check("single fy", parse_fy_range("FY27"), (2027, 2027))
check("range", parse_fy_range("FY28-FY29"), (2028, 2029))
check("range short", parse_fy_range("FY28-29"), (2028, 2029))
check("with H1", parse_fy_range("H1 FY27"), (2027, 2027))

# --- sub_year_offset ---
print("sub_year_offset")
check("H1", sub_year_offset("H1 FY27"), 0.5)
check("Q2", sub_year_offset("Q2 FY27"), 0.5)
check("Q4", sub_year_offset("Q4 FY27"), 0.0)
check("plain", sub_year_offset("FY27"), 0.0)

# --- years_from_fy (fractional + floor) ---
print("years_from_fy")
check("FY27 from FY26", years_from_fy(2027, 2026, "FY27"), 1.0)
check("H1 FY27 fractional", years_from_fy(2027, 2026, "H1 FY27"), 0.5)
check("same FY floored", years_from_fy(2026, 2026, "FY26"), 0.25)  # not 0 → no silent drop

# --- guided_net_margin_equiv (Bug 1) ---
print("guided_net_margin_equiv")
scr = {"trailing_net_margin_pct": 8.0, "current_ebitda_margin_pct": 19.0,
       "current_pbt_margin_pct": 11.0}
# Guided EBITDA 25% vs current 19% → net uplift = 8 * (25/19) = 10.53% → 0.1053
m = guided_net_margin_equiv({"metric": "ebitda_margin_pct", "guidance_value": "25"}, scr)
check("ebitda→net uplift", round(m * 100, 2), 10.53)
# Guided EBITDA *below* current → floored at trailing net (no shrink)
m2 = guided_net_margin_equiv({"metric": "ebitda_margin_pct", "guidance_value": "15"}, scr)
check("ebitda below current floored", round(m2 * 100, 2), 8.0)
# Sanity: the equiv must never exceed the raw guided margin (the headline EBITDA %)
check("net equiv < guided ebitda", m < 0.25, True)

# --- compute_block_cagr: EBITDA must NOT be treated as net margin ---
print("compute_block_cagr — Bug 1 regression")
screener = {
    "current_pat_cr": 64.0,
    "current_revenue_cr": 631.0,
    "trailing_net_margin_pct": 10.14,
    "current_ebitda_margin_pct": 19.0,
    "current_pbt_margin_pct": 11.0,
}
items = [
    {"metric": "revenue_absolute", "guidance_value": "1000", "guidance_unit": "crore",
     "timeline": "FY28", "passage": "rev to 1000cr by FY28", "level": "company", "horizon": "medium"},
    {"metric": "ebitda_margin_pct", "guidance_value": "22", "guidance_unit": "%",
     "timeline": "FY28", "passage": "ebitda margin 22% by FY28", "level": "company", "horizon": "medium"},
]
base, bull, _ = compute_block_cagr(items, screener, 2026)
# Bull uses NET-equiv margin = 10.14*(22/19)=11.74%, NOT 22%.
# future_pat_bull = 1000 * 0.1174 = 117.4 ; CAGR over 2yr = (117.4/64)^.5-1 = 35.4%
check("bull uses net-equiv not ebitda", bull, 35.4, tol=1.0)
# The buggy version would have used 22%: 1000*0.22=220 → (220/64)^.5-1 = 85.5% — assert we're far below that
check("bull not inflated to ~85%", bull < 50, True)

print(f"\n{'='*40}\n{PASS} passed, {FAIL} failed")
exit(1 if FAIL else 0)
