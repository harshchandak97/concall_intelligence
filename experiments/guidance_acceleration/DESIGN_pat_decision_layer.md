# Design Spec — PAT-CAGR extraction + decision layer (guidance-acceleration experiment)

**Status:** draft for review, NOT yet implemented.
**Why:** stock returns follow PAT/EPS growth, not revenue growth. Revenue → PAT only
at constant margin. So the ranking metric must be **implied PAT CAGR (Base & Bull)**,
per horizon, derived by bridging extracted guidance to PAT via Screener margins + base.

---

## 0. The big realization — most of this already exists in the repo

| Need | Already in repo | Reuse / adapt |
|---|---|---|
| PAT-CAGR cascade (PAT abs → PAT % → revenue×margin → revenue-only) | `decision.py: compute_block_cagr()` | **Reuse almost verbatim** |
| EBITDA/PBT margin → net-margin bridge (no fabrication) | `decision.py: guided_net_margin_equiv()` | Reuse |
| Horizon blocks (near vs medium/long), Base/Bull | `decision.py: process_company()` | Reuse |
| FY/timeline → years, sub-year (H1/Q2) handling | `decision.py: parse_fy_range, years_from_fy` | Reuse |
| Driver selection + auditable alternatives | `decision.py: _ranked_by_class, format_basis` | Reuse |
| Granular metric vocabulary | `prompts/v1_oneshot_prompt.txt` | Adopt the PAT-relevant subset |
| LLM output schema (currency/horizon/level/timeline) | `run.py: GuidanceItem`, `schemas.py` | Adapt |
| Screener current revenue/PAT/margins | `screener.py: fetch_screener()` | Reuse + extend (ticker by universe, +3yr history) |

**So the work is not "build a decision layer" — it's: make the LLM emit the granular
metric kinds decision.py needs, and wire Screener for ~400 companies by ticker.**

---

## 1. Extraction scope

Extract **quantifiable, company-level, forward-looking** statements that can affect
**PAT CAGR** (near or long term). Everything else → `other` (context, not in the CAGR)
or ignored. The LLM only *reads and classifies*; ALL arithmetic is Python (decision.py).

---

## 2. LLM output schema (Pydantic) — the contract

```python
from pydantic import BaseModel
from typing import List, Literal, Optional

# Metrics the PAT cascade consumes. Each is a DISTINCT KIND so Python knows what it is
# (this is what fixes the "ebitda 25% = margin level vs growth" ambiguity).
DriverMetric = Literal[
    "revenue_growth_pct",   # % or multiple ("times")
    "revenue_absolute",     # ₹/$ amount
    "pat_growth_pct",
    "pat_absolute",
    "ebitda_margin_pct",    # a LEVEL — feeds the margin bridge, NOT a growth rate
    "pbt_margin_pct",       # a LEVEL
    "net_margin_pct",       # a LEVEL (rare but clean)
]

class Guidance(BaseModel):
    metric: DriverMetric
    value: str                                  # "18-20", "1000", "2", "3-4"
    unit: str                                   # "%", "times", "crore", "lakh", "million", "billion"
    currency: Optional[Literal["INR", "USD"]]   # absolute money only; null for %/times
    timeline: str                               # "FY27", "H1 FY27", "FY28-FY29" (verbatim-resolved)
    passage: str                                # exact, verbatim, self-sufficient

class OtherSignal(BaseModel):
    label: str            # capex / order_book / segment_revenue / store_count / commissioning / volume / geography ...
    value: Optional[str]
    unit: Optional[str]
    timeline: Optional[str]
    passage: str

class Extraction(BaseModel):
    call_period: str             # "Q4 FY24" — anchors horizon/years (read from transcript header)
    items: List[Guidance]        # company-level PAT-CAGR drivers (may be empty)
    other: List[OtherSignal]     # everything else — context only, never in the CAGR
```

Notes:
- **`level` is structural, not a field:** company-level drivers go in `items`; segment/
  geography/binary/capex/volume go in `other`. (Cleaner than the v1 `level` enum.)
- **`horizon` is NOT an LLM field — Python derives it** from `timeline` + `call_period`
  (near ≤4Q / medium 1-2Y / long 3Y+). Keeps the LLM to *reading the date*; the bucketing
  is deterministic. (decision.py currently reads `item["horizon"]`; tiny tweak to derive it.)
- Mapping to decision.py's field names at load time: `value→guidance_value`,
  `unit→guidance_unit`, `timeline→timeline`. (Or rename in decision.py — one adapter.)

---

## 3. Per-field rules (carried from the current prompt, already validated)

- `value` = number exactly as spoken next to the unit; **never pre-convert** ("$1 billion"
  → value="1", unit="billion", not "1000"). **Basis points ≠ percent** (100 bps = 1%).
- `currency` = INR (crore/lakh/₹) or USD ($/dollars/bare million-billion from an exporter).
- `timeline` = machine-parseable FY or range, relative phrases resolved from `call_period`
  ("next year" from a FY24 call → "FY25"; "over 3 years" → "FY27").
- `passage` = exact, verbatim, self-sufficient (subject + number + currency + timeframe in
  the quote; expand to resolve "that number" / bare confirmations).
- **margin items are LEVELS** ("maintain 25% EBITDA margin" → `ebitda_margin_pct`, value="25").

---

