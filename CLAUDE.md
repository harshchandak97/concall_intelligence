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

An automated pipeline that downloads Indian company earnings call transcripts from BSE/NSE, extracts quantifiable forward-looking guidance using an LLM, scores each company on guidance quality and credibility, cross-references with valuation data, and outputs a ranked list of companies worth deep research.

Built for personal use by an Indian retail investor with a ₹40L direct equity portfolio. The goal is to surface mid and small cap companies where management is guiding strong growth (short-term AND long-term) but the market has not priced it in yet. Aggressive forward-looking targets are the primary re-rating signal: a company that was growing slowly and then articulates a bullish multi-year vision often gets re-rated as the market begins pricing the outlook ahead of delivery.

This is a screening tool, not a buy signal.

Target universe: Companies with market cap ₹500 crore to ₹8,000 crore. This is where the tool has the most edge — thin institutional coverage, simpler single-business P&Ls, and guidance that maps cleanly to company-level metrics.

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

### How tags route to scoring
- **Ambition (Layer 2)** consumes ALL extracted items — especially long-horizon high-growth aspirations. This is the re-rating signal that drives the investing thesis.
- **Credibility (Layer 3)** consumes ONLY `credibility_scorable: true` items — near-term, company-level P&L guidance matched against actuals.

Ambition and Credibility are separate layers fed by different statement types. Extracting only near-term items would destroy the ambition signal; extracting only long-term items would leave nothing to score credibility on. The tool needs both.

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

*(This section replaces the earlier "Extraction Criteria — Critical" section, which used a flat extract/never-extract list gated purely on 4-quarter trackability. That list's examples are preserved above, now correctly split across the two gates.)*

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
| Backend | FastAPI |
| Database | PostgreSQL (Docker) + pgvector |
| ORM | SQLAlchemy |
| PDF Reading | pypdf |
| Env Management | python-dotenv |
| Valuation Data | Screener.in Premium export |
| UI | Streamlit (Phase 3) |
| Agents | Vanilla loop first, then LangGraph |
| Observability | Langfuse |

---

## Version Strategy

Three phases. Complete each version fully before moving to the next.

### PHASE 1 — AI Engineering Foundation
- v1: Extract guidance from one transcript ✓ COMPLETE
- v2: Structured output + automated eval + PostgreSQL
- v3: Multi-transcript RAG + semantic search

### PHASE 2 — Screener Core
- v4: Scoring engine (specificity + ambition)
- v5: Credibility tracker (promise vs actual across quarters)
- v6: Valuation integration + ranked output

### PHASE 3 — Full Automation
- v7: BSE/NSE automated pipeline (600+ companies)
- v8: Agent + Streamlit dashboard + deployment

---

## Current Status

Scope redefined to the Two-Gate Model (see above). Active phase: rebuild the eval set and ground truth under the new scope, then run the model + architecture bake-off. Detailed next steps live in **plan.md** — read it alongside this file.

Open items to reconcile with the actual repo state (these docs may lag the working tree):
- Confirm current eval companies (earlier docs reference Asian Paints; later sessions referenced Fineotex / Sandhar / Mold-Tek — verify which is authoritative for the new eval set).
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
├── PROJECT.md                 ← full project document
├── plan.md                    ← active phase: scope, GT rebuild, model bake-off next steps
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
├── data/                      ← ground truth and eval sets
│   ├── asian_paints_Q4_FY26_ground_truth_v3.txt
│   └── asian_paints_Q4_FY26_FLS.txt
├── transcripts/               ← PDF transcripts, gitignored
│   └── .gitkeep
└── venv/
```

Note: this listing is from the pre-two-gate session and may lag the actual working tree (e.g. pipeline/ stage modules, additional per-company data/ files). Verify against the repo before relying on it.

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
