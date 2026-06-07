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

Built for personal use by an Indian retail investor with a ₹40L direct equity portfolio. The goal is to surface mid and small cap companies where management is guiding strong growth but the market has not priced it in yet.

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

## Extraction Criteria — Critical

A guidance statement is only extracted if it is trackable within 4 quarters. It must have a number AND a timeframe, or a specific commitment that can be verified at the next results.

### Extract these:
- Revenue guidance with numbers and timeframe
- Margin guidance with target range
- Volume growth with percentage
- Capex commitments with amounts and timelines
- Project commissioning timelines
- Order book / contract announcements with values
- Pricing guidance with percentages

### Never extract these:
- Macro optimism without company-specific commitment
- Vague confidence statements
- Demand commentary without numbers
- Competitive commentary
- Past quarter explanations

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
- credibility_scorable # true/false
```

credibility_scorable = true only when:
- Metric is company-level revenue or EBITDA/PBDIT margin
- Value is directly matchable against Screener.in quarterly export
- No segment-level or derived metrics

Current ground truth file: data/asian_paints_Q4_FY26_ground_truth_v3.txt

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM API | OpenAI (gpt-4o-mini for extraction, gpt-4o for scoring) |
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
- v1: Extract guidance from one transcript (IN PROGRESS)
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

Phase 1, v1 — Prompt iteration in progress

- Prompt versions completed: v1, v2, v3, v4
- Best recall: 55% (prompt_v3)
- Best precision: 100% (prompt_v4)
- Best self-sufficiency: 5/8 passages (prompt_v4)
- Ground truth: v3 finalised (4 items, Asian Paints Q4 FY26) — structure locked
- Next action: Iterate prompt v5 targeting recall ≥ 70%
- Target to complete v1: Recall ≥ 70%, Precision ≥ 80%, all passages self-sufficient

Update this section at the start of every session.

---

## Folder Structure

```
concall-intelligence/
├── CLAUDE.md                  ← this file
├── PROJECT.md                 ← full project document
├── .env                       ← real keys, gitignored
├── .env.example               ← key names only, committed
├── .gitignore
├── README.md
├── requirements.txt
├── eval_log.md                ← prompt iteration tracking
├── main.py
├── prompts/                   ← one file per prompt version
│   ├── prompt_v1.txt
│   ├── prompt_v2.txt
│   ├── prompt_v3.txt
│   └── prompt_v4.txt
├── notes.md                   ← decisions and future implementation notes
├── data/                      ← ground truth and eval sets
│   ├── asian_paints_Q4_FY26_ground_truth_v3.txt
│   └── asian_paints_Q4_FY26_FLS.txt
├── transcripts/               ← PDF transcripts, gitignored
│   └── .gitkeep
└── venv/
```

---

## What NOT to Do

- Do not suggest LangChain — vanilla approaches preferred
- Do not suggest fine-tuning unless specifically asked
- Do not skip evaluation — every version has an eval step
- Do not build multiple versions simultaneously — finish one, commit, then move
- Do not extract vague or untrackable guidance — number + timeframe required
- Do not write code unless explicitly asked