## 4. The Python decision layer (reuse decision.py)

Per company, per **horizon block** (Near ≤1yr, Long >1yr), `compute_block_cagr` runs the
priority cascade and returns **(base_cagr, bull_cagr, basis, passage)**:

1. **PAT absolute** → `CAGR(pat_target / current_pat)`
2. **PAT growth %** → apply to `current_pat`
3. **Revenue (abs or %/times) + margin** → `Future PAT = Future Revenue × net_margin`
   - Base margin = **current trailing net margin** (Screener) — margins prove nothing until delivered
   - Bull margin = **guided margin** via `guided_net_margin_equiv()` (holds current net/EBITDA
     ratio constant, applies guided expansion — no fabrication), floored at trailing net
4. **Revenue only** → same as (3) with margin = trailing (Base = Bull)

`current_revenue`, `current_pat`, `trailing_net_margin`, `current_ebitda/pbt_margin` come from
**Screener**. Base uses the lower revenue bound × more years; Bull uses upper bound × fewer years.

Final per company: **Near CAGR (Base–Bull)**, **Long CAGR (Base–Bull)**, plus
`ACCELERATION = implied PAT CAGR − trailing PAT CAGR` (the experiment's ranking metric;
decision.py stops at forward PEG — we add the trailing-CAGR diff on top).

---

## 5. Edge cases (the three raised) — how this handles them

**#1 Revenue and margin on different timelines.** Items are split into Near/Long blocks by
their own `timeline`; the cascade runs *within* a block, pairing that block's revenue with a
margin. Projection horizon `n` = the revenue/PAT target's horizon (`years_from_fy`). A margin
stated as steady-state ("maintain ~25%") is usable for any block; a margin dated *later* than
the revenue target is not pulled earlier. Margins never cross-pair across blocks.

**#2 Always produce a number if there's a bridgeable item.** Because `current margin` is always
available from Screener, **any** forward growth/absolute (revenue, PAT, or — fallback — EBITDA)
yields at least a Base PAT CAGR. PAT given → Base=Bull. Revenue + no margin guide → Base=Bull.
Revenue + margin guide → Bull>Base. The **only** no-number case is a company whose sole guidance
is a flat margin *level* with no growth/absolute — correct, since it isn't promising growth.
**Add a `method` tag** (`direct_pat` > `pat_growth` > `revenue_x_margin` > `revenue_only` >
`ebitda_proxy`) so equal-looking CAGRs carry their confidence; `format_basis()` already records
the driver + unused alternatives for audit.

**#3 Aspirational long-term + short-term margin.** Computed in the **Long block, separately** —
never blended with Near into one figure. Long Base = aspirational revenue (annualised via n-th
root) × **current** margin (trusted floor); Long Bull = × best available guided margin (even if
near-term — an explicit, flagged assumption). Long CAGR is the **ambition / re-rating signal**
(lower confidence, `credibility_scorable=false` in the v1 schema), kept in a **separate column**
from Near CAGR (the commitment). The Near↔Long gap is itself the acceleration flag.

---

## 6. What is genuinely NEW for the experiment (not in the repo)

- **Screener by ticker at scale:** `screener.py` uses a 4-row manual `TICKER_MAP`; the experiment
  has `nse_ticker` for every company in `universe_with_concalls.csv` → fetch by that. Also extend
  to pull a **3-yr revenue/PAT series** for `trailing_growth` (acceleration denominator).
- **Run order:** batch LLM extract (all ~636) → drop empty-`items` companies → Screener pull for
  the rest → decision.py cascade → `ACCELERATION` → rank → top-50 manual prune (using `sector`/
  `industry` columns) → freeze → returns.
- **Sector exclusion:** drop Realty / Financial Services up front (pre-sales/AUM ≠ revenue).

---

## 7. Decisions — LOCKED (owner-confirmed)

1. **Horizon → Python-derived** from `timeline` + `call_period` (near ≤4Q / medium 1-2Y /
   long 3Y+). The LLM does not emit it. decision.py is tweaked to derive it, not read it.
2. **`other` bucket → extract it.** It's ~free (same transcript input) and gives richer
   review context. Goes to "Other Signals", never into the CAGR.
3. **EPS → leave it out** of the drivers (lands in `other` if mentioned). PAT CAGR ≈ EPS CAGR
   absent dilution, so no separate EPS handling for now.
4. **Ranking metric → ACCELERATION** (this is the EXPERIMENT's metric, per its PLAN.md §4/§8 —
   NOT the screener's CAGR-level/forward-PEG sort in the repo's plan.md):
   ```
   ACCELERATION = implied forward PAT CAGR − trailing PAT CAGR
   ```
   - forward PAT CAGR = decision.py cascade (the strongest forward block); rank key =
     **max(Near acceleration, Long acceleration)**; report Near and Long separately.
   - trailing PAT CAGR = Screener 3-yr history.
   - Sort universe by ACCELERATION, study top 2–5% (§8).
   - **forward PEG / CAGR level / P/E are carried as columns but are EXPLORATORY ONLY** (§8:
     cannot declare success on them; confirm on a different quarter). They are the screener
     view, not the experiment's verdict.
5. **Field names → rename to `value` / `unit`** in the schema AND rename
   `guidance_value`/`guidance_unit` → `value`/`unit` inside decision.py (no adapter layer).
