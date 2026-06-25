# Concall Intelligence — Indian Equity Screener
## Project Document v1.1

> v1.1 change log: Extraction scope redefined. The "trackable within 4 quarters" rule is no longer an extraction gate — it is a tag controlling automated credibility scoring only. Extraction now captures all *falsifiable-eventually* forward-looking statements (number/threshold + timeframe, any horizon), including multi-year aspirations and segment-level binary commitments. See "Extraction Criteria" below. Model references updated (gpt-4o retired). All v1.0 sections retained — see "Current Status" for the historical record.

---

## The Problem Being Solved

Indian retail investors cannot efficiently find companies where management is projecting strong future growth but the stock is currently undervalued. The information asymmetry exists because:

- 4,600+ companies are listed on NSE/BSE
- ~600–900 publish concall transcripts every quarter
- Almost nobody outside institutional investors reads these transcripts
- No existing tool scans ALL concall transcripts, extracts forward-looking guidance, and cross-references it with current valuation to produce a ranked shortlist

The edge: companies where management gives specific, quantifiable positive guidance — short-term OR a bullish multi-year vision — but the market hasn't priced it in yet. Aggressive long-horizon targets are the primary re-rating catalyst: when a previously slow-growing company articulates a big quantified outlook, the market starts pricing it ahead of delivery.

---

## What This Project Does

An automated pipeline that:

1. Downloads concall transcript PDFs from BSE/NSE filings every quarter
2. Extracts only meaningful, falsifiable forward-looking guidance using an LLM
3. Tracks whether management delivered on past near-term guidance (credibility scoring)
4. Cross-references guidance with current valuation data
5. Outputs a ranked list of the top 30–50 companies worth individual deep research

This is a screening tool, not a buy signal. The output is a shortlist for further human research.

Target universe: Companies with market cap ₹500 crore to ₹8,000 crore. Small and mid cap focus. This is where the information edge is highest — thin institutional coverage, simpler single-business P&Ls, and management guidance that maps cleanly to company-level financial metrics. Large caps are used for testing and eval only.

---

## Extraction Criteria — What Gets Extracted (Two-Gate Model)

Handling is split into two gates. **Gate 1** = extract or not (broad, structural, industry-agnostic). **Gate 2** = tag, which routes each item to the right scoring layer. The 4-quarter and Screener-matchability constraints belong to Gate 2 ONLY — they do not restrict extraction.

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

(The above table preserves every example from the original v1.0 extraction-criteria list — order book, capacity addition, capex, volume, pricing, project timelines — now joined by the two new categories that triggered the v1.1 scope correction: multi-year aspirations and segment binary events.)

### Gate 2 — Tags
- `horizon`: near (≤4Q) | medium (1–2Y) | long (3Y+)
- `level`: company | segment | geography
- `track`: A (numeric guidance) | B (binary commitment event)
- `credibility_scorable`: true only when level=company AND metric ∈ {Revenue, EBITDA/PBDIT margin, PAT, PBT, EPS} AND horizon=near AND Screener-matchable; false otherwise.

### Ignore These (fail Gate 1)
- Macro optimism: "India's growth story remains strong"
- Vague confidence: "We are confident of delivering good results"
- Demand commentary without numbers: "Demand environment is positive"
- Competitive commentary: "Competitive intensity will continue"
- Explanations of past quarter performance

---

## Scoring Framework (4 Layers)

### Layer 1: Guidance Specificity (15% weight)
Does management give actual numbers or just vibes?
- Score 1: Pure vague optimism — "we are very positive"
- Score 3: Directional with reasoning — "margins should improve, expecting 14-16%"
- Score 5: Fully specific — "FY27 revenue ₹800-900 crore, EBITDA 17-18%"

### Layer 2: Guidance Ambition — Implied Growth (20% weight)
How aggressive is the guidance relative to current performance? **This layer consumes ALL extracted items, especially long-horizon aspirations — it is the re-rating signal.**
- Compute implied growth rate: Guided figure ÷ Trailing 12-month actual (for long-horizon, annualize: e.g. 3x in 4 years ≈ 32% CAGR)
- Compare against sector median guided growth rate
- A company guiding 40% growth when sector median is 12% = high ambition score

### Layer 3: Management Credibility (35% weight — MOST IMPORTANT)
Did they deliver on what they said? **This layer consumes ONLY `credibility_scorable: true` items — near-term, company-level P&L guidance.**
- For each past guidance item: Delivery Ratio = Actual Reported / What Was Guided
- Average across last 4 quarters
- Ratio 0.95–1.05 → Score 5 (consistently accurate)
- Ratio 0.80–0.95 → Score 3 (slight miss, acceptable)
- Ratio below 0.75 → Score 1 (serial over-promiser, discard)

