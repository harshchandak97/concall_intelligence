"""
Stage 4 — Acceptance Test (Synthetic Inputs)

Tests every rule and normalize_timeline example from SPEC_STAGE4_VALIDATOR.md
WITHOUT needing Stage 2 or Stage 3 output.

Run from project root: python scripts/test_stage4_acceptance.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.models import ClassifiedItem
from pipeline.stage4_validator import (
    validate,
    normalize_timeline,
    compute_credibility_scorable,
    _clean_value,
    _timeline_end_date,
)

# ── Reference call date: May 15, 2026 (Q1 FY27) ─────────────────────────────
CALL_DATE = date(2026, 5, 15)

PASS = 0
FAIL = 0


def check(label: str, actual, expected) -> None:
    global PASS, FAIL
    ok = actual == expected
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
        print(f"  {status}  {label}")
    else:
        FAIL += 1
        print(f"  {status}  {label}")
        print(f"         expected : {expected!r}")
        print(f"         got      : {actual!r}")


def _item(**kwargs) -> ClassifiedItem:
    defaults = dict(
        chunk_id="chunk_001",
        passage="Management guided for strong performance.",
        speaker="Speaker",
        page_number=5,
        metric_description="Revenue guidance",
        guidance_value="100",
        guidance_unit="crore",
        timeline="FY27",
        metric="revenue_absolute",
    )
    defaults.update(kwargs)
    return ClassifiedItem(**defaults)


def _run(items, call_date=CALL_DATE, transcript_text=""):
    valid, log = validate(items, call_date, transcript_text)
    return valid, log


# ─────────────────────────────────────────────────────────────────────────────
# normalize_timeline — spec examples
# ─────────────────────────────────────────────────────────────────────────────

print("\n── normalize_timeline ──────────────────────────────────────────────────")

# Explicit FY
check("FY27 → FY27",          normalize_timeline("FY27",     CALL_DATE), "FY27")
check("FY 27 → FY27",         normalize_timeline("FY 27",    CALL_DATE), "FY27")
check("FY2027 → FY27",        normalize_timeline("FY2027",   CALL_DATE), "FY27")
check("2026-27 → FY27",       normalize_timeline("2026-27",  CALL_DATE), "FY27")
check("2026-2027 → FY27",     normalize_timeline("2026-2027",CALL_DATE), "FY27")

# Half-year explicit
check("H1 FY27 → H1 FY27",           normalize_timeline("H1 FY27",                     CALL_DATE), "H1 FY27")
check("H1FY27 → H1 FY27",            normalize_timeline("H1FY27",                      CALL_DATE), "H1 FY27")
check("first half FY27 → H1 FY27",   normalize_timeline("first half FY27",             CALL_DATE), "H1 FY27")
check("first half of FY27 → H1 FY27",normalize_timeline("first half of FY27",          CALL_DATE), "H1 FY27")
check("H2 FY27 → H2 FY27",           normalize_timeline("H2 FY27",                     CALL_DATE), "H2 FY27")
check("second half of FY27 → H2 FY27",normalize_timeline("second half of FY27",        CALL_DATE), "H2 FY27")

# Half-year relative
check("second half of this financial year → H2 FY27",
      normalize_timeline("second half of this financial year", CALL_DATE), "H2 FY27")

# Quarter explicit
check("Q1 FY27 → Q1 FY27",           normalize_timeline("Q1 FY27",             CALL_DATE), "Q1 FY27")
check("first quarter FY27 → Q1 FY27",normalize_timeline("first quarter FY27",  CALL_DATE), "Q1 FY27")
check("first quarter of FY27 → Q1 FY27",normalize_timeline("first quarter of FY27", CALL_DATE), "Q1 FY27")
check("Q2 FY27 → Q2 FY27",           normalize_timeline("Q2 FY27",             CALL_DATE), "Q2 FY27")

# Quarter relative (no FY given — defaults to current FY=27, call in Q1 FY27)
check("second quarter → Q2 FY27",    normalize_timeline("second quarter",       CALL_DATE), "Q2 FY27")

# Relative full-year
check("this financial year → FY27",  normalize_timeline("this financial year",  CALL_DATE), "FY27")
check("this fiscal year → FY27",     normalize_timeline("this fiscal year",     CALL_DATE), "FY27")
check("next financial year → FY28",  normalize_timeline("next financial year",  CALL_DATE), "FY28")
check("next fiscal year → FY28",     normalize_timeline("next fiscal year",     CALL_DATE), "FY28")
check("next year → FY28",            normalize_timeline("next year",            CALL_DATE), "FY28")

# next quarter
check("next quarter → Q2 FY27",      normalize_timeline("next quarter",         CALL_DATE), "Q2 FY27")

# "by end of this financial year" → FY27
check("by end of this financial year → FY27",
      normalize_timeline("by end of this financial year", CALL_DATE), "FY27")


# ─────────────────────────────────────────────────────────────────────────────
# normalize_timeline — edge cases
# ─────────────────────────────────────────────────────────────────────────────

print("\n── normalize_timeline edge cases ───────────────────────────────────────")

# Q4 FY26 call context: next quarter from Q4 (Jan 2026 call, FY26) → Q1 FY27
check("next quarter from Q4 FY26 → Q1 FY27",
      normalize_timeline("next quarter", date(2026, 1, 15)), "Q1 FY27")

# Q4 on a Q1 FY27 call → past — normalize correctly and let Rule 3 reject
check("Q4 FY26 normalized correctly",
      normalize_timeline("Q4 FY26", CALL_DATE), "Q4 FY26")

# Current quarter on a Q1 FY27 call
check("current quarter → Q1 FY27",
      normalize_timeline("current quarter", CALL_DATE), "Q1 FY27")


# ─────────────────────────────────────────────────────────────────────────────
# _clean_value — Rule 2 value cleaning
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Rule 2 — _clean_value ───────────────────────────────────────────────")

check("18 → 18",               _clean_value("18"),           "18")
check("18-20 → 18-20",         _clean_value("18-20"),        "18-20")
check("18.5 → 18.5",           _clean_value("18.5"),         "18.5")
check("18.5-20.5 → 18.5-20.5", _clean_value("18.5-20.5"),   "18.5-20.5")
check("~18 → 18",              _clean_value("~18"),          "18")
check(">20 → 20",              _clean_value(">20"),          "20")
check("<20 → 20",              _clean_value("<20"),          "20")
check("around 40 → 40",        _clean_value("around 40"),   "40")
check("approximately 18-20 → 18-20", _clean_value("approximately 18-20"), "18-20")
check("18 to 20 → 18-20",      _clean_value("18 to 20"),    "18-20")
check("18% → 18",              _clean_value("18%"),          "18")
check("around text → None",    _clean_value("around text"), None)


# ─────────────────────────────────────────────────────────────────────────────
# compute_credibility_scorable
# ─────────────────────────────────────────────────────────────────────────────

print("\n── compute_credibility_scorable ────────────────────────────────────────")

check("revenue_absolute → True",      compute_credibility_scorable("revenue_absolute"),      True)
check("revenue_growth_pct → True",    compute_credibility_scorable("revenue_growth_pct"),    True)
check("ebitda_margin_pct → True",     compute_credibility_scorable("ebitda_margin_pct"),     True)
check("pat_absolute → True",          compute_credibility_scorable("pat_absolute"),          True)
check("pat_growth_pct → True",        compute_credibility_scorable("pat_growth_pct"),        True)
check("pbt_margin_pct → True",        compute_credibility_scorable("pbt_margin_pct"),        True)
check("eps_absolute → True",          compute_credibility_scorable("eps_absolute"),          True)
check("volume_growth_pct → False",    compute_credibility_scorable("volume_growth_pct"),     False)
check("capex_absolute → False",       compute_credibility_scorable("capex_absolute"),        False)
check("commissioning_event → False",  compute_credibility_scorable("commissioning_event"),   False)
check("other_segment_revenue → False",compute_credibility_scorable("other_segment_revenue"), False)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — Null value rejection
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Rule 1 — null value rejection ───────────────────────────────────────")

valid, rlog = _run([_item(guidance_value=None, metric="revenue_absolute")])
check("null value, non-commissioning → rejected",
      len(valid) == 0 and any(r["rule"] == "rule1" for r in rlog), True)

valid, rlog = _run([_item(guidance_value=None, metric="commissioning_event")])
check("null value, commissioning_event → allowed",
      len(valid) == 1, True)

valid, rlog = _run([_item(guidance_value="100", metric="revenue_absolute")])
check("non-null value, revenue → kept",
      len(valid) == 1, True)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — Malformed value
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Rule 2 — malformed guidance value ───────────────────────────────────")

valid, rlog = _run([_item(guidance_value="~18")])
check("~18 → cleaned to 18, kept",         len(valid) == 1, True)
check("~18 output value is 18",            valid[0].guidance_value if valid else None, "18")

valid, rlog = _run([_item(guidance_value="18 to 20")])
check("18 to 20 → cleaned to 18-20, kept", len(valid) == 1, True)
check("18 to 20 output value is 18-20",    valid[0].guidance_value if valid else None, "18-20")

valid, rlog = _run([_item(guidance_value="around text")])
check("uncleanable value → rejected",
      len(valid) == 0 and any(r["rule"] == "rule2" for r in rlog), True)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — Past timeline
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Rule 3 — past timeline rejection ────────────────────────────────────")

valid, rlog = _run([_item(timeline="Q4 FY26")])
check("Q4 FY26 on May-2026 call → rejected (past)",
      len(valid) == 0 and any(r["rule"] == "rule3" for r in rlog), True)

valid, rlog = _run([_item(timeline="FY26")])
check("FY26 on May-2026 call → rejected (past)",
      len(valid) == 0 and any(r["rule"] == "rule3" for r in rlog), True)

valid, rlog = _run([_item(timeline="FY27")])
check("FY27 on May-2026 call → kept (forward-looking)",
      len(valid) == 1, True)

valid, rlog = _run([_item(timeline="Q1 FY27")])
check("Q1 FY27 on May-2026 call → kept (current quarter, ongoing)",
      len(valid) == 1, True)

valid, rlog = _run([_item(timeline="H1 FY27")])
check("H1 FY27 on May-2026 call → kept",
      len(valid) == 1, True)

valid, rlog = _run([_item(timeline="next financial year")])
check("next financial year → resolves to FY28, kept",
      len(valid) == 1 and (valid[0].timeline == "FY28" if valid else False), True)

valid, rlog = _run([_item(timeline="this financial year")])
check("this financial year → resolves to FY27, kept",
      len(valid) == 1 and (valid[0].timeline == "FY27" if valid else False), True)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 — Deduplication
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Rule 5 — deduplication ───────────────────────────────────────────────")

# Exact duplicate — keep longest passage
item_a = _item(chunk_id="chunk_001", passage="Short passage.", guidance_value="18")
item_b = _item(chunk_id="chunk_002", passage="Longer passage with more context here.", guidance_value="18")
valid, rlog = _run([item_a, item_b])
check("exact duplicate → 1 item kept",     len(valid) == 1, True)
check("exact duplicate → longer passage kept",
      valid[0].passage if valid else None,
      "Longer passage with more context here.")

# Exact duplicate: normalized values "18-20" and "18.0-20.0" are the same
item_c = _item(chunk_id="chunk_003", passage="Passage C.", guidance_value="18-20")
item_d = _item(chunk_id="chunk_004", passage="Passage D long context.", guidance_value="18.0-20.0")
valid, rlog = _run([item_c, item_d])
check("18-20 and 18.0-20.0 → same item, deduped", len(valid) == 1, True)

# Different values → both kept
item_e = _item(chunk_id="chunk_005", passage="Passage E.", guidance_value="18-20")
item_f = _item(chunk_id="chunk_006", passage="Passage F.", guidance_value="17-20")
valid, rlog = _run([item_e, item_f])
check("18-20 and 17-20 → different values, both kept", len(valid) == 2, True)

# Different metrics → both kept
item_g = _item(chunk_id="chunk_007", metric="revenue_absolute",  guidance_value="100")
item_h = _item(chunk_id="chunk_008", metric="ebitda_margin_pct", guidance_value="100")
valid, rlog = _run([item_g, item_h])
check("same value different metric → both kept", len(valid) == 2, True)

# Fuzzy near-duplicate passage (>90% similar)
long_a = "We expect EBITDA margins to improve to 18-20% in FY27 driven by operating leverage."
long_b = "We expect EBITDA margins to improve to 18-20% in FY27 driven by operating levrage."  # typo
item_i = _item(chunk_id="chunk_009", passage=long_a, guidance_value="18-20", metric="ebitda_margin_pct")
item_j = _item(chunk_id="chunk_010", passage=long_b, guidance_value="18-20", metric="ebitda_margin_pct")
valid, rlog = _run([item_i, item_j])
check("fuzzy near-duplicate → 1 item kept", len(valid) == 1, True)


# ─────────────────────────────────────────────────────────────────────────────
# commissioning_event edge case — force null value
# ─────────────────────────────────────────────────────────────────────────────

print("\n── commissioning_event edge case ────────────────────────────────────────")

item_comm = _item(
    metric="commissioning_event",
    guidance_value="50000",   # Stage 2 mistakenly extracts capacity
    guidance_unit="MT",
    timeline="H1 FY27",
)
valid, rlog = _run([item_comm])
check("commissioning_event: guidance_value forced to null",
      valid[0].guidance_value if valid else "not_valid", None)


# ─────────────────────────────────────────────────────────────────────────────
# credibility_scorable set correctly on output
# ─────────────────────────────────────────────────────────────────────────────

print("\n── credibility_scorable on final GuidanceItem ───────────────────────────")

valid, _ = _run([_item(metric="revenue_absolute",   guidance_value="500")])
check("revenue_absolute → credibility_scorable=True",  valid[0].credibility_scorable if valid else None, True)

valid, _ = _run([_item(metric="volume_growth_pct",  guidance_value="10")])
check("volume_growth_pct → credibility_scorable=False", valid[0].credibility_scorable if valid else None, False)

valid, _ = _run([_item(metric="commissioning_event", guidance_value=None)])
check("commissioning_event → credibility_scorable=False", valid[0].credibility_scorable if valid else None, False)


# ─────────────────────────────────────────────────────────────────────────────
# Multi-rule interaction
# ─────────────────────────────────────────────────────────────────────────────

print("\n── multi-rule interaction ───────────────────────────────────────────────")

mixed = [
    _item(chunk_id="c01", guidance_value=None, metric="revenue_absolute", timeline="FY27"),   # rule1
    _item(chunk_id="c02", guidance_value="~15", metric="ebitda_margin_pct", timeline="FY27"), # rule2 cleaned
    _item(chunk_id="c03", guidance_value="text", metric="pat_absolute", timeline="FY27"),      # rule2 reject
    _item(chunk_id="c04", guidance_value="20", metric="revenue_growth_pct", timeline="FY26"), # rule3
    _item(chunk_id="c05", guidance_value="100", metric="revenue_absolute", timeline="FY27"),  # pass
    _item(chunk_id="c06", guidance_value="100", metric="revenue_absolute", timeline="FY27"),  # rule5 dup
]
valid, rlog = _run(mixed)
# c01 → rule1, c03 → rule2, c04 → rule3, c06 → rule5 dedup with c05
# c02 (~15 cleaned → 15, ebitda_margin_pct) and c05 (100, revenue_absolute) both survive
check("mixed: 2 valid items (c02 cleaned, c05 kept; c06 deduped)", len(valid), 2)

rule1_count = sum(1 for r in rlog if r["rule"] == "rule1")
rule2_count = sum(1 for r in rlog if r["rule"] == "rule2")
rule3_count = sum(1 for r in rlog if r["rule"] == "rule3")
rule5_count = sum(1 for r in rlog if r["rule"].startswith("rule5"))

check("mixed: 1 rule1 rejection",   rule1_count, 1)
check("mixed: 1 rule2 rejection",   rule2_count, 1)
check("mixed: 1 rule3 rejection",   rule3_count, 1)
check("mixed: 1 rule5 dedup",       rule5_count, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

total = PASS + FAIL
print()
print("=" * 60)
print(f"OVERALL: {PASS}/{total} passed — {'PASS' if FAIL == 0 else 'FAIL'}")
print("=" * 60)
