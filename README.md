# Concall Intelligence

A tool that extracts forward-looking guidance statements from Indian company earnings call transcripts, tracks them over time, and compares what management promised against what actually happened.

---

## What It Does

- Extracts management guidance from concall transcripts (revenue targets, margin expectations, capex plans, expansion timelines)
- Stores structured records per company and quarter in PostgreSQL
- Answers natural language questions across many quarters and companies using semantic search
- Compares promises made in earlier quarters against actual reported results
- Scores management guidance reliability over time

---

## Why an LLM

Management phrases guidance in dozens of ways — "we expect", "we are targeting", "we are confident of". Rule-based keyword search misses most of it. An LLM understands meaning, not just words, making it the right tool for this task.

---

## Tech Stack

- **Backend:** FastAPI + PostgreSQL
- **AI:** Anthropic Claude API (extraction, comparison, generation)
- **Vector Search:** pgvector (semantic search across transcripts)
- **Evaluation:** Custom eval framework tracking precision and recall across prompt versions
- **Agents:** Vanilla agent loop + LangGraph
- **UI:** Streamlit
- **Observability:** Langfuse (latency, cost, error rate per request)

---

## Build Versions

| Version | Capability |
|---|---|
| v1 | Extract guidance from one transcript |
| v2 | Structured output + eval pipeline + PostgreSQL storage |
| v3 | RAG across many transcripts — semantic search |
| v4 | Model comparison, routing, promise vs actual tracker |
| v5 | Agent that fetches, extracts, stores and reports autonomously |
| v6 | FastAPI + Streamlit UI + streaming + monitoring |

---

## Data Sources

Transcripts sourced from Screener.in, BSE/NSE filings, and company investor relations pages. Initial focus: Asian Paints, Infosys, HDFC Bank (4+ quarters each).

---

## Evaluation

Every prompt version is scored against a hand-labelled ground truth set using precision and recall. Retrieval quality is evaluated separately from generation quality. All scores are tracked across versions.

---

## Status

🚧 In progress — currently on v1.
