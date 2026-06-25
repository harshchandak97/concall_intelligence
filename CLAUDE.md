# CLAUDE.md — Concall Intelligence / Indian Equity Screener

This file gives you full context about this project. Read it at the start of every session.

---

## How to Behave

- Do NOT write code unless explicitly asked. Wait for "give me the code" or "show me the implementation".
- When asked "how do I do X" or "what's the approach" — explain the concept only, no code.
- Act as a senior AI engineer and thought partner. Help reason through decisions, explain concepts clearly, flag tradeoffs.
- Be concise and specific. Avoid generic advice. Give examples where useful.
- When reviewing code (pasted by the user), be direct and critical — point out what is wrong, what is missing, what could be better.
- Do not repeat context back unnecessarily. Get to the point.

---

## What This Project Is

Concall Intelligence — Indian Equity Screener

An automated pipeline that downloads Indian company earnings call transcripts from BSE/NSE, extracts quantifiable forward-looking guidance using an LLM, **converts that guidance into a comparable implied PAT CAGR per company under Base and Bull scenarios**, scores each company on guidance quality and credibility, cross-references with valuation data, and outputs a ranked list of companies worth deep research.

Built for personal use by an Indian retail investor with a ₹40L direct equity portfolio. The goal is to surface mid and small cap companies where management is guiding strong growth (short-term AND long-term) but the market has not priced it in yet. Aggressive forward-looking targets are the primary re-rating signal: a company that was growing slowly and then articulates a bullish multi-year vision often gets re-rated as the market begins pricing the outlook ahead of delivery.

**Why extraction alone is not enough:** extraction without a decision layer is just a fancy PDF reader. The decision layer is what turns extracted guidance into a comparable number so companies can be ranked. The v1 goal is a usable ranked table, not clean extraction alone. Future versions (credibility, valuation, automation) are built only if v1 proves useful.

This is a screening tool, not a buy signal.

Target universe: Companies with market cap ₹500 crore to ₹15,000 crore. This is where the tool has the most edge — thin institutional coverage, simpler single-business P&Ls, and guidance that maps cleanly to company-level metrics.

---

## Who Is Building This

- Name: Harsh Chandak
- Background: ~5 years as a Data Engineer (JLR, Partners Group), IIT Bombay dual degree, AWS + GCP certified
- Goal: Build this as both a personal investing tool AND a portfolio piece for AI Engineer / Senior Data Engineer roles
- Strong in: Python, SQL, PostgreSQL, FastAPI, SQLAlchemy, data pipelines
- New to: LLM APIs, RAG, agents, evaluation frameworks — learning through this project
- Personal use case: Indian retail investor, existing portfolio ₹40L, primary approach techno-fundamental

---

## Extraction Scope — Two-Gate Model (CRITICAL — read carefully)

The single most important correction to earlier versions of this doc: **"trackable within 4 quarters" is NOT an extraction gate.** It was wrongly promoted to a master filter. It is a *tag* (`credibility_scorable`) that controls automated credibility scoring only. Extraction is broader than credibility scoring.

A statement is handled in two stages. **Gate 1** decides whether to extract at all. **Gate 2** assigns tags that route the item to the correct scoring layer.

### Gate 1 — Extract? (broad, industry-agnostic, structural)
Extract the statement if ALL THREE hold:
1. **Forward-looking** — about future performance, plans, or targets (not a past-quarter explanation).
2. **Specific** — contains a number, a threshold (e.g. EBT breakeven), OR a binary outcome (e.g. "plant commissioned").
3. **Timeframe** — attached to a date, quarter, or horizon ("FY27", "by Q3", "over 3 years", "by FY29").

Horizon does NOT matter at Gate 1. A 4-year "3x revenue by FY29" aspiration IS extracted. Segment-level guidance IS extracted.

