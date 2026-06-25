# Concall Intelligence — Indian Equity Screener
## Project Document v1.2

> **v1.2 change log (decision layer added):** The project now has an explicit **decision layer** that converts extracted forward-looking guidance into a comparable, rankable number per company — implied PAT CAGR, computed under Base and Bull scenarios across two horizon blocks (near ≤1yr, long >1yr). Extraction was always a means; the end is a usable ranked screener output that drives investment decisions. This change adds the "Decision Layer (v1)" section and a research-grounded rationale, and reframes Phase 1 v1's definition of done around a ranked table rather than clean extraction alone. The Two-Gate extraction model (v1.1) is unchanged and feeds directly into the decision layer via the existing `level` and `horizon` tags.
>
> v1.1 change log (retained): Extraction scope redefined. The "trackable within 4 quarters" rule is a Gate-2 tag controlling credibility scoring only, not an extraction gate. Extraction captures all falsifiable-eventually forward-looking statements (number/threshold + timeframe, any horizon). Model references updated (gpt-4o retired).

---

## The Problem Being Solved

Indian retail investors cannot efficiently find companies where management is projecting strong future growth but the stock is currently undervalued. The information asymmetry exists because:

- 4,600+ companies are listed on NSE/BSE
- ~600–900 publish concall transcripts every quarter
- Almost nobody outside institutional investors reads these transcripts
- No existing tool scans ALL concall transcripts, extracts forward-looking guidance, converts it into a comparable growth number, and cross-references it with current valuation to produce a ranked shortlist

The edge: companies where management gives specific, quantifiable positive guidance — short-term OR a bullish multi-year vision — but the market hasn't priced it in yet. Aggressive long-horizon targets are the primary re-rating catalyst: when a previously slow-growing company articulates a big quantified outlook, the market starts pricing it ahead of delivery.

**Why this edge is real (research-grounded):** Forward earnings expectation is the dominant driver of stock returns at the 1–2 year horizon (Chen & Zhao: cash-flow news explains ~37% of return variance at 1 year, ~54% at 2 years, exceeding discount-rate news beyond two years). The sub-₹15,000cr universe has limited analyst coverage → pricing inefficiencies, and a wide guidance-vs-delivery gap (~40% of Indian small caps miss expectations vs ~25% for large caps). The screener surfaces the forward-guidance signal before the market reprices it.

---

## What This Project Does

An automated pipeline that:

1. Downloads concall transcript PDFs from BSE/NSE filings every quarter
2. Extracts only meaningful, falsifiable forward-looking guidance using an LLM (Two-Gate model)
3. **Converts that guidance into a comparable implied PAT CAGR per company (Base + Bull scenarios, near + long horizons)** ← the decision layer added in v1.2
4. Cross-references with current valuation data
5. Tracks whether management delivered on past near-term guidance (credibility scoring — future version)
6. Outputs a ranked list of companies worth individual deep research

This is a screening tool, not a buy signal. The output is a shortlist for further human research.

Target universe: Companies with market cap ₹500 crore to ₹15,000 crore. Small and mid cap focus. This is where the information edge is highest — thin institutional coverage, simpler single-business P&Ls, and management guidance that maps cleanly to company-level financial metrics. Large caps are used for testing and eval only.

---

## Extraction Criteria — What Gets Extracted (Two-Gate Model)

Handling is split into two gates. **Gate 1** = extract or not (broad, structural, industry-agnostic). **Gate 2** = tag, which routes each item to the right scoring layer AND to the right decision-layer bucket. The 4-quarter and Screener-matchability constraints belong to Gate 2 ONLY — they do not restrict extraction.

### Gate 1 — Extract if ALL three hold
1. Forward-looking (future plan/target, not past-quarter explanation)
2. Specific — a number, a threshold (e.g. EBT breakeven), or a binary outcome (e.g. plant commissioned)
3. Has a timeframe (date, quarter, or horizon)

**Core extraction rule — falsifiable eventually:** a statement must carry a number-or-threshold AND a date. If it can never be checked, it is noise. Horizon is irrelevant here — a 4-year aspiration that can be checked on trajectory each quarter qualifies.

