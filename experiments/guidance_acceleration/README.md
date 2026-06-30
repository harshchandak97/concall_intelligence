# Guidance-Acceleration Experiment — Steps 1–2 (universe + transcripts)

Implements the first two execution steps of [PLAN.md](PLAN.md): build the Q4 FY24
concall cohort and download its transcripts. Everything here is **self-contained**
(stdlib-only data layer, no imports from the production pipeline) so the experiment
can't be confused with the main project.

## What it does

1. **Cohort** (`build_universe.py`): sweep the BSE announcements feed market-wide for
   every *Earnings Call Transcript* filed in the Q4 FY24 results window
   (Apr 1 – Jun 30 2024), then keep only companies whose **current** market cap (read
   live from screener.in) is **≤ ₹50,000 cr**.
2. **Download** (`download_concalls.py`): pull each cohort company's transcript PDF
   into `transcripts/`, page-count checked (real transcript ≈ 15–25 pages; `<5p`
   flagged `COVER?`).

The cohort is the intersection *(held a Q4 FY24 concall)* ∩ *(mcap ≤ ₹50,000 cr today)*.
We get there concall-first because the BSE transcript feed returns the few hundred
concall-holders in one sweep — far cheaper than reading market cap for all ~5,000
listed names. The result is identical either way.

## Files

| File | Role |
|---|---|
| `lib_bse.py` | stdlib data helpers (HTTP, BSE sweep, screener parse, PDF download). HTTP/PDF/quarter helpers duplicated verbatim from `scripts/download_transcripts.py`. |
| `build_universe.py` | Step 1–2 → `universe_with_concalls.csv` (+ `universe_unresolved.csv`). |
| `download_concalls.py` | Step 4 → `transcripts/*.pdf` (+ `download_log.csv`). Batch summaries, inline ❌/⚠ flags, final failures block; `--skip-existing` to resume. |
| `recover_covers.py` | Second pass: re-fetches the correct transcript for any `<5p` COVER? PDF (some companies file a cover/audio stub alongside the real transcript) → `recover_log.csv`. |
| `extract_cheap.py` | Batch-ready OpenAI extraction for the PAT-CAGR driver fields. Builds Batch JSONL + manifest, submits, checks status, collects parsed results, and writes cache/token usage summaries. |
| `universe_all.csv` | Every concall company (827) + current market cap + status (`kept` / `over_cap` / `unresolved`) — lets you re-pick the cap later without re-fetching. |

## Usage

```bash
cd experiments/guidance_acceleration

# quick slice to sanity-check
python build_universe.py --limit 15

# full Q4 FY24 cohort (~800 concalls swept; screener fetch per name, cached/resumable)
python build_universe.py

# smoke-test the download, then the full pull (resumable)
python download_concalls.py --limit 20
python download_concalls.py --skip-existing

# recover any 1-page COVER? PDFs from alternate BSE filings
python recover_covers.py

# build and inspect a Batch API request file without spending API money
python extract_cheap.py --all --dry-run --model gpt-5.4 --out-name gpt54_full

# submit the full usable-transcript extraction batch, then poll and collect
python extract_cheap.py --all --batch --model gpt-5.4 --out-name gpt54_full
python extract_cheap.py --status <batch_id>
python extract_cheap.py --collect <batch_id>

# if download_log.csv is stale and you want every top-level PDF on disk
python extract_cheap.py --all-files --batch --model gpt-5.4 --out-name gpt54_all_files
```

## Result (Q4 FY24 run)

827 concall companies → **694 cohort** (≤₹50,000cr) → transcripts downloaded:
**636 OK** (real, ≥5p), **58 COVER?** (BSE has only a cover/weblink; transcript on
the company IR site), **0 missing**. 26 of the initial 84 covers were auto-recovered
by `recover_covers.py`.

Knobs: `build_universe.py --cap-max 50000 --from 20240401 --to 20240630 --pause 0.4`.
Screener pages cache to `.cache/screener/` so reruns resume cheaply.
`download_concalls.py --skip-existing` to resume an interrupted pull.

## Outputs

- `universe_with_concalls.csv` — the cohort: `company_name, nse_ticker, slug,
  bse_scrip, market_cap_cr, concall_date, attachment, headline`. This is the frozen
  list that steps 3+ (extraction → score → freeze ranks → prices) consume.
- `universe_unresolved.csv` — concall companies whose market cap couldn't be read
  (delisted / not on screener). **Logged, not dropped** — preserves survivorship
  visibility (PLAN §9).
- `download_log.csv` — per-company download status.

## Design decisions & caveats

- **Current market cap, not as-of-2024.** The owner chose a current ≤₹50,000 cr cut.
  No free API returns per-company *historical* market cap by date (verified: BSE
  exposes only per-company *current* mcap or *aggregate* historical; yfinance/jugaad
  give price + shares, not a mcap field). A precise 31-Mar-2024 mcap would require
  `dated price × dated shares`; deliberately skipped for this pilot.
- **BSE date-window limit.** The announcements API silently returns nothing for
  windows wider than ~1 month, so the sweep is chunked into ≤28-day pieces and merged.
- **Mangled scrip codes.** The feed occasionally reports a wrong scrip (e.g. BPCL as
  `100547` vs `500547`) that 404s on screener; we fetch screener by the **NSE ticker
  first** (from the filing's NSURL), falling back to the scrip.
- **Concall date = BSE filing date**, within a day or two of the actual call.
- **Q4 window.** A handful of Q4 FY24 calls held in early July would be tagged Q1 by
  BSE; the Apr–Jun window captures the overwhelming majority.
- **Non-equity noise.** Some debt/SME issuers file "transcripts"; they 404 on
  screener and land in `universe_unresolved.csv`, never in the cohort.

Steps 3+ (extraction, scoring, freeze, prices, analysis) are out of scope here.
