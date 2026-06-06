# Concall Intelligence — Indian Equity Screener
## Project Document v1.0

---

## The Problem Being Solved

Indian retail investors cannot efficiently find companies where management is projecting strong future growth but the stock is currently undervalued. The information asymmetry exists because:

- 4,600+ companies are listed on NSE/BSE
- ~600–900 publish concall transcripts every quarter
- Almost nobody outside institutional investors reads these transcripts
- No existing tool scans ALL concall transcripts, extracts forward-looking guidance, and cross-references it with current valuation to produce a ranked shortlist

The edge: companies where management gives specific, quantifiable positive guidance but the market hasn't priced it in yet — especially in mid and small cap where institutional research coverage is thin.

---

## What This Project Does

An automated pipeline that:

1. Downloads concall transcript PDFs from BSE/NSE filings every quarter
2. Extracts only meaningful, quantifiable forward-looking guidance using an LLM
3. Tracks whether management delivered on past guidance (credibility scoring)
4. Cross-references guidance with current valuation data
5. Outputs a ranked list of the top 30–50 companies worth individual deep research

This is a screening tool, not a buy signal. The output is a shortlist for further human research.

---

## Extraction Criteria — What Gets Extracted

### Extract These (Must Be Falsifiable Within 4 Quarters)

| Type | Example |
|---|---|
| Revenue guidance | "We expect ₹800–900 crore revenue in FY27" |
| Margin guidance | "EBITDA margins to expand to 17–18% from current 13%" |
| Order book | "Executable order book of ₹1,200 crore over 18 months" |
| Capacity addition | "New plant commissioned in Q3, adding 40% capacity" |
| Capex commitment | "₹250 crore capex over 2 years, ₹80 crore already deployed" |
| Volume guidance | "We expect 8-10% volume growth going forward" |
| Pricing guidance | "Further price increases planned, 10.5% implemented till now" |
| Project timelines | "VAM-VAE plant commissioning in H1 FY27" |

### Ignore These (Low Signal / Not Trackable)

- Macro optimism: "India's growth story remains strong"
- Vague confidence: "We are confident of delivering good results"
- Demand commentary without numbers: "Demand environment is positive"
- Competitive commentary: "Competitive intensity will continue"
- Explanations of past quarter performance

**Core extraction rule:** A statement must have a number AND a timeframe, OR a specific commitment that can be checked within 12 months. If you cannot verify delivery next quarter, it is noise.

---

## Scoring Framework (4 Layers)

### Layer 1: Guidance Specificity (15% weight)
Does management give actual numbers or just vibes?

- Score 1: Pure vague optimism — "we are very positive"
- Score 3: Directional with reasoning — "margins should improve, expecting 14-16%"
- Score 5: Fully specific — "FY27 revenue ₹800-900 crore, EBITDA 17-18%"

### Layer 2: Guidance Ambition — Implied Growth (20% weight)
How aggressive is the guidance relative to current performance?

- Compute implied growth rate: Guided figure ÷ Trailing 12-month actual
- Compare against sector median guided growth rate
- A company guiding 40% growth when sector median is 12% = high ambition score

### Layer 3: Management Credibility (35% weight — MOST IMPORTANT)
Did they deliver on what they said last quarter?

- For each past guidance item: Delivery Ratio = Actual Reported / What Was Guided
- Average across last 4 quarters
- Ratio 0.95–1.05 → Score 5 (consistently accurate)
- Ratio 0.80–0.95 → Score 3 (slight miss, acceptable)
- Ratio below 0.75 → Score 1 (serial over-promiser, discard)

This is the most critical filter. Indian promoter-run companies are notoriously aspirational. Without credibility filtering, the output list fills up with chronic over-promisers.

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
Extract Text from PDFs (pypdf)
      ↓
Send to OpenAI API → Get Structured JSON (guidance data)
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
| LLM API | OpenAI (gpt-4o-mini for extraction, gpt-4o for scoring) |
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

---

### PHASE 1 — AI Engineering Foundation
Goal: Build and validate the extraction engine. Interview-ready after this phase.

#### v1 — Extract guidance from one transcript (IN PROGRESS)
- Read a PDF transcript into text
- Write a prompt that extracts quantifiable forward-looking guidance
- Call OpenAI API and print results
- Compare against hand-labelled ground truth (20 statements)
- Iterate prompt until recall ≥ 70%, precision ≥ 80%, all passages self-sufficient
- Done when: one command runs and produces clean, self-sufficient passages

#### v2 — Structured output + eval pipeline + PostgreSQL
- Define Pydantic schema: company, quarter, speaker, passage, metric, value, timeline, confidence
- Force structured JSON output from LLM
- Build automated eval script: precision and recall calculated programmatically
- Save extracted records to PostgreSQL
- Track prompt versions with scores in eval log
- Done when: extraction runs on 3 transcripts, records land in PostgreSQL, eval script prints scores automatically

