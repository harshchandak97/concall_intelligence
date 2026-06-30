#!/usr/bin/env python3
"""Check Claude Code and Codex shared-agent configuration for drift.

Usage:
  python3 scripts/check_agent_sync.py
  python3 scripts/check_agent_sync.py --hook
"""
from __future__ import annotations

import argparse
import filecmp
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "PROJECT_CONTEXT.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".codex/config.toml",
    ".codex/README.md",
]

DOC_FILES = [
    "PROJECT_CONTEXT.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".codex/README.md",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def check_required_files() -> list[str]:
    issues = []
    for name in REQUIRED_FILES:
        if not (ROOT / name).is_file():
            issues.append(f"missing required file: {name}")
    return issues


def check_old_codex_tree() -> list[str]:
    old = ROOT / "codex"
    if old.exists():
        return ["old inactive codex/ tree exists; active Codex paths are .codex/ and .agents/"]
    return []


def check_stale_path_refs() -> list[str]:
    issues = []
    pattern = re.compile(r"(?<![.])\bcodex/")
    for name in DOC_FILES:
        path = ROOT / name
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                issues.append(f"stale codex/ path reference in {name}:{line_no}")
    return issues


def check_toml() -> list[str]:
    issues = []
    for path in [ROOT / ".codex/config.toml", *sorted((ROOT / ".codex/agents").glob("*.toml"))]:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validation script should report parse failures.
            issues.append(f"invalid TOML: {rel(path)} ({exc})")
            continue

        if path.parent.name == "agents":
            for key in ("name", "description", "developer_instructions"):
                if not data.get(key):
                    issues.append(f"{rel(path)} missing required custom-agent key: {key}")
    return issues


def check_skill_mirrors() -> list[str]:
    issues = []
    claude_root = ROOT / ".claude/skills"
    codex_root = ROOT / ".agents/skills"

    if not claude_root.is_dir():
        issues.append("missing Claude skill directory: .claude/skills")
        claude_names: set[str] = set()
    else:
        claude_names = {p.name for p in claude_root.iterdir() if p.is_dir()}

    if not codex_root.is_dir():
        issues.append("missing Codex skill directory: .agents/skills")
        codex_names: set[str] = set()
    else:
        codex_names = {p.name for p in codex_root.iterdir() if p.is_dir()}

    for name in sorted(claude_names - codex_names):
        issues.append(f"skill missing from Codex mirror: {name}")
    for name in sorted(codex_names - claude_names):
        issues.append(f"skill missing from Claude mirror: {name}")

    for name in sorted(claude_names & codex_names):
        left = claude_root / name / "SKILL.md"
        right = codex_root / name / "SKILL.md"
        if not left.is_file():
            issues.append(f"missing Claude skill file: {rel(left)}")
            continue
        if not right.is_file():
            issues.append(f"missing Codex skill file: {rel(right)}")
            continue
        if not filecmp.cmp(left, right, shallow=False):
            issues.append(f"skill mirror drift: {rel(left)} != {rel(right)}")

    return issues


def collect_issues() -> list[str]:
    issues: list[str] = []
    issues.extend(check_required_files())
    issues.extend(check_old_codex_tree())
    issues.extend(check_stale_path_refs())
    issues.extend(check_toml())
    issues.extend(check_skill_mirrors())
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hook",
        action="store_true",
        help="print concise warnings and exit 0 so agent hooks do not block work",
    )
    args = parser.parse_args()

    issues = collect_issues()
    if not issues:
        if not args.hook:
            print("agent sync ok")
        return 0

    print("agent sync warnings:", file=sys.stderr)
    for issue in issues:
        print(f"- {issue}", file=sys.stderr)

    return 0 if args.hook else 1


if __name__ == "__main__":
    raise SystemExit(main())