This is the most critical filter. Indian promoter-run companies are notoriously aspirational. The Ambition layer rewards a bold "3x by FY29"; the Credibility layer is what tells you whether to believe it. A bullish vision plus a clean near-term track record is shortlist gold; the same vision from a chronic short-term misser is a discard. That contrast only works because both statement types are extracted and tagged.

**Credibility scoring scope:** Automated credibility scoring is computed only on company-level revenue and EBITDA/PBDIT margin guidance, matched against Screener.in quarterly exports. Segment-level guidance (volume growth, sub-segment margins, segment breakeven) and binary events (commissioning timelines) are extracted and tagged but excluded from automated credibility scoring — they require manual verification from subsequent transcripts or BSE segment disclosures.

### Layer 4: Valuation Discount (25% weight)
Is the stock cheap relative to the growth being guided?
Forward PEG = Current PE ÷ Guided Revenue Growth Rate
- PEG below 0.5 → Score 5 (very cheap for guided growth)
- PEG 0.5–1.0 → Score 3 (fairly valued)
- PEG above 1.5 → Score 1 (expensive relative to guidance)

### Composite Score Formula
```
Final Score = (Specificity × 0.15) + (Ambition × 0.20) +
              (Credibility × 0.35) + (Valuation Discount × 0.25)
```
Sort all companies descending. Top 30–50 = research shortlist.

### Bonus Signal (Add in Phase 3)
If promoter has been buying shares in open market in the last quarter: add +0.5 to Final Score.

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
Store in PostgreSQL (with pgvector for semantic search)
      ↓
Pull Valuation Data (Screener.in export)
      ↓
Run Scoring Logic
      ↓
Ranked Output (Streamlit dashboard)
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| LLM API | OpenAI + Anthropic. gpt-4o RETIRED (early 2026). Current extraction candidates: Claude Sonnet 4.6, GPT-5.4. Re-evaluate one-step vs two-step on current models. |
| Backend | FastAPI |
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy |
| PDF Reading | pypdf |
| Env Management | python-dotenv |
| Valuation Data | Screener.in Premium export |
| UI | Streamlit |
| Agents | Vanilla loop first, then LangGraph |
| Observability | Langfuse |

---

## Version Strategy

Build in phases. Each phase ships something usable on its own. Never start the next phase until the current one is complete and committed.

### PHASE 1 — AI Engineering Foundation
Goal: Build and validate the extraction engine. Interview-ready after this phase.

#### v1 — Extract guidance from one transcript
- Read a PDF transcript into text
- Write a prompt that extracts falsifiable forward-looking guidance under the two-gate model
- Call the LLM and print results
- Compare against hand-adjudicated ground truth
- Iterate prompt until acceptance thresholds met (see plan.md), all passages self-sufficient
- Done when: one command produces clean, self-sufficient, correctly-tagged passages

#### v2 — Structured output + eval pipeline + PostgreSQL
- Define Pydantic schema matching the GT structure (incl. horizon/level/track/credibility_scorable)
- Force structured JSON output from the LLM
- Build automated eval script: precision and recall computed programmatically
- Save extracted records to PostgreSQL
- Track prompt versions with scores in eval log
- Done when: extraction runs on 3 transcripts, records land in PostgreSQL, eval prints scores automatically

#### v3 — Multi-transcript RAG
- Chunk transcripts by speaker turn; embed; store in pgvector
- Semantic + hybrid search with reranking; retrieval evaluated separately from generation
- Done when: "What has company X said about margins over 4 quarters?" returns correct sourced answer

### PHASE 2 — Screener Core
- v4: Scoring engine (Layer 1 specificity + Layer 2 ambition)
- v5: Credibility tracker (Layer 3, promise vs actual across 4 quarters)
- v6: Valuation integration + Layer 4 + composite ranked output

### PHASE 3 — Full Automation + Production
- v7: BSE/NSE automated download pipeline (200+ then 600+ companies; flag scanned PDFs, add OCR later)
- v8: Agent orchestration + Streamlit dashboard + AWS deployment

---

## Interview Talking Points (Grows With Each Version)