#### v3 — Multi-transcript RAG
- Chunk transcripts by speaker turn
- Embed chunks using OpenAI embedding model
- Store vectors in pgvector
- Semantic search: query across all loaded transcripts by meaning
- Add hybrid search (semantic + keyword) and reranking
- Evaluate retrieval separately from generation
- Done when: "What has Asian Paints said about margins over 4 quarters?" returns correct sourced answer

---

### PHASE 2 — Screener Core
Goal: Build the scoring engine and credibility tracker. Personal use starts here.

#### v4 — Scoring engine
- Implement Layer 1 (specificity) and Layer 2 (ambition) scoring
- Normalise guidance ambition against sector median
- Score each extracted guidance item automatically
- Run on 5 companies you know well — sanity check output manually
- Done when: 5 companies scored, output makes intuitive sense

#### v5 — Credibility tracker (promise vs actual)
- Match earlier guidance items against later reported results
- Compute delivery ratio per guidance item
- Implement Layer 3 (credibility) scoring across 4 quarters of history
- Backfill 2–4 quarters of Asian Paints and Infosys data for testing
- Done when: credibility score computed for at least 2 companies with real history

#### v6 — Valuation integration + ranked output
- Pull valuation data from Screener.in export (PE, market cap, sector)
- Compute Forward PEG per company
- Implement Layer 4 (valuation discount) scoring
- Combine all 4 layers into composite score
- Output ranked list as CSV or simple table
- Done when: end-to-end score produced for 5 companies, output ranked correctly

---

### PHASE 3 — Full Automation + Production
Goal: Scale to 600+ companies, automate the pipeline, ship the dashboard.

#### v7 — BSE/NSE automated pipeline
- Script to download all concall PDFs from BSE/NSE filings each quarter
- Handle scanned PDFs (flag as unprocessed for V1, add OCR in V2)
- Build company name → NSE ticker mapping table (one-time, tedious but necessary)
- Process first full quarter: target 200+ companies
- Done when: pipeline runs overnight and processes a full quarter automatically

#### v8 — Agent + Streamlit dashboard + deployment
- Agent that orchestrates: download → extract → score → rank without manual steps
- Streamlit dashboard: ranked table with filters by sector, market cap, score
- Each row shows: company, guidance summary, guided growth %, PE, PEG, credibility score, final score
- Deploy on AWS (certified — use what you know)
- Done when: dashboard is live at a public URL, runs itself every quarter

---

## Interview Talking Points (Grows With Each Version)

| When they ask | You can say |
|---|---|
| How do you know your AI output is good? | "I hand-labelled an eval set of 20 statements and built an automated script tracking precision and recall across every prompt version" |
| How did you choose your extraction criteria? | "I started with all forward-looking statements, then realised untrackable ones pollute the credibility scoring — so I tightened to number + timeframe required" |
| Tell me about your RAG setup | "Chunked by speaker turn to preserve meaning and speaker identity, hybrid search plus reranking, retrieval evaluated separately from generation" |
| Have you built agents? | "Vanilla loop first to understand the mechanics, then LangGraph for state management" |
| What does this project actually do? | "It scans 600+ Indian company earnings calls every quarter, extracts quantifiable management guidance, scores it on specificity, ambition, credibility and valuation, and surfaces the top 30-50 companies worth deeper research" |
| Why does credibility scoring matter? | "Indian promoter-run companies are notoriously aspirational. Without filtering for past delivery, your output list fills with chronic over-promisers. Credibility at 35% weight is the most important filter." |

---

## Known Hard Problems

### Scanned PDFs
~10-15% of concall PDFs are scanned images. Standard text extraction fails.
Fix for V1: Skip and flag. Add OCR (Tesseract or AWS Textract) in Phase 3.

### LLM Hallucination
LLM will occasionally invent a number not in the transcript.
Fix: Spot-check 10-15 companies from output against actual transcript each quarter.

### Credibility Scoring Needs History
Layer 3 requires 2-4 quarters of historical data.
Fix: Backfill manually for 3-5 companies before going live. System builds history automatically after that.

### Company Name Matching
Transcript says "Voltamp Transformers Ltd", Screener.in says "VOLTAMPQ".
Fix: One-time mapping table built in Phase 3 Week 1.

---

## Cost

| Tool | Cost |
|---|---|
| OpenAI API (gpt-4o-mini) | ~$5-15 per quarter for 600 companies |
| Screener.in Premium | ₹4,999/year |
| PostgreSQL | Free (Docker local) |
| Streamlit | Free |
| AWS deployment | ~$5-10/month |

Total ongoing: ~₹500-600/month after setup.

---

## Current Status

Phase 1, v1 — Prompt iteration in progress (prompt_v4 complete)

Ground truth: 20 statements labelled from Asian Paints Q4 FY26
Best recall so far: 55% (prompt_v3)
Best precision so far: 100% (prompt_v4)
Best self-sufficiency: 5/8 passages (prompt_v4)

Next milestone: Recall ≥ 70% + Precision ≥ 80% + all passages self-sufficient → v1 done → move to v2

---

Project started June 2026.
