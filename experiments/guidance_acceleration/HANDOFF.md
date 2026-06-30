# Handoff — guidance_acceleration (post-design-lock)

## What this experiment is
Tests one thesis cheaply before building the full screener: does a sleepy company making
an unusually aggressive forward growth promise go on to deliver high stock returns?
**ACCELERATION = forward PAT CAGR − trailing 3yr PAT CAGR.** Rank by it, freeze ranks,
pull forward returns. Cohort = Q4 FY24 concalls, sub-₹50,000cr.
Everything lives self-contained in `experiments/guidance_acceleration/` (do NOT import the
production pipeline). Read `CLAUDE.md` for project rules: LLM extracts/classifies only,
Python does ALL arithmetic, no fabricated numbers.

---

## Exact batch size: 652 usable transcripts

Funnel (do not re-derive — use these numbers):
- `universe_all.csv`: 827 companies screened (sub-₹50,000cr Q4 FY24 cohort)
- 133 dropped — ALL are large caps > ₹50,000cr, zero in-scope companies missing
- `universe_with_concalls.csv`: 694 companies, all with download attempts, all in `download_log.csv`
- 636 with status `OK` originally (includes 26 recovered in first recover pass)
- 58 with status `COVER?` — went through multi-pass recovery this session:
  - **16 newly recovered** (4 via BSE alternate, 12 via link-letter URL extraction)
  - **42 still cover-only** — need manual check (see list below)
- **Total usable for batch: 652** (636 + 16 newly recovered)

**IMPORTANT:** `download_log.csv` still shows the 16 newly recovered as `COVER?` —
it has NOT been updated yet. `lib_extract.usable_transcripts()` reads the log and will
only return 636 until the log is updated. **Update the log before running the batch.**
The 16 recovered slugs are in `recover_log.csv` where `result == RECOVERED` (this session's
run — the log was rewritten, so all 16 are in it alongside the 42 still-cover).

---

## Design decisions LOCKED (all implemented in score.py / lib_screener.py)

1. **Forward CAGR = max(near, long) by Base** — boldest promise on either horizon.
   Both near and long blocks shown as separate columns in output.
2. **Rank by Base; show Base + Bull** — conservative sort, upside visible.
3. **Turnarounds kept in main table AND a separate "Trailing-unrankable" table** —
   main table stays sortable; unrankable rows collected below for human review.
4. **Sector filter: none** — run all sectors, filter Realty/FinServ by eye using the
   sector column in output. Simpler; data preserved for later.
5. **Full-run model: GPT-5.4 full (Batch)** — matches the ~96%-validated test extractions.
   GPT-5.4-mini over-reads; do not substitute.
6. **Consolidated-always basis with divergence-gated standalone-prior borrow:**
   - Consolidated is always the reporting basis.
   - If consolidated lacks the prior FY (FY21 for Q4 FY24 calls), fetch standalone and
     borrow ONLY the prior-FY row, ONLY IF overlap sales-divergence < 10%.
   - Above 10% divergence: leave trailing as `missing` → unrankable table.
   - Every borrow is audited: `prior_source` + `overlap_div_pct` in CSV and .md.

---

## Current 6-company result (post-design-lock, run `score.py --candidate gpt54_scope`)

| # | Company | Sector | Near B/Bull | Long B/Bull | Fwd CAGR B/Bull | Trailing | Accel B/Bull |
|---|---|---|---|---|---|---|---|
| 1 | Advanced Enzyme Technologies | Healthcare | 13.0/16.0% | 9.9/9.9% | **13.0/16.0% (near)** | -3.2% | **+16.2/+19.2** |
| 2 | Mallcom (India) | Capital Goods | 15.0/15.0% | 24.1/24.1% | **24.1/24.1% (long)** | 8.7% | **+15.4/+15.4** |
| 3 | Container Corp | Services | 18.0/30.4% | —/— | 18.0/30.4% (near) | 36.1% | -18.1/-5.7 |
| 4 | Kaynes Technology | Capital Goods | 60.0/71.5% | 46.6/49.2% | 60.0/71.5% (near) | 163.5% | -103.5/-92.0 |
| 5 | Kalyani Cast-Tech | Capital Goods | 49.0/59.6% | 50.0/50.0% | 50.0/50.0% (long) | base_pat_nonpositive | — |
| 6 | Patel Engineering | Construction | 10.0/15.0% | 20.0/25.0% | 20.0/25.0% (long) | base_pat_nonpositive | — |

Kalyani: fixed from `missing` → `base_pat_nonpositive` (standalone FY21 borrowed,
overlap div=0.0%, PAT≈₹0cr → CAGR undefined but correctly labelled).

---

## Files and their current state

- **`lib_screener.py`** — consolidated-always + divergence-gated standalone-prior borrow.
  `fetch_series(scrip, ticker, base_fy, lookback)` returns `prior_source` + `overlap_div_pct`
  for audit. MAX_OVERLAP_DIV_PCT = 10.0.
- **`lib_fx.py`** — offline USD/INR quarterly table 2013–2025. No changes needed.
- **`decision.py`** — cascade: pat_absolute → pat_growth_pct → revenue+margin → revenue-only.
  Implausibility guard (>100%/yr revenue CAGR → skip). No changes needed.
