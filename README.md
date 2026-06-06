# Concall Intelligence — Indian Equity Screener

An automated pipeline that scans Indian company earnings call transcripts, extracts quantifiable management guidance, scores it on specificity, credibility and valuation, and surfaces the top companies worth deep research every quarter.

Built for Indian retail investors who want an information edge in mid and small cap stocks.

---

## The Problem

~600-900 Indian companies publish earnings call transcripts every quarter. Almost nobody outside institutional investors reads them. The companies where management gives specific, quantifiable growth guidance but the market has not priced it in yet — especially in mid and small caps — represent the best asymmetric opportunities. Finding them manually is impossible at scale.

---

## What It Does

- Downloads concall PDFs from BSE/NSE filings every quarter
- Extracts only quantifiable forward-looking guidance (number + timeframe required)
- Tracks whether management actually delivered on past guidance
- Cross-references guidance with current valuation data
- Outputs a ranked list of 30-50 companies worth individual research

This is a screening tool, not a buy signal.

---

## Scoring Framework

Each company is scored across four layers:

| Layer | Weight | What It Measures |
|---|---|---|
| Guidance Specificity | 15% | Does management give actual numbers or just vibes? |
| Guidance Ambition | 20% | How aggressive is guidance vs current performance and sector peers? |
| Management Credibility | 35% | Did they deliver on what they promised last quarter? |
| Valuation Discount | 25% | Is the stock cheap relative to the growth being guided? |

Credibility carries the most weight. Indian promoter-run companies are notoriously aspirational — filtering by past delivery is the most important signal.

---

## Tech Stack

- LLM: OpenAI API (gpt-4o-mini for extraction, gpt-4o for scoring)
- Backend: FastAPI + PostgreSQL + pgvector
- ORM: SQLAlchemy
- PDF Reading: pypdf
- Valuation Data: Screener.in Premium export
- UI: Streamlit
- Observability: Langfuse

---

## Build Phases

### Phase 1 — AI Engineering Foundation

| Version | What It Does | Status |
|---|---|---|
| v1 | Extract guidance from one transcript with eval | In Progress |
| v2 | Structured output + automated eval pipeline + PostgreSQL | Planned |
| v3 | Multi-transcript RAG + semantic search across quarters | Planned |

### Phase 2 — Screener Core

| Version | What It Does | Status |
|---|---|---|
| v4 | Scoring engine — specificity and ambition layers | Planned |
| v5 | Credibility tracker — promise vs actual across quarters | Planned |
| v6 | Valuation integration + ranked output | Planned |

### Phase 3 — Full Automation

| Version | What It Does | Status |
|---|---|---|
| v7 | BSE/NSE automated pipeline — 600+ companies per quarter | Planned |
| v8 | Agent + Streamlit dashboard + deployment | Planned |

---

## Extraction Criteria

A statement is only extracted if it answers: can I check whether management delivered on this within 4 quarters?

Extracted: revenue guidance, margin targets, volume growth percentages, capex commitments, project commissioning timelines, order book values, pricing guidance with percentages.

Ignored: macro optimism, vague confidence, demand commentary without numbers, competitive commentary, past quarter explanations.

---

## Evaluation

Every prompt version is scored against a hand-labelled ground truth set using precision and recall. Retrieval quality is evaluated separately from generation quality. All scores tracked in eval_log.md.

Current best: Precision 100%, Recall 55% (prompt_v4).

---

## Cost

~₹500-600/month ongoing after setup. OpenAI API costs ~$5-15 per full quarterly run across 600 companies.

---

## Setup

```bash
git clone https://github.com/harshchandak/concall-intelligence
cd concall-intelligence
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env
```

---

Project started June 2026.
