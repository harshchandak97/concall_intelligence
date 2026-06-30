#!/usr/bin/env python3
"""compare_view.py — side-by-side view of cheap vs Opus-4.8 reference extractions.

Prints (and writes results/comparison.md):
  1. a per-company table: cheap target vs reference target, with implied growth
  2. each model's ranked list by forward_growth (the % / multiple targets)
  3. the absolute-₹ targets (excluded from the forward_growth ranking — need a
     Screener base in step 5), listed separately

Usage:  python compare_view.py
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import lib_extract as L
from forward_growth import forward_growth

EXTRACT_DIR = L.HERE / "extractions"
REF = EXTRACT_DIR / "reference"


def load(d: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in d.glob("*.json")}


def field(item: dict) -> str:
    """One-line 'metric value unit / timeframe' or 'none'."""
    if (item.get("metric") or "none") == "none":
        return "none"
    return (f"{item['metric']} {item.get('value')}{item.get('unit') or ''}"
            f" / {item.get('timeframe')}")


def growth(item: dict) -> str:
    g = forward_growth(item)
    if g["status"] == "ok":
        return f"{g['low']*100:.0f}-{g['high']*100:.0f}%"
    return {"none": "—", "needs_base": "abs(₹)", "unparseable": "??"}[g["status"]]


def gnum(item: dict):
    g = forward_growth(item)
    return g["low"] if g["status"] == "ok" else None


def passage(item: dict) -> str:
    return " ".join((item.get("passage") or "").split())  # collapse whitespace/newlines


def main() -> None:
    ap = argparse.ArgumentParser(description="Side-by-side: candidate model vs Opus-4.8 reference.")
    ap.add_argument("--candidate", default="cheap",
                    help="extractions/<name>/ to compare against reference (default 'cheap')")
    args = ap.parse_args()
    lab = args.candidate                       # column/section label for the candidate
    cand_dir = EXTRACT_DIR / lab
    suffix = "" if lab == "cheap" else f"_{lab}"
    out_md = L.HERE / "results" / f"comparison{suffix}.md"
    out_csv = L.HERE / "results" / f"comparison{suffix}.csv"

    cand, ref = load(cand_dir), load(REF)
    slugs = sorted(set(cand) | set(ref))
    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    emit(f"# {lab} vs Opus-4.8 reference — {len(slugs)}-company sample\n")

    # 1. per-company side-by-side
    emit("## Per-company (alphabetical)\n")
    emit(f"| {'company':38} | {lab:34} | {'→':>7} | {'reference':34} | {'→':>7} | ok |")
    emit(f"|{'-'*40}|{'-'*36}|{'-'*9}|{'-'*36}|{'-'*9}|----|")
    for s in slugs:
        c, r = cand.get(s, {}), ref.get(s, {})
        agree = "✓" if field(c) == field(r) else ("~" if (c.get("metric") or "none") != "none"
                                                  and (r.get("metric") or "none") != "none" else "✗")
        emit(f"| {s[:38]:38} | {field(c)[:34]:34} | {growth(c):>7} | "
             f"{field(r)[:34]:34} | {growth(r):>7} | {agree:2} |")

    # 1b. per-company PASSAGES, stacked (table cells can't hold these)
    emit("\n## Passages — what each model quoted the number from\n")
    for s in slugs:
        c, r = cand.get(s, {}), ref.get(s, {})
        emit(f"### {s}")
        emit(f"- **{lab}** [{field(c)} → {growth(c)}]: {passage(c) or '—'}")
        emit(f"- **ref**   [{field(r)} → {growth(r)}]: {passage(r) or '—'}")
        emit("")

    # 2. ranked lists by forward_growth (only %/multiple targets rank)
    def ranked(d):
        rows = [(s, gnum(d[s])) for s in d if gnum(d[s]) is not None]
        return sorted(rows, key=lambda x: x[1], reverse=True)

    emit("\n## Ranked by forward_growth — REFERENCE (Opus 4.8)\n")
    for i, (s, g) in enumerate(ranked(ref), 1):
        emit(f"  {i:2}. {g*100:5.0f}%   {s:40} {field(ref[s])}")

    emit(f"\n## Ranked by forward_growth — {lab.upper()}\n")
    for i, (s, g) in enumerate(ranked(cand), 1):
        emit(f"  {i:2}. {g*100:5.0f}%   {s:40} {field(cand[s])}")

    # 3. absolute-₹ targets (not yet rankable — need Screener base in step 5)
    def absol(d):
        return [s for s in d if forward_growth(d[s])["status"] == "needs_base"]

    emit("\n## Absolute ₹ targets — REFERENCE (need Screener base, step 5)\n")
    for s in sorted(absol(ref)):
        emit(f"  • {s:40} {field(ref[s])}")
    emit(f"\n## Absolute ₹ targets — {lab.upper()}\n")
    for s in sorted(absol(cand)):
        emit(f"  • {s:40} {field(cand[s])}")

    # 4. 'none' (no qualifying target)
    emit("\n## 'none' — REFERENCE: "
         + ", ".join(sorted(s for s in ref if (ref[s].get('metric') or 'none') == 'none')))
    emit(f"## 'none' — {lab.upper()}:     "
         + ", ".join(sorted(s for s in cand if (cand[s].get('metric') or 'none') == 'none')))

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # CSV with full passages in their own columns (open in Excel/Sheets, wrap text)
    cols = ["company",
            f"{lab}_metric", f"{lab}_value", f"{lab}_unit", f"{lab}_timeframe",
            f"{lab}_growth", f"{lab}_passage",
            "ref_metric", "ref_value", "ref_unit", "ref_timeframe",
            "ref_growth", "ref_passage",
            "agree"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for s in slugs:
            c, r = cand.get(s, {}), ref.get(s, {})
            agree = "exact" if field(c) == field(r) else (
                "both-target" if (c.get("metric") or "none") != "none"
                and (r.get("metric") or "none") != "none" else "has-target-diff")
            w.writerow([
                s,
                c.get("metric"), c.get("value"), c.get("unit"), c.get("timeframe"),
                growth(c), passage(c),
                r.get("metric"), r.get("value"), r.get("unit"), r.get("timeframe"),
                growth(r), passage(r),
                agree])

    print(f"\n[written] {out_md}")
    print(f"[written] {out_csv}")


if __name__ == "__main__":
    main()
