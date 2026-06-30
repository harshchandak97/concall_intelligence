---
name: agent-sync-check
description: Check that Claude Code and Codex repo instructions, skills, config, and custom agents are discoverable and not drifting. Use when agent setup, skills, hooks, AGENTS.md, CLAUDE.md, PROJECT_CONTEXT.md, .codex, .agents, or .claude files change.
---

# Agent Sync Check

Run the deterministic sync check:

```bash
python3 scripts/check_agent_sync.py
```

Use it after changing shared project context, agent instructions, skills, hooks,
or Codex custom-agent config.

The check verifies:
- Required shared files exist: `PROJECT_CONTEXT.md`, `CLAUDE.md`, `AGENTS.md`.
- Codex active config exists under `.codex/`.
- Claude and Codex skill mirrors match between `.claude/skills/` and
  `.agents/skills/`.
- Codex custom-agent TOML files parse and include required keys.
- No stale inactive `codex/` tree or plain `codex/` path references remain.

If the check reports skill mirror drift, update the changed `SKILL.md` in both
`.claude/skills/<name>/` and `.agents/skills/<name>/`, then rerun the script.
