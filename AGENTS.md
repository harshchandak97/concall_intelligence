# AGENTS.md — OpenAI Codex Guide

> **Read [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) first.** It is the master,
> agent-agnostic source of truth: overview, current state, architecture, domain
> rules (two-gate model, decision layer, five accuracy rules), stack, and coding
> conventions. This file holds only Codex-specific behavior and points at the
> deeper config under `.codex/`. Do not duplicate project facts here — edit them in
> `PROJECT_CONTEXT.md`.

Codex reads this `AGENTS.md` automatically from the repo root. It is the Codex peer
of `CLAUDE.md`; both reference the same `PROJECT_CONTEXT.md` so the two agents stay
in lockstep.

---

## How to Behave

- **Do NOT write code unless explicitly asked.** For "how/what approach" questions,
  explain the concept only — no code.
- Senior AI-engineer thought partner: reason through tradeoffs, be concise and
  specific, no generic filler. When you can act, act.

## File-Editing Behavior

- Prefer editing an existing module over creating a new file. Don't create
  docs/READMEs proactively.
- Match surrounding style: `pathlib` paths, module docstring with a `Usage:` line,
  Pydantic models for any LLM I/O, ranges kept as strings (`"18-20"`), not floats.
- **Hard boundary:** the LLM never does arithmetic — all CAGR math lives in
  `decision.py`. Never push calculation into a prompt.
- Prompts stay in `prompts/` as versioned files. Extraction is `temperature=0` +
  structured output.
- Never commit `.env`, `*.csv`, `transcripts/`, `venv/` (see `.gitignore`).
- Commit/push only when asked; branch off `main` first.

## Code-Review Conventions

Be direct and critical. Priority order: (1) domain-rule violations — LLM doing
math, midpoints vs bounds, segment/geography leaking into CAGR, fabricated numbers,
"4 quarters" misused as an extraction gate; (2) schema drift vs the `GuidanceItem`
structure; (3) determinism; (4) correctness over style. See `PROJECT_CONTEXT.md` §4.

## Codex Config & Skills

- `.codex/config.toml` — model, reasoning effort, and token/encoding settings.
- `.codex/hooks.json` — startup/stop sync check for Claude/Codex instructions,
  skills, and Codex custom-agent config.
- `.agents/skills/` — packaged repeatable workflows (mirror of `.claude/skills/`).
  Keep both copies in sync when a workflow changes.
- `.codex/agents/` — reusable Codex agent definitions (extraction reviewer,
  decision-layer auditor). See `.codex/README.md` for the layout and token-budget
  guidance.
- `scripts/check_agent_sync.py` — deterministic sync check; run manually if a hook
  reports drift.

## Token Management (Codex)

Optimize for token cost — details in `.codex/config.toml` and `.codex/README.md`:
- This `AGENTS.md` stays lean; deep context is loaded on demand from
  `PROJECT_CONTEXT.md` and `specs/` rather than pasted into every prompt.
- Load only the relevant spec/prompt file for the task, not the whole `prompts/`
  or `specs/` tree.
- Large artifacts (`crawl_full.log`, `universe_*.csv`, `transcripts/`) are
  context-excluded — never read them wholesale; grep/slice instead.