| Type | Example | Note |
|---|---|---|
| Revenue guidance | "₹800–900 crore revenue in FY27" | |
| Margin guidance | "EBITDA margins to 17–18% from 13%" | |
| **Multi-year aspiration** | "3x revenue by FY29" | horizon: long, credibility_scorable: false — KEY re-rating signal |
| **Segment binary event** | "Segment X reaches EBT breakeven by Q3 FY27" | track: B, level: segment, credibility_scorable: false |
| Order book | "Executable order book ₹1,200 crore over 18 months" | |
| Capacity addition | "New plant commissioned in Q3, +40% capacity" | |
| Capex commitment | "₹250 crore capex over 2 years" | |
| Volume guidance | "8–10% volume growth going forward" | |
| Pricing guidance | "Further price increases, 10.5% so far" | |
| Project timelines | "VAM-VAE plant commissioning in H1 FY27" | |

### Gate 2 — Tags
- `horizon`: near (≤4Q) | medium (1–2Y) | long (3Y+)
- `level`: company | segment | geography
- `track`: A (numeric guidance) | B (binary commitment event)
- `credibility_scorable`: true only when level=company AND metric ∈ {Revenue, EBITDA/PBDIT margin, PAT, PBT, EPS} AND horizon=near AND Screener-matchable; false otherwise.

**How tags feed the decision layer (v1.2):** the decision layer keys directly on existing tags — no schema change. `level = company` items become CAGR inputs; `level = segment/geography` items become Other Signals. `horizon = near` routes to the Near block; `horizon = medium/long` routes to the Long block.

### Ignore These (fail Gate 1)
- Macro optimism: "India's growth story remains strong"
- Vague confidence: "We are confident of delivering good results"
- Demand commentary without numbers: "Demand environment is positive"
- Competitive commentary: "Competitive intensity will continue"
- Explanations of past quarter performance

---

## Decision Layer (v1) — From Extraction to a Rankable Number

This is the layer that makes the project useful rather than just an extractor. It converts tagged guidance into one comparable number per company, with the evidence shown inline.

### The v1 output (LOCKED)
One row per company. Two horizon blocks. Two scenarios per block.

| Company | Near CAGR (Base–Bull) | Long CAGR (Base–Bull) | Current P/E | Guidance Used (verbatim) | Other Signals |
|---|---|---|---|---|---|

- **Near CAGR (Base–Bull):** implied PAT CAGR from company-level guidance with horizon ≤ 1 year.
- **Long CAGR (Base–Bull):** same for company-level guidance with horizon > 1 year, including aspirations ("3x by FYxx") annualised.
- **Current P/E:** from Screener.in (manual in v1). Surfaces the mispricing gap.
- **Guidance Used (verbatim):** the exact quotes that produced the numbers — catches extraction errors, makes the number trustable.
- **Other Signals:** unconvertible items (segment/geography guidance, capacity, order book, binary commissioning) as raw text, read by eye.

### The single conversion rule (deterministic Python — NEVER the LLM)
```
Future PAT = Guided Revenue × Guided Net Margin
Implied PAT CAGR = (Future PAT / Current PAT) ^ (1 / years) − 1
```
Applied twice per horizon block:
- **Base** = lower revenue bound × current trailing net margin (margins prove nothing until delivered)
- **Bull** = upper revenue bound × upper guided net-margin bound (both delivered together)

### Why bounds, not midpoints (research-grounded)
Empirical research on analysts' reaction to range forecasts shows the lower bound carries more predictive weight, AND that management pads the upper bound by pairing it with a sandbagged lower bound. These pull in opposite directions — so don't collapse to one biased point. Use the range itself: lower bound → Base, upper bound → Bull.

### Why two horizon blocks (keystone design decision)
Near-term and long-term guidance answer different questions, carry different trust levels, and feed different parts of the thesis: near-term is the quarterly tracking checkpoint; long-term is the re-rating story. They also cross-check each other — e.g. "18–20% next year" compounded 4 years ≈ 2x, but "3x in 4 years" implies acceleration. That gap is a flag: find the catalyst (capacity/product/market) that explains the acceleration, or treat the aspiration as talk.

