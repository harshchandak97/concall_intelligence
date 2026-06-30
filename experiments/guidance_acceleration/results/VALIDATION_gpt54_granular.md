# Extraction validation — `gpt54_granular`, read against full transcripts

Per item: ✅ correct · ❌ wrong (level / class / value) · ➕ MISSED (company-level target the model dropped).
"Level" = the recurring failure: a segment/geography number mapped to company-level.

---

## advanced-enzyme-technologies-ltd  (call Q4 FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `revenue_growth_pct` 13-16% FY25 | ✅ | Line 281-285: "top line… between 13% to 16%" → Nitish: "13% to 16% top line growth outlook for FY'25? — Yes, that's right." Company-level. |
| 2 | `ebitda_margin_pct` 33% FY25 | ✅ | Line 311-323: consolidated EBITDA "annual numbers 29% to 33%… going ahead". Company-level margin level. |
| 3 | `revenue_growth_pct` 10% FY25-FY26 | ❌ **level** | Line 461-463: "you have grown **US** close to 9%, 10%… what growth you expect" → "maintain a 10%". This is **US geography** growth, NOT company-level. |
| — | `revenue_absolute` ₹1000cr FY28-29 | ➕ **MISSED** | Line 611-617: "₹1,000 crores top line company by '28-29… we need to grow about 14% to 16% to reach that target." Clear company-level long-term target — dropped this run (it WAS captured in the prior run → non-determinism). |

**Score: 2 / 3 extracted correct; 1 level-error; 1 missed long-term target.**

---

## kalyani-cast-tech-ltd  (call Q4 FY24, reports FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `net_margin_pct` 10-13% FY25 | ✅ | Line 170-175: "PAT will be 10% to 13%… of that" → "10% to 13% is the PAT margins". Company-level margin level. |
| 2 | `revenue_growth_pct` 40-50% FY25 | ✅ | Line 173-175: "grow by 40% to 50% during this year" → "40% to 50% is the top-line growth". Company-level. |
| 3 | `revenue_absolute` 140-150cr INR FY25 | ✅ | Line 233-234: "we will be around INR140 crores to INR145… INR150 crores this time." Company revenue target. |
| 4 | `revenue_growth_pct` 50% FY26-FY30 | ✅ (loose) | Line 696-698: "growing 50% this year. Same rate for next three/five years? — Yes, it should be." A loose confirmation, but said. |
| 5 | `revenue_growth_pct` 30-35% FY26-FY30 | ✅ | Line 868-870: "next year, maybe 30%, 35% growth will continue for another 4-5 years." Company-level long-term. |

**Score: 5 / 5 correct.** (Items 4 & 5 are both genuine but slightly redundant long-term figures — 50% loose vs 30-35% considered; the "4–5x Railway Minister" remark was correctly NOT extracted.) No misses found.

---

## mallcom-(india)-ltd  (call Q4 FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `revenue_growth_pct` 15% FY25 | ✅ | Line 131/177: "15% growth from here for the next year"; "15% minimum growth for next year". Company-level. |
| 2 | `ebitda_margin_pct` 14% FY28 | ✅ | Line 185-192: "margins… in the range of 14%… may be 50 basis point up". Company-level margin level. |
| 3 | `revenue_absolute` 1000cr INR FY28 | ✅ | Line 170-178: "target till FY28 we target Rs.1000 crore… achieve this target of 1000 crore by FY28." Company revenue target. |

