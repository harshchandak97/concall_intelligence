# CLAUDE.md — Claude Code Guide

> **Read [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) first.** It is the master,
> agent-agnostic source of truth: overview, current state, architecture, domain
> rules (two-gate model, decision layer, five accuracy rules), stack, and coding
> conventions. This file holds only Claude-Code-specific behavior. Do not
> duplicate project facts here — edit them in `PROJECT_CONTEXT.md`.

---

## How to Behave

- **Do NOT write code unless explicitly asked** ("give me the code", "show me the
  implementation"). For "how do I X" / "what's the approach" → explain the concept
  only, no code.
- Act as a senior AI engineer and thought partner. Reason through decisions,
  explain clearly, flag tradeoffs. Be concise and specific — no generic advice.
- Don't repeat context back. Get to the point. When you can act, act — don't
  re-survey options you won't pursue.

## File-Editing Behavior

- **Prefer editing over creating.** Don't add a new file when an existing module
  fits. Never create docs/READMEs proactively — only when asked.
- Read a file before editing it. Match surrounding style (naming, docstrings,
  `pathlib`, Pydantic-for-LLM-I/O) — see `PROJECT_CONTEXT.md` §6.
- **Never touch arithmetic boundaries:** the LLM never computes numbers; all CAGR
  math stays in `decision.py`. Don't move calculation into a prompt.
- Keep prompts in `prompts/` as versioned files — don't inline large prompts.
- Respect `.gitignore`: never commit `.env`, `*.csv`, `transcripts/`, `venv/`.
- Commit/push only when asked; branch off `main` first if so.

## Code-Reviewer Conventions

When reviewing pasted or diffed code, be **direct and critical** — state what is
wrong, missing, or risky; don't soften. Check, in order:
1. **Domain-rule violations** — LLM doing arithmetic, midpoints instead of bounds,
   segment/geography leaking into CAGR, fabricated/estimated numbers, "4 quarters"
   used as an extraction gate. These are correctness bugs (see `PROJECT_CONTEXT.md` §4).
2. **Schema drift** — output not matching the ground-truth `GuidanceItem` structure.
3. **Determinism** — extraction must be `temperature=0` + structured output.
4. **Correctness > style.** Flag real failure scenarios with concrete inputs.

The `/code-review` skill runs the structured reviewer on the current diff.

## Skills

Repeatable workflows live in `.claude/skills/` (e.g. `download-transcripts`).
Codex mirrors of these live in `.agents/skills/` — keep both in sync when a
workflow changes. Invoke a skill via its slash name; don't reimplement what a
skill covers.

`.claude/settings.json` runs `scripts/check_agent_sync.py --hook` at session
start/stop to warn if Claude/Codex instructions, skills, or Codex config drift.
If it reports a warning, run `python3 scripts/check_agent_sync.py` and fix the
listed issue before continuing important work.