**Governing principle: falsifiable eventually.** Every extracted item must carry a number-or-threshold AND a date. Dated-but-vague or number-but-undated statements are noise. This is the hard line that keeps scope from sliding into "extract everything."

The filter is structural, not semantic — it asks "is this checkable?" not "is this good guidance?" That is why it does not require domain knowledge and works identically across industries.

### Gate 2 — Tag (where the nuance lives)
- `horizon`: near (≤4Q) | medium (1–2Y) | long (3Y+)
- `level`: company | segment | geography
- `track`: A (numeric guidance: number + timeframe) | B (binary commitment: verifiable yes/no + timeframe)
- `credibility_scorable`: true | false

`credibility_scorable` = true ONLY when ALL hold:
- `level` = company (not segment or geography)
- metric ∈ {Revenue, EBITDA/PBDIT margin, PAT/Net Profit, PBT, EPS} — i.e. available in Screener.in quarterly P&L exports
- `horizon` = near — matchable against a Screener.in quarterly export within the tracking window
- value is directly matchable against the export

`credibility_scorable` = false for:
- All long/medium-horizon aspirations (e.g. "3x revenue by FY29")
- All segment-level or geography-level metrics
- All Track B binary events (commissioning, breakeven)
- volume_growth_pct, capex_absolute, commissioning_event, volume_value_gap_pct

### How tags route to scoring and the decision layer
- **Decision layer (v1):** `level = company` items → CAGR conversion. `level = segment/geography` → Other Signals (raw text). `horizon = near` → Near CAGR block. `horizon = medium/long` → Long CAGR block. The tag schema already supports the decision layer — no schema change needed.
- **Ambition (Layer 2):** consumes ALL extracted items — especially long-horizon high-growth aspirations. This is the re-rating signal.
- **Credibility (Layer 3, future):** consumes ONLY `credibility_scorable: true` items — near-term, company-level P&L guidance matched against actuals.

### Extract these (examples)
- Revenue / margin / PAT / PBT / EPS guidance with number + timeframe (ANY horizon)
- Multi-year aspirations: "3x revenue by FY29", "₹2,000 cr revenue by FY28" → `horizon: long`, `credibility_scorable: false`
- Segment EBT breakeven by a date → `track: B`, `level: segment`, `credibility_scorable: false`
- Order book / contract values, capex commitments, commissioning timelines, volume growth %, pricing guidance — all with number + timeframe

### Never extract these
- Macro optimism without company-specific commitment
- Vague confidence statements ("we are confident of good results")
- Demand commentary without numbers
- Competitive commentary
- Past-quarter explanations
- Anything failing Gate 1 (no number/threshold, OR no date)

---

## Decision Layer (v1) — From Extraction to a Rankable Number

This is what makes the project useful. It converts tagged guidance into one comparable implied PAT CAGR per company, with evidence shown inline. It is deterministic Python — the LLM is never involved in arithmetic.

### The v1 output (LOCKED)
One row per company. Two horizon blocks. Two scenarios per block. Sorted by Near CAGR Base descending.

| Company | Near CAGR (Base–Bull) | Long CAGR (Base–Bull) | Current P/E | Guidance Used (verbatim) | Other Signals |
|---|---|---|---|---|---|

- **Near CAGR (Base–Bull):** implied PAT CAGR from all `level = company` guidance with `horizon = near` (≤1yr). Base = lower revenue bound × current trailing net margin. Bull = upper revenue bound × upper guided net-margin bound.
- **Long CAGR (Base–Bull):** same for `level = company` guidance with `horizon = medium/long` (>1yr), including aspirations ("3x by FYxx") annualised via the n-th root. Base = slower/conservative end. Bull = faster/guided-margin end.
- **Current P/E:** Screener.in, manual for v1. Surfaces the mispricing gap.
- **Guidance Used (verbatim):** every quote that produced the numbers — catches extraction errors, makes the number trustable.
- **Other Signals:** all `level = segment/geography` items, capacity additions, order book, binary events — raw text, read by eye.