- **`score.py`** — orchestrator with all design decisions locked:
  - max(near, long) by Base for forward CAGR
  - near/long columns both shown
  - sector column in console + CSV + markdown
  - separate "Trailing-unrankable" table in markdown
  - prior_source + overlap_div_pct in CSV and per-company evidence
- **`recover_covers.py`** — rewritten to multi-pass: BSE alternates (Apr–Sep 2024 window)
  → link-letter URL extraction from cover PDF → give up.
- **`extract_cheap.py`** — unchanged; use `--all --batch --model gpt-5.4` for the full run.

---

## 42 companies still needing manual transcript check

These have only a 1-page cover/link PDF on disk. Check the company's IR website directly.
The bottom 7 (Rane group + AG Ventures + IRIS RegTech + Expleo) likely have no transcript at all.

| Scrip | Company |
|---|---|
| 506579 | AG Ventures Ltd |
| 532988 | Rane Engine Valve Ltd |
| 540735 | IRIS RegTech Solutions Ltd |
| 532987 | Rane Brake Lining Ltd |
| 533121 | Expleo Solutions Ltd |
| 505800 | Rane Holdings Ltd |
| 532661 | Rane (Madras) Ltd |
| 532610 | Dwarikesh Sugar Industries Ltd |
| 506618 | Punjab Chemicals & Crop Protection Ltd |
| 500199 | IG Petrochemicals Ltd |
| 543652 | Fusion Finance Ltd |
| 532983 | RPG Life Sciences Ltd |
| 513269 | Man Industries (India) Ltd |
| 534804 | CARE Ratings Ltd |
| 517168 | Subros Ltd |
| 500185 | Hindustan Construction Company Ltd |
| 531431 | Shakti Pumps India Ltd |
| 538666 | Sharda Cropchem Ltd |
| 532856 | Time Technoplast Ltd |
| 532922 | Edelweiss Financial Services Ltd |
| 532439 | Olectra Greentech Ltd |
| 505283 | Kirloskar Pneumatic Company Ltd |
| 506590 | PCBL Chemical Ltd |
| 543335 | Aptus Value Housing Finance India Ltd |
| 532714 | KEC International Ltd |
| 500101 | Arvind Ltd |
| 517146 | Usha Martin Ltd |
| 539083 | Inox Wind Ltd |
| 514162 | Welspun Living Ltd |
| 505714 | Gabriel India Ltd |
| 524742 | Caplin Point Laboratories Ltd |
| 540596 | Eris Lifesciences Ltd |
| 513375 | Carborundum Universal Ltd |
| 543635 | Piramal Pharma Ltd |
| 522287 | Kalpataru Projects International Ltd |
| 532514 | Indraprastha Gas Ltd |
| 532947 | IRB Infrastructure Developers Ltd |
| 532144 | Welspun Corp Ltd |
| 524000 | Poonawalla Fincorp Ltd |
| 532331 | Ajanta Pharma Ltd |
| 532830 | Astral Ltd |
| 513683 | NLC India Ltd |

---

## Immediate next steps (in order)

### Step A — Update download_log.csv for the 16 newly recovered companies
`lib_extract.usable_transcripts()` reads `download_log.csv` and only returns status=OK rows.
The 16 recovered still show COVER? in the log. Fix: for each scrip in `recover_log.csv`
where `result==RECOVERED`, update `download_log.csv` status→OK and pages→actual page count.
Either do this with a small Python patch script, or re-run `download_concalls.py --skip-existing`
(it will mark existing valid PDFs as SKIP which also counts as usable).

### Step B — Decide on the 42 manual-check companies
Options: (a) manually find + download their PDFs and add to transcripts/; (b) skip them
and run the batch on 652; (c) run the batch on 652 now and circle back.
Recommended: run on 652 now, don't block the batch on 42 edge cases.

### Step C — Submit the full extraction batch
```
cd experiments/guidance_acceleration
python extract_cheap.py --all --batch --model gpt-5.4 --out-name gpt54_full
```
This submits ~652 transcripts to OpenAI Batch API (50% off). Note the batch ID printed —
needed for `--collect` when status=completed (typically 1-24 hours).

### Step D — Collect batch results
```
python extract_cheap.py --collect <batch_id> --out-name gpt54_full
```

### Step E — Run score.py on full results
```
python score.py --candidate gpt54_full
```
This fetches Screener for ~652 companies (cached to `extractions/screener_cache.json`).
First run will be slow (~30 min with rate-limit pauses). Use `--refresh` only if you
need to bust the Screener cache.

### Step F — Freeze ranks
Review `results/acceleration_gpt54_full.md`. Do a top-tail human check (eyeball top 20-30
for extraction quality). Then:
```
cp results/acceleration_gpt54_full.csv results/frozen_ranks.csv
```
Record the freeze date. This is the irreversible step — ranks must not change after this.

### Step G — Pull forward returns
For each company in `frozen_ranks.csv`, pull the stock price on the freeze date and
~12 months later. Compare high-acceleration vs low-acceleration cohorts.

---

## How to run (quick reference)
```
cd experiments/guidance_acceleration

# smoke tests
python lib_screener.py
python lib_fx.py
python score.py --candidate gpt54_scope          # 6-company test; --refresh to bust cache

# full pipeline
python extract_cheap.py --all --batch --model gpt-5.4 --out-name gpt54_full
python extract_cheap.py --collect <batch_id> --out-name gpt54_full
python score.py --candidate gpt54_full
```