| When they ask | You can say |
|---|---|
| How do you know your AI output is good? | "I hand-labelled an eval set of statements and built an automated script tracking precision and recall across every prompt version" |
| How did you choose your extraction criteria? | "I started with all forward-looking statements, then realised untrackable ones pollute the credibility scoring — so I tightened to number + timeframe required" |
| Tell me about your RAG setup | "Chunked by speaker turn to preserve meaning and speaker identity, hybrid search plus reranking, retrieval evaluated separately from generation" |
| Have you built agents? | "Vanilla loop first to understand the mechanics, then LangGraph for state management" |
| What does this project actually do? | "It scans 600+ Indian company earnings calls every quarter, extracts quantifiable management guidance, scores it on specificity, ambition, credibility and valuation, and surfaces the top 30-50 companies worth deeper research" |
| Why does credibility scoring matter? | "Indian promoter-run companies are notoriously aspirational. Without filtering for past delivery, your output list fills with chronic over-promisers. Credibility at 35% weight is the most important filter." |
| How did your extraction scope evolve? | "I originally gated extraction itself on a 4-quarter trackability rule. I realised that conflated two different jobs — credibility scoring needs near-term, verifiable numbers, but the actual re-rating signal I'm trying to capture is often a multi-year aspirational target. I split it into a two-gate model: a broad, industry-agnostic 'is this falsifiable eventually' extraction gate, and a separate tagging layer that routes each item to the right scoring layer — ambition vs credibility." |
| How do you keep ground truth trustworthy? | "Ground truth is LLM-proposed but human-adjudicated. I use two strong, cross-family models to propose candidates biased toward high recall, then manually verify every item against the source PDF. I never trust LLM-generated ground truth directly — scoring a cheap model against GT built by a model in the same family just measures agreement, not correctness." |

---

## Known Hard Problems

### Segment-Level Guidance Verification
Multi-segment companies guide on segment-level metrics that cannot be reliably matched against Screener.in exports.
Fix: Restrict automated credibility scoring to company-level revenue and EBITDA/PBDIT margin. Segment-level guidance is extracted and tagged `credibility_scorable: false` — available for human review, excluded from automated scoring. This is also why the target universe is ₹500cr–8,000cr, where single-business P&Ls dominate.

### Scanned PDFs
~10–15% of concall PDFs are scanned images. Fix for V1: skip and flag. Add OCR in Phase 3.

### LLM Hallucination
LLM may invent a number. Fix: spot-check 10–15 companies from output against transcripts each quarter; passages must be verbatim.

### Credibility Scoring Needs History
Layer 3 needs 2–4 quarters of history. Fix: backfill 3–5 companies before going live.

### Company Name Matching
Transcript name vs Screener.in ticker. Fix: one-time mapping table in Phase 3.

---

## Cost

At ~600 transcripts/quarter and ~15k input / ~1.5k output tokens per transcript, per-quarter API cost is negligible (single digits to low tens of dollars even on premium models, before batch/caching discounts). Quality, not cost, is the optimization axis at this scale.

| Tool | Cost |
|---|---|
| LLM API (current candidates) | ~$10–40 per quarter for 600 companies (lower with batch + caching) |
| Screener.in Premium | ₹4,999/year |
| PostgreSQL | Free (Docker local) |
| Streamlit | Free |
| AWS deployment | ~$5-10/month |

Total ongoing: roughly ₹1,000–3,500/month after setup, depending on which LLM tier is chosen for production (the v1.0 estimate of ₹500-600/month assumed gpt-4o-mini pricing, which is no longer current — see Tech Stack).

---

## Current Status

Scope redefined to the two-gate model (this document, v1.1; see "Extraction Criteria" above). Active work: rebuild the eval set and ground-truth files under the new scope, then run the model + architecture bake-off. Detailed next steps are in **plan.md**.

### Historical reference — pre-two-gate status (kept for the record)

Two snapshots exist from the prior phase, at different points in the prompt-iteration arc — both preserved here rather than discarded:

**Earlier snapshot (PROJECT.md v1.0):**
- Phase 1, v1 — Prompt iteration in progress (prompt_v4 complete)
- Ground truth: v3 finalised — 4 items from Asian Paints Q4 FY26, structure locked (pre-two-gate structure — no horizon/level/track tags)
- Best recall so far: 55% (prompt_v3)
- Best precision so far: 100% (prompt_v4)
- Best self-sufficiency: 5/8 passages (prompt_v4)
- Next action at the time: iterate prompt v5 targeting recall ≥ 70%
- Next milestone at the time: Recall ≥ 70% + Precision ≥ 80% + all passages self-sufficient → v1 done → move to v2

**Later snapshot (CLAUDE.md, same arc, v1 subsequently completed):**
- Prompt iteration continued through prompt_v8 (9 runs total); final recall 75%, final precision 67%, on the same 4-item Asian Paints v3 ground truth
- Full detail in CLAUDE.md → Current Status → "Historical reference — Phase 1, v1 outcome"

Neither snapshot is directly comparable to upcoming eval runs — the ground truth structure and extraction scope have both changed (two-gate model, horizon/level/track tags added). They're retained as a record of how the prompt evolved, not as a current benchmark.

---

Project started June 2026.