### The single conversion rule (Python only — NEVER the LLM)
```
Future PAT = Guided Revenue × Guided Net Margin
Implied PAT CAGR = (Future PAT / Current PAT) ^ (1 / years) − 1
```
Applied twice per horizon block:
- **Base** = lower revenue bound × current trailing net margin (margins prove nothing until delivered)
- **Bull** = upper revenue bound × upper guided net-margin bound (both delivered together)

Ranges annualise via `^(1/years)`. "3x in 3–4 years" → Base 32% (4yr) to Bull 44% (3yr). Base numbers (Current Revenue, Current PAT, trailing net margin) come from Screener.in.

### Why bounds, not midpoints
Research shows the lower bound of a guidance range is more predictive of actual outcomes; simultaneously, management sandbagged the lower bound to make the target easier to beat. These two effects pull in opposite directions — collapsing to a midpoint creates one biased number. Use the bounds: lower → Base, upper → Bull. This naturally produces the scenario spread and avoids false precision.

### Why two horizon blocks (not one number)
Near-term and long-term guidance carry different trust levels and feed different parts of the thesis: near-term is the quarterly tracking checkpoint, long-term is the re-rating story. They also cross-check each other — e.g. "18–20% next year" compounded 4 years ≈ 2x, but "3x in 4 years" means growth must accelerate later. That gap is a flag: find the capacity/product/market catalyst that explains it, or discount the aspiration.

### Why no bear case in v1
A true bear case requires modeling a guidance miss — a downside event the transcript contains no data for. Building it means fabricating a number (violates the no-hallucination rule). Downside is handled by the credibility layer in future versions. v1 ships Base + Bull only.

### The five accuracy rules
1. LLM extracts and classifies only. Python does ALL arithmetic. (Primary hallucination guard.)
2. Use bounds, never midpoints.
3. Only `level = company` guidance enters CAGR numbers. `segment`/`geography` → Other Signals.
4. Empty cells are valid — never interpolate or ask the LLM to estimate a number management didn't give.
5. Verbatim evidence always shown inline.

### How to use the table
Sort by Near CAGR Base primarily. Scan Long CAGR for re-rating stories. Use P/E for cheapness. Read Other Signals for upside the numbers don't capture. A company with high Near CAGR, high Long CAGR, low P/E, and a big capacity addition in Other Signals = top research candidate.

---

## Ground Truth Structure

Every ground truth item and every LLM output item uses this exact structure:

```
- passage              # verbatim from PDF, self-sufficient
- speaker              # who said it
- page_number          # integer
- metric               # from controlled vocabulary (see notes.md)
- guidance_value       # numeric range or value e.g. "18-20" or "8-10", null if not applicable
- guidance_unit        # unit of measurement e.g. "%", "crore", null if not applicable
- timeline             # e.g. "H1 FY27" or "FY27" — clean value only, no explanatory notes
- horizon              # near (<=4Q) | medium (1-2Y) | long (3Y+)
- level                # company | segment | geography
- track                # A (numeric) | B (binary commitment event)
- credibility_scorable # true/false
```

`credibility_scorable` = true only when (see Gate 2 above):
- `level` = company — not segment-level or geography-level
- metric is one of: Revenue, EBITDA/PBDIT margin, PAT/Net Profit, PBT, EPS
- `horizon` = near, and value is directly matchable against a Screener.in quarterly export

`credibility_scorable` = false always for:
- All long/medium-horizon aspirations
- All segment-level or geography-level metrics
- All Track B binary events (commissioning, breakeven)
- volume_growth_pct, capex_absolute, commissioning_event, volume_value_gap_pct

Ground truth is the answer key for the EVAL SET only (~8–15 transcripts across sectors), not for all 600 production transcripts. GT files are LLM-proposed and HUMAN-adjudicated (never LLM-generated and trusted). See plan.md for the GT build process.

