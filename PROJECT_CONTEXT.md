# PROJECT_CONTEXT.md — Master Shared Context

> **Single source of truth, agent-agnostic.** Both Claude Code (`CLAUDE.md`) and
> OpenAI Codex (`AGENTS.md`) reference this file. Edit project facts HERE, not in
> the tool-specific files. The tool files hold only behavior/config that differs
> per agent.

---

## 1. Project Overview

**Concall Intelligence — Indian Equity Screener.** An automated pipeline that
downloads Indian company earnings-call transcripts from BSE/NSE, extracts
quantifiable forward-looking guidance with an LLM, **converts that guidance into
a comparable implied PAT CAGR per company (Base + Bull scenarios)**, and outputs
a ranked table of companies worth deep research.

- **For:** an Indian retail investor (₹40L direct equity), techno-fundamental.
- **Edge band:** market cap ₹500cr–₹15,000cr — thin coverage, single-business
  P&Ls, guidance that maps cleanly to company metrics.
- **Re-rating signal:** management articulating aggressive multi-year targets
  before the market prices them in.
- **This is a screening tool, not a buy signal.**

**Why the decision layer matters:** extraction alone is "a fancy PDF reader." The
decision layer turns extracted guidance into one comparable, rankable number. The
v1 definition of done is a usable ranked table — not perfect extraction.

---

## 2. Current State (as of 2026-06)

- **Active goal:** ship the usable **v1 ranked screener** (extraction + deterministic
  decision layer → sorted CSV/HTML table).
- Two parallel lines of work live in the tree:
  - **Root pipeline** — the productionizing path: `run.py` (one-shot extraction) →
    `decision.py` (CAGR table), plus the staged `pipeline/` modules.
  - **`experiments/guidance_acceleration/`** — a large research sandbox: universe
    building from Screener, bulk concall download (BSE + screener), cheap
    extraction, scoring. Self-contained `lib_*.py` helpers; treat as exploratory.
- **Models:** `gpt-4o` is **retired**. Current extraction candidates: **GPT-5.4**
  (`run.py` uses `gpt-5.4`) and **Claude Sonnet 4.6**. `main.py` still pins the
  retired `gpt-4o` — legacy, not the current path. gpt-4o-mini-class was previously
  insufficient; re-test on current models rather than carrying that forward.
- **Eval:** `eval_v2.py` scores extraction against LLM-generated ground truth
  (two-pass: propose → Opus 4.8 judge). Measures *model agreement*, not human truth.

> Docs (`CLAUDE.md`, `PROJECT.md`, `plan.md`) can lag the working tree — verify
> against the repo before relying on a claim.

---

## 3. Architecture & Module Relationships

### Root pipeline (the v1 path)
| File | Role |
|---|---|
| `run.py` | One-shot extraction. PDF → `pdfplumber` text → LLM (GPT-5.4) → `output/{company}_guidance.json`. Pydantic-validated. |
| `main.py` | **Legacy** single-file extractor (pins retired `gpt-4o`). Not the current path. |
| `decision.py` | **Deterministic, zero-LLM.** Reads `output/*_guidance.json` + Screener financials → implied PAT CAGR Base/Bull → `output/ranked_table.csv`. All arithmetic lives here. |
| `schemas.py` | Pydantic models (`GuidanceItem`, `ExtractionResult`, `GuidanceRecord`). Mirrors the ground-truth structure. |
| `screener.py` | Fetches current P&L from screener.in (`requests` + `BeautifulSoup`); `TICKER_MAP` + standalone overrides. |
| `eval_v2.py` / `eval.py` | Score extraction vs ground truth (strict/soft precision/recall + per-tag agreement). |
| `models.py` / `database.py` | SQLAlchemy models + DB session (PostgreSQL, future v2). |

### Staged pipeline (`pipeline/`)
`stage0_segmenter.py` (speaker/turn segmentation) → `stage1_filter.py` (candidate
filter: digit/temporal/commitment lexicons) → `stage2_extractor.py` (structured
extraction) → `stage4_validator.py` (deterministic validate/normalize/dedup).
Specs for every stage live in `specs/SPEC_STAGE*.md`.

### Research sandbox (`experiments/guidance_acceleration/`)
Universe build (`build_universe*.py`), bulk download (`download_concalls.py`,
`download_screener.py`, `lib_bse.py`), cheap extraction (`extract_cheap.py`),
scoring (`score.py`, `forward_growth.py`). Has its own `PLAN.md` / `HANDOFF.md` /
`README.md`. Self-contained — don't entangle with the root v1 path.

### Data flow (v1)
```
transcripts/*.pdf → run.py → output/{company}_guidance.json
                                      │
            screener.py (P&L) ────────┤
                                      ▼
                            decision.py → output/ranked_table.csv
```

---

## 4. Domain Rules (do not violate)

### Two-Gate extraction model
- **Gate 1 — Extract?** Keep a statement iff ALL: (1) forward-looking,
  (2) specific (number / threshold / binary outcome), (3) has a timeframe.
  Governing principle: **falsifiable eventually** (number-or-threshold AND a date).
  Horizon does NOT gate extraction — a "3x by FY29" aspiration IS extracted.
- **Gate 2 — Tag:** `horizon` (near ≤4Q | medium 1–2Y | long 3Y+), `level`
  (company | segment | geography), `track` (A numeric | B binary), and
  `credibility_scorable`.
