# Experiment Plan — Does "Guidance Acceleration" Predict Stock Returns?

**Status:** design locked, not yet implemented.
**Owner:** Harsh Chandak.
**Created:** 2026-06-26.
**Goal:** Before building the full screener, cheaply test whether the core thesis is real — that a company making an unusually aggressive *first-time* forward growth promise (relative to its own past) goes on to deliver high stock returns. One quarter first; expand only if it shows a sign.

---

## 1. The thesis in one line

The re-rating alpha is **not** in the *level* of guidance — it's in the **acceleration**: a sleepy/moderate-growth company that newly articulates a much higher forward growth aspiration. That gap (forward ambition − trailing trajectory) is a positive *surprise* the market underreacts to → multiple expansion + earnings growth (the double engine).

**Academic backing** (we are confirming, not discovering): Post-Earnings-Announcement Drift (Bernard & Thomas), post-guidance drift (Das et al.), conference-call tone predicts returns (Price et al. 2012), and the drift is **10–20× larger in illiquid small caps** — exactly this universe. So the prior is favourable; the job is to confirm it survives in Indian sub-₹15,000cr names and is big enough to act on.

---

## 2. Why the obvious experiment is wrong (and what we do instead)

- **Don't select companies by looking at their returns.** Score every company *blind* to price, freeze the list, then pull returns. This is the one rule that stops us fitting the result.
- **Don't split the whole universe into thirds.** The signal is rare (~1% of companies). If we bucket the universe into thirds, the handful of winners get averaged with hundreds of ordinary companies in the same bucket and the signal disappears. (Worked example: 6 winners at +150% diluted by 194 ordinary names at +3% → top-third average only +7.4%, invisible.)
- **Instead: scan the whole universe, rank by acceleration, and study only the extreme top ~2–5%** — the rare archetype — compared to the typical company. Report those names individually too, so one lucky name can't fool us.

**Why this works:** we ask the question that matches the thesis — *"when a sleepy company makes an extreme growth promise, does that specific event tend to pay off?"* — instead of the diluted question *"do high-guidance companies on average beat the market?"*

---

## 3. Scope of THIS run: one quarter only

- **Cohort:** all sub-₹15,000cr companies that held an earnings concall for **Q4 FY24 (calls ~April–May 2024)**. Chosen because a full **+1yr return is available** and **+2yr is just available** as of June 2026.
- **Expected size:** ~400–600 companies → **top 2–5% = ~10–25 names**. Enough for a directional read.
- **This is a directional pilot, not proof.** A single quarter can be a sector/market fluke. A positive result = "expand to more quarters." A flat result = "signal is weak, reconsider before building."

---

## 4. The score (frozen before any prices are pulled)

For each company, **one comparable number**:

```
forward_growth   = implied annual growth from management's most aggressive
                   quantified, company-level forward revenue target
trailing_growth  = company's realised 3-yr revenue CAGR (from Screener)
ACCELERATION     = forward_growth − trailing_growth        ← the score
```

- Rank all companies by `ACCELERATION`, descending.
- Companies with **no quantified forward target** get no score and drop out of the top automatically.
- Revenue is the common denominator (use PAT/EBITDA only if no revenue target is given).

---

## 5. The cheap LLM extraction — exactly 4 fields per transcript

The LLM does **only the reading**, never arithmetic. We collapse the full pipeline schema down to one job: *find the single most aggressive quantified, company-level, forward-looking growth target.*

**LLM output per transcript:**

| Field | Example |
|---|---|
| `metric` | revenue (preferred) / pat / ebitda |
| `value` | "2", "3-4", "1000" |
| `unit` | times / % / crore |
| `timeframe` | "by FY27", "in 3 years" |
| (`none` if no quantified forward target) | |

- **One call per transcript, whole transcript in context** (≈14k tokens — trivial; no chunking).
- **Model:** GPT-5.4-mini (or Haiku 4.5) via Batch API — cheapest tier is fine because we only need the ranking roughly right, not perfect extraction. Est. cost for ~600 transcripts: a few thousand rupees.

**Then deterministic Python converts to `forward_growth`:**
- "double in 3 yrs" → 2^(1/3) − 1 = 26%
- "3–4× in 4 yrs" → ~32–44%
- "₹1000cr by FY27 from ₹500cr now" → compute CAGR
- ranges → use a consistent bound (e.g. lower bound)

**Worked example:**

