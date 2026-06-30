#!/usr/bin/env python3
"""review_extraction.py — render an extraction folder to a readable markdown file.

Shows, per company: the company-level PAT-CAGR drivers (`items`) and the
`other` signals, each with its verbatim passage, so the granular extraction is
easy to eyeball.

Usage:  python review_extraction.py --candidate gpt54_granular
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import lib_extract as L

EXTRACT_DIR = L.HERE / "extractions"


def _p(passage) -> str:
    return " ".join((passage or "").split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="gpt54_granular")
    args = ap.parse_args()
    src = EXTRACT_DIR / args.candidate
    out = L.HERE / "results" / f"review_{args.candidate}.md"

    files = sorted(src.glob("*.json"))
    lines = [f"# Extraction review — `{args.candidate}` ({len(files)} companies)\n"]
    for fp in files:
        d = json.loads(fp.read_text())
        items = d.get("items", [])
        lines.append(f"\n## {fp.stem}")
        lines.append(f"*call_period: {d.get('call_period', '—')}  ·  {len(items)} driver(s)*\n")

        co = [g for g in items if g.get("scope") == "company"]
        non = [g for g in items if g.get("scope") != "company"]
        if items:
            lines.append("| metric | value | unit | cur | scope | timeline |")
            lines.append("|---|---|---|---|---|---|")
            for g in items:
                mark = "" if g.get("scope") == "company" else "  ⟵ excluded"
                lines.append(f"| `{g['metric']}` | {g.get('value')} | {g.get('unit')} "
                             f"| {g.get('currency') or ''} | {g.get('scope')}{mark} | {g.get('timeline')} |")
            lines.append(f"\n**Company drivers (feed CAGR): {len(co)}  ·  non-company (excluded): {len(non)}**\n")
            for g in co:
                lines.append(f"- `{g['metric']}` {g.get('value')}{g.get('unit') or ''} "
                             f"/{g.get('timeline')} — {_p(g.get('passage'))[:240]}")
            if non:
                lines.append("\n_non-company (labelled, filtered out):_")
                for g in non:
                    lines.append(f"- [{g.get('scope')}] `{g['metric']}` {g.get('value')}{g.get('unit') or ''} "
                                 f"/{g.get('timeline')} — {_p(g.get('passage'))[:160]}")
        else:
            lines.append("_no qualifying drivers_")
        lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[written] {out}")


if __name__ == "__main__":
    main()
