# CLAUDE.md — Concall Intelligence

This file gives you full context about this project. Read it at the start of every session.

---

## How to Behave

- **Do NOT write code unless explicitly asked.** Wait for "give me the code" or "show me the implementation" before writing any code.
- When asked "how do I do X" or "what's the approach" — explain the concept only. No code.
- Act as a senior AI engineer and thought partner. Help reason through decisions, explain concepts clearly, flag tradeoffs.
- Be concise and specific. Avoid generic advice. Give examples where useful.
- When reviewing code (pasted by the user), be direct and critical — point out what's wrong, what's missing, what could be better.
- Do not repeat context back unnecessarily. Get to the point.

---

## What This Project Is

**Concall Intelligence** — a tool that extracts forward-looking guidance statements from Indian company earnings call transcripts, stores them in a database, and compares what management promised against what actually happened. The headline feature is a management reliability score across quarters.

### Why an LLM

Management phrases guidance in dozens of ways — "we expect", "we are targeting", "we are confident of". Rule-based keyword extraction misses most of it. An LLM understands meaning, making it the right tool for this task.

---

## Who Is Building This

- **Name:** Harsh Chandak
- **Background:** ~5 years as a Data Engineer (JLR, Partners Group), IIT Bombay dual degree, AWS + GCP certified
- **Goal:** Build this project as a portfolio piece for AI Engineer / Senior Data Engineer roles
- **Strong in:** Python, SQL, PostgreSQL, FastAPI, SQLAlchemy, data pipelines
- **New to:** LLM APIs, RAG, agents, evaluation frameworks — learning these through this project

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM API | OpenAI API (has existing credits) |
| Backend | FastAPI |
| Database | PostgreSQL (Docker) |
| Vector Search | pgvector |
| ORM | SQLAlchemy |
| PDF Reading | pypdf |
| Env Management | python-dotenv |
| UI | Streamlit (v6) |
| Agents | Vanilla loop first, then LangGraph |
| Observability | Langfuse |

---

## Build Plan — Versions in Order

Build one version completely before starting the next. Each version is a working, committable thing.

### v1 — Extract from one transcript (Day 1)
- Read a PDF transcript into text
- Write a prompt that identifies forward-looking statements
- Call OpenAI API and print results
- Hand-label one transcript first as ground truth — compare system output against it
- **Done when:** one command runs and prints a clean list matching most of the hand-labelled statements

### v2 — Structured output + eval + PostgreSQL (Days 2–3)
- Force output into a fixed Pydantic schema (company, quarter, speaker, quote, metric, value, timeline, confidence)
- Build an eval script that measures precision and recall against hand-labelled ground truth
- Save extracted records to PostgreSQL
- Track prompt versions — change one thing at a time, record score changes
- **Done when:** extraction runs on several transcripts, records land in PostgreSQL, eval script prints precision/recall

### v3 — RAG across many transcripts (Days 4–6)
- Chunk transcripts by speaker turn (not fixed size — preserves meaning and speaker identity)
- Embed chunks using OpenAI embedding model — pick one model and stick with it
- Store vectors in pgvector (PostgreSQL extension)
- Semantic search: turn a user question into a vector, find closest chunks
- Add hybrid search (semantic + keyword) and reranking in v3.5
- Evaluate retrieval separately from generation — know which one is failing
- **Done when:** plain-English question across many transcripts returns correct, sourced answer

### v4 — Model comparison + promise vs actual (Days 7–8)
- Run eval across multiple OpenAI models — record quality, cost, latency for each
- Route cheap extraction to a smaller model, hard reasoning to a stronger one
- Build promise vs actual tracker: match earlier guidance to later reported results
- Score management reliability per company across quarters
- **Done when:** model comparison table exists in README, promise tracker working

### v5 — Agent (Days 9–10)
- Write a vanilla agent loop by hand first — no framework
- Tools: fetch_transcript(), extract_statements(), save_to_db(), query_past_guidance(), compare_promise_vs_actual()
- Add error handling, step cap (prevent infinite loops), output validation via Pydantic
- Then optionally compare with LangGraph implementation
- **Done when:** one instruction triggers full pipeline autonomously, recovers from failures, writes a log

### v6 — API + UI + monitoring (Days 11–12)
- Wrap logic in FastAPI endpoints
- Add streaming responses (token-by-token)
- Streamlit UI for non-technical access
- Langfuse for latency, cost, error rate tracking
- Real failures feed back into eval set — this is the production learning loop
- **Done when:** deployed, anyone can log in and use it, monitoring dashboard live

---

## Data Sources

- Screener.in → company page → Concalls section
- BSE/NSE India filings
- Company investor relations pages

Starting companies: **Asian Paints or Infosys** (clean transcripts, well-documented guidance, long history).

---

## Key Concepts to Know

**Forward-looking statement:** any sentence about the future — targets, expectations, guidance on revenue, margins, volumes, capex, expansion. NOT past quarter results.

**Ground truth:** hand-labelled correct answers used to score the system. Built before the system is built.

**Precision:** of what the system returned, how much was correct. Low precision = hallucination.

**Recall:** of what was actually there, how much the system found. Low recall = missing statements.

**Chunking by speaker turn:** split transcript at each speaker change, not every N words. Preserves meaning and speaker identity.

**RAG:** retrieve relevant chunks first, then generate answer from only those chunks. Solves the token limit problem.

**Model routing:** send cheap repetitive tasks (extraction) to a small model, hard reasoning (comparison) to a strong model. Cuts cost without quality loss.

---

## Current Status

🚧 **Day 1 — v1 in progress**

Update this line at the start of each session.

---

## Folder Structure

```
concall-intelligence/
├── CLAUDE.md               ← this file
├── .env                    ← real keys, gitignored
├── .env.example            ← key names only, committed
├── .gitignore
├── README.md
├── requirements.txt
├── Makefile
├── transcripts/            ← PDF transcripts, gitignored
│   └── .gitkeep
├── data/                   ← ground truth labels, eval sets
└── src/
    └── main.py
```

---

## What NOT to Do

- Do not install or suggest LangChain — vanilla approaches preferred
- Do not suggest fine-tuning unless specifically asked
- Do not skip evaluation — every version has an eval step
- Do not build multiple versions simultaneously — finish one, commit, then move to next
- Do not write code unless explicitly asked
