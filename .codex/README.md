# .codex/ — OpenAI Codex Configuration

Codex project-scoped configuration for Concall Intelligence. Codex reads this
directory only when the project is trusted.

## Layout

```
.codex/
├── README.md
├── config.toml
└── agents/
    ├── extraction-reviewer.toml
    └── decision-layer-auditor.toml
```

## Related Codex Files

| Purpose | Location |
|---|---|
| Repo instructions | `AGENTS.md` |
| Shared project context | `PROJECT_CONTEXT.md` |
| Repo skills | `.agents/skills/<skill-name>/SKILL.md` |
| Project config | `.codex/config.toml` |
| Custom subagents | `.codex/agents/*.toml` |

## Token-Budget Guidance

This is a data-heavy repo. Keep Codex token usage low:

1. Pull deep context on demand from `PROJECT_CONTEXT.md` and the relevant
   `specs/SPEC_*.md`; do not load the whole tree.
2. Never read `transcripts/`, `*.csv`, `*.log`, or experiment transcript/output
   artifacts wholesale. Grep or slice.
3. Load only the prompt version or stage spec the task needs.
4. Keep UTF-8 end to end. Transcripts carry `₹` and unit glyphs used by extraction.
5. Use lower reasoning effort for mechanical edits; reserve high effort for
   architecture and decision-layer changes.