**Score: 3 / 3 correct.** (The analyst's "25–30% CAGR to reach ₹1000cr" is the same guidance as the absolute — correctly not double-counted.) No misses.

---

## patel-engineering-ltd  (call Q4 FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `revenue_growth_pct` 10-15% FY25 | ✅ | Line 208: "revenue to continue to grow by around 10% to 15% in the coming year." Company-level. |
| 2 | `revenue_growth_pct` 20-25% FY26 | ✅ | Line 208-211 / 564: "in FY'26… higher growth rate of at least 20% to 25%." Company-level. |
| 3 | `ebitda_margin_pct` 14% FY25 | ✅ | Line 302 / 437: "maintain our margins of around 14%… operating EBITDA margins." Company-level level. |
| 4 | `pat_growth_pct` 10-15% FY25 | ✅ | Line 664: "10% to 15% growth in the top line. And bottom line… same percentage." Genuine PAT growth. |
| — | `revenue_growth_pct` ~20% FY27 | ➖ minor miss | Line 602-604: "'26,'27… around 20% year-on-year." Near-duplicate of #2, low impact. |

**Score: 4 / 4 correct;** 1 minor near-duplicate miss (FY27 ~20%). Clean transcript — best-extracted of the set so far.

---

## kaynes-technology-india-ltd  (call Q4 FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `revenue_growth_pct` 60% FY25 | ✅ | Line 122: "For the year 2025… growth in revenue greater than 60%." Company-level. |
| 2 | `ebitda_margin_pct` 15% FY25 | ⚠ value ✅ / **passage ❌** | Real (line 199-200: "about 15% operational EBITDA"), but the quoted passage is the *gross-margin* sentence (line 192-193), which doesn't support 15% EBITDA. Wrong evidence. |
| 3 | `revenue_growth_pct` 60% FY25 | ❌ **duplicate** | Same as #1; passage is the CAPEX-funding sentence (line 235). Deduped by decision.py. |
| 4 | `ebitda_margin_pct` 14.5-15% FY29 | ✅ | Line 307-310: "retain margins between 14.5% to 15% EBITDA… five year plan." Long-term level. |
| 5 | `revenue_absolute` 1 billion USD FY28 | ✅ | Line 366-373: "billion dollar revenue by FY'28… confident we'll achieve in 2028." |
| 6 | `ebitda_margin_pct` 15% FY28 | ✅ | Line 377-378: "current thesis level… 15%-plus EBITDA" at the FY28 ($1bn) level. |
| 7 | `net_margin_pct` 10% FY28 | ✅ | Line 378: "10%-plus PAT" → PAT margin. Correct. |

**Score: all 7 values correct & company-level;** but 1 duplicate (#3) and 1 mismatched passage (#2). The three EBITDA-margin items (FY25/FY28/FY29) are all genuinely said — decision.py's per-block selection collapses them. No misses.

---

## container-corporation-of-india-ltd  (call Q4 FY24)

| # | Extracted | Verdict | Evidence |
|---|---|---|---|
| 1 | `revenue_growth_pct` 18-20% FY25 | ✅ | Line 111-112 / 422-423: "EXIM 15%, Domestic 25%… **overall 18% to 20%** growth in FY'25." The combined figure is company-level (EXIM/Domestic segments correctly excluded). |
| 2 | `ebitda_margin_pct` 25% FY25 | ✅ | Line 163-164 / 394: "EBITDA in the range of 25%… maintain the 25% EBITDA this financial year." Company-level level. |

**Score: 2 / 2 correct.** No misses (first-mile/last-mile 50%→85% is operational, correctly excluded).

---

# OVERALL ACCURACY

| Company | items | value/class correct | level error | missed | quality issues |
|---|---|---|---|---|---|
| advanced-enzyme | 3 | 2 | **1 (US→company)** | **1 (₹1000cr)** | — |
| kalyani | 5 | 5 | 0 | 0 | 2 redundant long-term |
| mallcom | 3 | 3 | 0 | 0 | — |
| patel | 4 | 4 | 0 | 0 (1 minor near-dup) | — |
| kaynes | 7 | 7 | 0 | 0 | 1 dup, 1 bad passage |
| container | 2 | 2 | 0 | 0 | — |
| **TOTAL** | **24** | **23 (96%)** | **1** | **1 significant** | dup/passage/redundancy (handled by decision.py) |

## The two issues that actually matter

**1. Level confusion (the one you caught) — 1/24, but it's the dangerous kind.**
`advanced-enzyme` mapped **US-geography** growth ("you have grown US ~10%… maintain 10%") to company-level `revenue_growth_pct`. A false company-level number pollutes the CAGR. Rare here (one case), but it's the failure mode that corrupts the ranking, so it must be closed.
**Fix (definitional, not test-set fitting):** add to the prompt's exclude rules — *growth for a named geography/region (US, Europe, domestic, EXIM, a country) or a segment is NOT company-level unless it is explicitly the consolidated/overall total.* Geography growth is **never** company-level by definition — this generalizes to all 600.

**2. Non-determinism → inconsistent misses (the systemic one).**
`advanced-enzyme` dropped the **₹1,000cr-by-FY28-29** long-term target this run — it WAS captured in the prior run. Because `temperature` is ignored on gpt-5.4 (reasoning model), output varies run-to-run and can drop important items, including the long-term aspirations that drive the Long-CAGR / acceleration signal.
**Mitigation (no perfect fix):** (a) the freeze-once rule means you act on one frozen run; (b) the **top-tail human verification** (reading the top ~30 before freezing) catches dropped items where they matter; (c) optionally, run each transcript 2–3× and **union** the items to recover drops (2–3× cost) — worth it only if the tail check proves insufficient.

## Verdict
Value/classification accuracy is **high (~96%)** and margin-vs-growth is reliably correct. The drivers that feed the number are mostly trustworthy. **Two real reliability gaps remain:** geography/segment→company level-confusion (close via the prompt rule above) and run-to-run misses (covered by freeze-once + tail verification). With fix #1 applied, this is solid enough to scale, *provided* the top tail is human-verified before freezing.