### Why no bear case in v1
A true bear case requires modeling a guidance *miss* — a downside event the transcript contains no data for. Building it would mean inventing numbers (violates the no-hallucination rule). Downside is handled later, correctly, by the credibility layer discounting a chronic misser's Base case. v1 ships Base + Bull only.

### The five accuracy rules
1. LLM extracts and classifies only. Python does ALL arithmetic. (Primary hallucination guard.)
2. Use bounds, never midpoints.
3. Only `level = company` guidance enters CAGR numbers. `segment`/`geography` → Other Signals.
4. Empty cells are valid. Never interpolate or ask the LLM to estimate a number management didn't give.
5. Verbatim evidence always shown inline.

### How to use the table
Sort by Near CAGR Base primarily. Scan Long CAGR for re-rating stories. Use P/E for cheapness. Read Other Signals for upside the numbers don't capture. A company with high Near CAGR, high Long CAGR, low P/E, and a big capacity addition in Other Signals = top research candidate.

---

## Scoring Framework (4 Layers) — full vision, mostly future

The decision layer above is the v1 realization of Layers 1–2. Layers 3–4 are future versions.

### Layer 1: Guidance Specificity (15% weight)
Does management give actual numbers or just vibes? Score 1 (vague) → Score 5 (fully specific). Partly realized in v1: only specific, falsifiable guidance survives Gate 1 and produces a CAGR; vague statements are excluded.

### Layer 2: Guidance Ambition — Implied Growth (20% weight)
How aggressive is guidance vs current performance? **This is the core of the v1 decision layer — the implied PAT CAGR IS the ambition signal.** Consumes ALL extracted items, especially long-horizon aspirations (the re-rating signal).

### Layer 3: Management Credibility (35% weight — MOST IMPORTANT — FUTURE)
Did they deliver on what they said? Consumes ONLY `credibility_scorable: true` items. Delivery Ratio = Actual / Guided, averaged over 4 quarters. **The highest-alpha layer per the research, and almost certainly v2 — but built only after v1's extraction→number loop works.** A bullish vision plus a clean near-term track record is shortlist gold; the same vision from a chronic misser is a discard.

### Layer 4: Valuation Discount (25% weight — FUTURE)
Forward PEG = Current PE ÷ Guided Growth Rate. In v1 this is a manual glance via the Current P/E column; automating it is a future version.

### Composite Score Formula (future)
```
Final Score = (Specificity × 0.15) + (Ambition × 0.20) +
              (Credibility × 0.35) + (Valuation Discount × 0.25)
```

### Bonus Signal (Phase 3)
Promoter open-market buying in last quarter: +0.5 to Final Score.

---

## System Architecture