| Company | LLM finds | forward_growth | trailing (Screener) | ACCELERATION |
|---|---|---|---|---|
| A | "double revenue in 3 yrs" | 26% | 8% | **+18** |
| B | "steady 12–14% growth" | 13% | 12% | +1 |
| C | no quantified target | — | — | excluded |

---

## 6. Data needed

| Item | Source | Notes |
|---|---|---|
| Cohort list + concall dates | Screener / BSE announcements | sub-₹15,000cr, Q4 FY24 calls |
| Transcripts | existing `scripts/download_transcripts.py` | screener→BSE fallback |
| Trailing 3-yr revenue CAGR | existing `screener.py` | for the acceleration denominator |
| Daily prices + benchmark | `yfinance` (`TICKER.NS`) / jugaad-data / nsepy | **Nifty Smallcap 250** as benchmark (better matched than Nifty 50) |

---

## 7. Execution steps (in order)

1. **Build the universe**: list sub-₹15,000cr companies with a Q4 FY24 concall + the call date.
2. **Download** all those transcripts.
3. **Cheap-extract** the 4 fields from each (one batch LLM job).
4. **Compute `forward_growth`** (Python) and pull **`trailing_growth`** (Screener) → **`ACCELERATION`** per company.
5. **FREEZE the ranked list to `frozen_ranks.csv`. Commit it. Do NOT look at prices yet.** ← anti-fitting checkpoint.
6. **Pull prices** and compute, for every company, market-adjusted return = stock return − Nifty Smallcap 250 return, over **+21 trading days, +252, +504**, measured from the close **after** the call date (no look-ahead).
7. **Analyse** (Section 8).

---

## 8. Analysis & decision (thresholds set NOW, before results)

Take the **top 5% by acceleration** (the archetype group) and compare to the **median company** in the cohort.

| Check | Plain meaning | "Validated" bar (pre-registered) |
|---|---|---|
| **Group avg return vs index** | did the tail beat the market a lot? | top-5% median 1-yr market-adj return **≥ +20%** |
| **Gap vs typical company** | is it the signal, not a rising market? | top-5% beats cohort median by **≥ +15pp** |
| **Hit rate** | did most names work, or just 1–2 lottery names? | **≥ 60%** of the top-5% beat the index meaningfully |
| **Tail case studies** | sanity | list each top-5% name's return individually |

- **All three bars met → signal is real & worth expanding to multiple quarters.**
- **Bars missed → signal weak in this cohort; reconsider before building.**
- **High average but low hit rate (driven by 1–2 monsters) → it's a lottery, not an edge.** Note this explicitly.

**Exploratory only (cannot be used to declare success):** re-ranking by near CAGR, long CAGR, forward PEG, current PEG, or acceleration×cheapness. Any of these that looks good must be confirmed on a *different* quarter later — never on this one.

---

## 9. Honest caveats

- One quarter + ~20 tail names = **suggestive, not conclusive**. It's a build/no-build gate, not a published result.
- Small-cap returns are fat-tailed — report **median, mean, and hit rate** together so one outlier can't carry the verdict.
- **Survivorship:** include names that fell or delisted; don't silently drop them.
- **Earnings-surprise confound:** the +1mo window mixes "good quarter" with "good outlook"; the +1yr/+2yr windows are cleaner for the multi-year guidance signal. Lean on the longer windows for the verdict.

---

## 10. Folder layout (this experiment)

```
experiments/guidance_acceleration/
├── PLAN.md                ← this file
├── universe.csv           ← cohort: company, ticker, concall date  (step 1)
├── transcripts/           ← downloaded PDFs                          (step 2)
├── extract_cheap.py       ← 4-field LLM extraction (batch)           (step 3)
├── score.py               ← forward_growth + trailing → ACCELERATION (step 4)
├── frozen_ranks.csv       ← committed ranked list, prices NOT seen   (step 5)
├── returns.py             ← price pull + market-adjusted returns     (step 6)
├── analyze.py             ← top-5% vs median, hit rate, case studies (step 7-8)
└── results/               ← output tables / the verdict
```

Everything for this experiment stays in this folder; it reuses the repo's existing `download_transcripts.py` and `screener.py` but writes nothing outside `experiments/guidance_acceleration/`.

---

## 11. If this quarter shows a sign (future, not now)

Repeat steps 1–8 across ~6–8 quarters, **pool** the top-5% tail cases across all quarters (~40–50 events), and re-check the same three bars on the pooled sample. That upgrades the verdict from "promising in one quarter" to "robust across time." Only then consider it validated enough to build the production screener.