GT file naming: `data/{company}_{quarter}_ground_truth_v{n}.txt`

Note: the previous ground truth structure (no horizon/level/track fields) is now superseded. Existing GT files built under the old structure (e.g. asian_paints_Q4_FY26_ground_truth_v3.txt) will need re-tagging or re-versioning to the new structure before reuse in an eval run — see plan.md Step 2.

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM API | OpenAI + Anthropic. **NOTE: gpt-4o (the originally documented extraction model) was retired in early 2026.** Current extraction candidates under evaluation: Claude Sonnet 4.6 and GPT-5.4. gpt-4o-mini-class models were previously confirmed insufficient — re-test on current models rather than carrying that conclusion forward. |
| Decision layer | Pure Python (deterministic arithmetic — no LLM) |
| Backend | FastAPI |
| Database | PostgreSQL (Docker) + pgvector |
| ORM | SQLAlchemy |
| PDF Reading | pypdf |
| Env Management | python-dotenv |
| Valuation Data | Screener.in Premium export (manual CSV in v1) |
| UI | Streamlit (Phase 3); CSV / static HTML in v1 |
| Agents | Vanilla loop first, then LangGraph |
| Observability | Langfuse |

---

## Version Strategy

Three phases. Complete each version fully before moving to the next. **Future versions are built only if v1 proves genuinely useful — if v1 does not produce a usable, motivating ranked table, the project stops there.**

### PHASE 1 — AI Engineering Foundation + Usable v1 Screener
- **v1: Extraction + Decision Layer → ranked table (THE CURRENT GOAL)**
  - Run extraction on 20–30 real Q4 FY26 transcripts (sub-₹15,000cr), accept imperfect recall
  - Write the deterministic conversion script (Step 6 in plan.md): filter to company-level, split by horizon, apply Base/Bull CAGR rule
  - Fill Current Revenue / PAT / margin / P/E from Screener.in (manual CSV)
  - Output a sorted CSV or static HTML table
  - **Done when:** one command produces a ranked table a human can act on. Buildable in 2 days.
- v2: Structured output + automated eval + PostgreSQL
- v3: Multi-transcript RAG + semantic search

### PHASE 2 — Screener Core (only if v1 satisfies)
- v4: Scoring engine (specificity + ambition, formalized)
- v5: **Credibility tracker (highest-alpha layer)** — past guidance vs actuals over 4 quarters; hard gate, not just a weight
- v6: Valuation integration + composite ranked output

### PHASE 3 — Full Automation (only if v2 satisfies)
- v7: BSE/NSE automated pipeline (600+ companies); OCR for scanned PDFs
- v8: Agent + Streamlit dashboard + AWS deployment

### Future-version ideas (do NOT plan or build until v1 satisfies)
- Credibility layer (highest alpha — deliverers vs over-promisers)
- Valuation / mispricing: forward PEG = P/E ÷ implied CAGR; forward price target
- Automated Screener.in pull (name → ticker mapping)
- Acceleration-gap flag: auto-detect when Long CAGR implies acceleration vs Near CAGR
- Q&A-vs-prepared-remarks tagging (Q&A guidance more predictive)
- Tone-delta tracking QoQ (rising negativity is a strong leading signal)
- Analyst-pushback pattern detection; uncertainty-hedging language scoring

---

## Current Status

**Active goal: build the usable v1 ranked screener in 2 days.** The extraction pipeline is mostly working on the 5 eval transcripts. The new work is: finish extraction cleanly, write the ~50-line deterministic conversion script (plan.md Steps 6–8), run on 20–30 real transcripts, fill Screener.in base numbers manually, and generate the ranked Base/Bull PAT CAGR table. That is the v1 definition of done.