```
BSE/NSE Website
      ↓
Download Concall PDFs (automated script)
      ↓
Extract Text from PDFs (pypdf) → Stage 0 deterministic segmenter
      ↓
Send to LLM → Get Structured JSON (guidance data, two-gate tagged)
      ↓
DECISION LAYER (deterministic Python): filter to company-level, split by horizon,
   apply Base/Bull conversion rule → implied PAT CAGR per company       ← v1.2
      ↓
Store in PostgreSQL (with pgvector for semantic search)
      ↓
Pull Valuation Data (Screener.in export)
      ↓
Run Scoring Logic
      ↓
Ranked Output (CSV/HTML in v1; Streamlit dashboard later)
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| LLM API | OpenAI + Anthropic. gpt-4o RETIRED (early 2026). Current extraction candidates: Claude Sonnet 4.6, GPT-5.4. |
| Decision layer | Pure Python (deterministic arithmetic — no LLM) |
| Backend | FastAPI |
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy |
| PDF Reading | pypdf |
| Env Management | python-dotenv |
| Valuation Data | Screener.in Premium export (manual CSV in v1) |
| UI | Streamlit (later); CSV/static HTML in v1 |
| Agents | Vanilla loop first, then LangGraph |
| Observability | Langfuse |

---

## Version Strategy

Build in phases. Each phase ships something usable on its own. Never start the next phase until the current one is complete and committed. **v1 must stand on its own — future versions are built only if v1 is genuinely useful.**

### PHASE 1 — AI Engineering Foundation + Usable v1 Screener
Goal: a working ranked screener output. Interview-ready and personally useful after this phase.

#### v1 — Extraction + Decision Layer → ranked table (THE CURRENT GOAL)
- Run extraction on 20–30 real Q4 FY26 transcripts (sub-₹15,000cr), accept imperfect recall
- Write the deterministic conversion script (~50 lines): filter to company-level, split by horizon, apply Base/Bull CAGR rule
- Pull Current Revenue / PAT / margin / P/E from Screener.in (manual CSV)
- Output one ranked table, sorted by implied PAT CAGR, evidence inline, unconvertible items flagged
- **Done when:** one command (plus a manual Screener CSV) produces a sorted, usable ranked table. Buildable in 2 days.

#### v2 — Structured output + eval pipeline + PostgreSQL
- Pydantic schema, forced structured JSON, automated eval, records to PostgreSQL, prompt versions tracked

#### v3 — Multi-transcript RAG
- Chunk by speaker turn; embed; pgvector; hybrid search + reranking; retrieval evaluated separately

### PHASE 2 — Screener Core (only if v1 satisfies)
- v4: Scoring engine (Layer 1 specificity + Layer 2 ambition, formalized)
- v5: **Credibility tracker (Layer 3)** — the highest-alpha layer; promise vs actual across 4 quarters
- v6: Valuation integration + Layer 4 + composite ranked output

### PHASE 3 — Full Automation + Production (only if v2 satisfies)
- v7: BSE/NSE automated download pipeline (200+ then 600+; flag scanned PDFs, OCR later)
- v8: Agent orchestration + Streamlit dashboard + AWS deployment

---

## Future-Version Ideas (do NOT build until v1 satisfies)

Recorded so the path is visible; built only if v1 proves useful. Rough order of value:
- **Credibility layer (highest alpha)** — deliverers vs over-promisers; hard gate; needs past-guidance extraction. Likely v2.
- **Valuation / mispricing** — forward PEG = P/E ÷ implied CAGR; forward price target = guided EPS × conservative multiple.
- **Automated Screener.in pull** — replace manual base-number CSV; needs name→ticker mapping.
- **Acceleration-gap flag, automated** — auto-detect Long-CAGR-implies-acceleration-vs-Near and surface "find the catalyst."
- **Extraction signal enhancements** — Q&A-vs-prepared-remarks tagging (Q&A more predictive); tone-delta QoQ (rising negativity is a strong signal); analyst-pushback detection; uncertainty-hedging scoring.
- **Composite scoring + weights** across all 4 layers — only once each proves useful individually.

---

## Interview Talking Points (Grows With Each Version)

| When they ask | You can say |
|---|---|
| What does this project actually do? | "It scans Indian small/mid-cap earnings calls, extracts quantifiable management guidance, converts it into a comparable implied PAT-growth number under base and bull scenarios, and ranks companies — surfacing the forward-earnings signal before the market reprices it." |
| How do you turn messy guidance into a comparable number? | "A deterministic conversion layer. The LLM only extracts and classifies — it never does arithmetic, which is my main hallucination guard. Python converts company-level revenue and margin guidance into implied PAT CAGR. I use the range bounds, not the midpoint, because research shows the lower bound is more predictive and management pads the upper bound — so I run base and bull scenarios instead of one biased number." |
| Why two horizons? | "Near-term and long-term guidance have different trust levels and feed different parts of the thesis — near-term is the quarterly checkpoint, long-term is the re-rating story. They also cross-check: if next-year growth compounded doesn't reach the multi-year aspiration, growth must accelerate, so I look for the catalyst." |
| How do you know your AI output is good? | "I hand-labelled an eval set and built an automated script tracking precision and recall across every prompt version. And the decision layer shows verbatim evidence inline, so every number is traceable to a quote." |
| How did your extraction scope evolve? | "I originally gated extraction on a 4-quarter trackability rule, then realised that conflated two jobs — credibility scoring needs near-term verifiable numbers, but the re-rating signal is often a multi-year aspiration. I split it into a two-gate model: a broad 'is this falsifiable eventually' extraction gate, and a tagging layer that routes each item to the right scoring layer." |
| Why does credibility scoring matter? | "~40% of Indian small caps miss guidance vs ~25% for large caps. Without filtering for past delivery, the list fills with chronic over-promisers. Credibility at 35% weight is the most important filter — and the highest-alpha layer I'm building next." |
| How do you keep ground truth trustworthy? | "LLM-proposed but human-adjudicated. Two strong cross-family models propose high-recall candidates; I manually verify every item against the source PDF. I never trust LLM-generated GT directly." |

---

## Known Hard Problems

### Diverse / conflicting guidance → one comparable number
Different statement shapes (revenue, margin, capacity, aspiration, segment) can't be compared directly. **Fix:** the decision layer converts only company-level revenue + margin guidance via a single deterministic rule, splits by horizon, and runs Base/Bull scenarios. Everything unconvertible is flagged as Other Signals — not forced into a fabricated number.

### Segment-Level Guidance Verification
Multi-segment companies guide on segment metrics that don't match Screener.in. **Fix:** restrict automated scoring to company-level revenue and EBITDA/PBDIT margin. Segment guidance is extracted, tagged `credibility_scorable: false`, and surfaced in Other Signals.

### Scanned PDFs
~10–15% of concall PDFs are scanned images. Fix for v1: skip and flag. OCR in Phase 3.

### LLM Hallucination
LLM may invent a number. **Fix:** LLM never does arithmetic — Python does all calculation; passages must be verbatim; spot-check 10–15 companies per quarter against transcripts.

### Credibility Scoring Needs History
Layer 3 needs 2–4 quarters of history. Fix: backfill 3–5 companies before going live (future version).

### Company Name Matching
Transcript name vs Screener.in ticker. Fix: one-time mapping table in Phase 3.

---

## Cost

At ~600 transcripts/quarter and ~15k input / ~1.5k output tokens per transcript, per-quarter API cost is negligible. The decision layer is pure Python — zero marginal cost. Quality, not cost, is the optimization axis at this scale.

| Tool | Cost |
|---|---|
| LLM API (current candidates) | ~$10–40 per quarter for 600 companies (lower with batch + caching) |
| Screener.in Premium | ₹4,999/year |
| PostgreSQL | Free (Docker local) |
| Streamlit | Free |
| AWS deployment | ~$5-10/month |

---

## Current Status

Scope is the two-gate extraction model (v1.1) PLUS the v1 decision layer (v1.2, this document). **Active goal: build the usable v1 ranked screener in 2 days** — finish extraction on the eval set, write the deterministic conversion script, run on 20–30 real transcripts, and generate the ranked Base/Bull PAT-CAGR table. Detailed steps in **plan.md** (Steps 6–8 + the 2-day sequence). Future versions (credibility, valuation, automation) are recorded as ideas only and built solely if v1 proves useful.

### Historical reference — pre-two-gate status (kept for the record)

**Earlier snapshot (PROJECT.md v1.0):** Phase 1 v1 — prompt iteration in progress (prompt_v4 complete); GT v3 finalised (4 items, Asian Paints Q4 FY26, pre-two-gate structure); best recall 55% (prompt_v3); best precision 100% (prompt_v4); best self-sufficiency 5/8 (prompt_v4).

**Later snapshot (CLAUDE.md, same arc):** prompt iteration continued through prompt_v8 (9 runs); final recall 75%, precision 67%, on the same 4-item Asian Paints v3 GT.

Neither snapshot is directly comparable to upcoming runs — the GT structure and extraction scope both changed (two-gate model, horizon/level/track tags). Retained as a record of how the prompt evolved, not as a current benchmark.

---

Project started June 2026.