- `credibility_scorable = true` ONLY when: `level=company` AND
  metric ∈ {Revenue, EBITDA/PBDIT margin, PAT, PBT, EPS} AND `horizon=near` AND
  directly matchable to a Screener quarterly export. Everything else (aspirations,
  segment/geography, Track B events, volume/capex) → `false`.
- **"4 quarters" is a TAG, never an extraction gate.**

### Decision layer (v1) — the one conversion rule
```
Future PAT       = Guided Revenue × Guided Net Margin
Implied PAT CAGR = (Future PAT / Current PAT) ^ (1 / years) − 1
```
- **Base** = lower revenue bound × current trailing net margin.
- **Bull** = upper revenue bound × upper guided net-margin bound.
- Use **bounds, never midpoints**. Ranges annualise via `^(1/years)`.
- Only `level=company` items enter CAGR numbers; segment/geography → "Other Signals".
- Two horizon blocks (Near ≤1yr, Long >1yr). **Base + Bull only — no bear case in v1.**

### The five accuracy rules
1. **LLM extracts/classifies only — Python does ALL arithmetic** (hallucination guard).
2. Use bounds, never midpoints.
3. Only `level=company` guidance enters CAGR numbers.
4. Empty cells are valid — never interpolate or ask the LLM to estimate.
5. Verbatim evidence always shown inline.

### Ground-truth item / output schema
`passage, speaker, page_number, metric, guidance_value (str, preserves "18-20"),
guidance_unit, timeline, horizon, level, track, credibility_scorable`. GT is
LLM-generated (propose → Opus 4.8 judge), **no human adjudication** — a deliberate
owner decision. Eval = model agreement, not absolute truth.

---

## 5. Tech Stack

| Layer | Choice |
|---|---|
| LLM API | OpenAI (GPT-5.4) + Anthropic (Claude Sonnet 4.6 / Opus 4.8 for judging). **gpt-4o retired.** |
| Decision layer | Pure Python (deterministic, no LLM) |
| PDF | `pdfplumber` (current) / `pypdf` (legacy `main.py`) |
| Validation | Pydantic v2 |
| Backend / DB | FastAPI + PostgreSQL + pgvector + SQLAlchemy (future v2) |
| Valuation data | Screener.in (`requests` + `BeautifulSoup`; premium CSV export in v1) |
| Env | `python-dotenv` (`.env`, gitignored) |
| UI | CSV / static HTML in v1; Streamlit in Phase 3 |
| Observability | Langfuse (future) |

---

## 6. Coding Conventions

- **Python 3, standard library + the pinned deps in `requirements.txt`.** Don't add
  a dependency without a reason; prefer what's already imported.
- **No LangChain. No fine-tuning** (unless explicitly asked). Vanilla loops first.
- **The LLM never does arithmetic.** Any number in the output table is computed in
  Python. Never ask the model to estimate a missing value.
- **Module style:** module-level docstring with `Usage:` line; `pathlib.Path` for
  paths; Pydantic models for any LLM I/O; `Optional[...]` fields preserve ranges as
  strings (e.g. `"18-20"`), never floats.
- **Prompts** live in `prompts/` as one file per version (`prompt_vN.txt`,
  `v1_oneshot_prompt.txt`). Don't inline large prompts in code — load from file and
  `.replace("{transcript_text}", ...)`.
- **Specs first** for pipeline stages: `specs/SPEC_STAGE*.md` is authoritative;
  code follows the spec. Stage tests: `scripts/test_stageN_acceptance.py`.
- **Determinism in extraction:** `temperature=0`, structured/`response_format` output.
- **Outputs** go to `output/`; experiments keep their artifacts inside
  `experiments/guidance_acceleration/`.
- **Filenames:** company stem is lowercase snake with quarter, e.g.
  `fineotex_chemical_Q4_FY26.pdf` → guidance `fineotex_chemical_q4_fy26`.
- **Secrets:** only from `.env`. Never hardcode keys; `.env`, `*.csv`,
  `transcripts/`, `venv/` are gitignored.
- **Don't write code unless asked** (per the working agreement); when asked "how/what
  approach", explain the concept, no code.

---

## 7. Repeatable Workflows (packaged as skills)

These are mirrored for both agents (Claude: `.claude/skills/`, Codex:
`.agents/skills/`):

- **download-transcripts** — fetch the last N quarters of concall PDFs for given
  tickers from screener.in with BSE fallback, into `transcripts/new_transcripts/`.
  Entry point: `python scripts/download_transcripts.py <TICKER> [...] --quarters 4`.
- **agent-sync-check** — verify Claude/Codex instructions, skill mirrors, Codex
  config, and custom-agent TOML are discoverable and not drifting. Hooks run this
  automatically at session start/stop; manual entry point:
  `python3 scripts/check_agent_sync.py`.

---

## 8. Key Reference Docs

- `CLAUDE.md` — Claude Code behavior + pointer here.
- `AGENTS.md` — Codex behavior + pointer here.
- `PROJECT.md` — long-form project document (v1.2).
- `plan.md` — active 2-day v1 build, Steps 6–8.
- `eval_log.md` — prompt-iteration tracking.
- `specs/` — per-stage extraction specs.
- `experiments/guidance_acceleration/{PLAN,HANDOFF,README}.md` — sandbox state.