Open items to reconcile with the actual repo state (these docs may lag the working tree):
- Confirm current eval companies (earlier docs reference Asian Paints; later sessions referenced Fineotex / Sandhar / Mold-Tek / Sambhv — verify which is authoritative for the new eval set).
- Confirm best prompt in use (prompt_v8 is the best-performing single-pass prompt per the historical record below; verify main.py is not loading a worse later version).
- Update model references everywhere from the retired gpt-4o to current candidates (Sonnet 4.6 / GPT-5.4).

### Historical reference — Phase 1, v1 outcome (pre-two-gate scope)

Recorded under the old "4-quarter gate" scope, before the two-gate correction. Not directly comparable to future eval runs (different scope → different ground truth → different denominator), but kept for the record — do not discard this history:

- Prompt versions completed: v1 through v8 (9 runs total)
- Best production prompt: prompt_v8 on gpt-4o (gpt-4o is now retired — see Tech Stack)
- Final recall: 75% on Asian Paints Q4 FY26 (3/4 GT items)
- Final precision: 67% (2 clean GT matches, 1 persistent false positive)
- Self-sufficiency: 2/3 passages fully clean
- Ground truth: v3 locked — 4 items, Asian Paints Q4 FY26
- Model decision at the time: gpt-4o confirmed for extraction — gpt-4o-mini insufficient (both now superseded; re-test needed on Sonnet 4.6 / GPT-5.4)
- Known limitations carried forward: price increase false positive oscillates, GT4 (volume-value gap) consistently missed — both accepted as edge cases at the time

### Historical reference — v2 plan (pre-two-gate, superseded by plan.md)

- Define Pydantic schema matching ground truth structure
- Force structured JSON output from LLM using OpenAI response_format
- Build automated eval script: precision and recall computed programmatically
- Save extracted records to PostgreSQL
- Track prompt versions with scores in eval log automatically
- Done when: extraction runs on 3 transcripts, records in PostgreSQL, eval script prints scores automatically

Update this section at the start of every session.

---

## Folder Structure

```
concall-intelligence/
├── CLAUDE.md                  ← this file
├── PROJECT.md                 ← full project document (v1.2)
├── plan.md                    ← active phase: 2-day v1 build, Steps 6–8
├── .env                       ← real keys, gitignored
├── .env.example               ← key names only, committed
├── .gitignore
├── README.md
├── requirements.txt
├── eval_log.md                ← prompt iteration tracking
├── main.py
├── prompts/                   ← one file per prompt version
│   ├── prompt_v1.txt through prompt_v8.txt (v8 is current best)
├── notes.md                   ← decisions and future implementation notes
├── data/                      ← ground truth, eval sets, and Screener base numbers
│   ├── asian_paints_Q4_FY26_ground_truth_v3.txt
│   ├── asian_paints_Q4_FY26_FLS.txt
│   └── screener_base.csv      ← (to be created) Current Revenue / PAT / margin / P/E per company
├── transcripts/               ← PDF transcripts, gitignored
│   └── .gitkeep
├── pipeline/                  ← stage modules (stage0_segmenter.py etc.)
└── venv/
```

Note: this listing may lag the actual working tree (e.g. additional pipeline/ stage modules, per-company data/ files). Verify against the repo before relying on it.

---

## What NOT to Do

- Do not suggest LangChain — vanilla approaches preferred
- Do not suggest fine-tuning unless specifically asked
- Do not skip evaluation — every version has an eval step
- Do not build multiple versions simultaneously — finish one, commit, then move
- Do not treat "4 quarters" as an extraction gate — it is a tag (see Two-Gate Model)
- Do not extract statements that fail Gate 1 — a number/threshold AND a date are required (falsifiable eventually)
- Do not generate ground truth with an LLM and trust it — GT must be human-adjudicated
- Do not write code unless explicitly asked
- Do not let the LLM do arithmetic or estimate missing numbers — Python does all calculation in the decision layer
- Do not fabricate a bear case — downside belongs to the credibility layer (future version)
- Do not block v1 on perfect extraction — functional on 5 eval transcripts is enough to expand to 20–30 real transcripts
