#!/usr/bin/env python3
"""validate_extraction.py — STEP 3 gate (PLAN.md §5a).

Compares the cheap model (GPT-5.4-mini, extractions/cheap/) against the
cross-family Opus-4.8 reference (extractions/reference/, written by Claude Code)
on the companies present in BOTH folders, on the three decision-relevant axes:

  1. Has-target agreement  — do both agree a company gave a quantified target
                             vs `none`?
  2. Derived-number agreement — after forward_growth(), is the implied annual
                             growth within a few pp? (absolute ₹ targets, which
                             need a Screener base, are compared on raw fields.)
  3. Top-N overlap         — rank both by forward_growth; do the top 3 / top 5
                             names match? (the metric that feeds the experiment)

It then lists the disagreements for manual adjudication. Pre-registered bars:
top-3 overlap >= 2/3, has-target >= ~85%, no gross derived-number errors.

Usage:  python validate_extraction.py
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

import lib_extract as L
from forward_growth import forward_growth, rank_key

EXTRACT_DIR = L.HERE / "extractions"
REF_DIR = EXTRACT_DIR / "reference"

NUM_TOL = 0.05   # 5 percentage points: "within a few pp"


def _load(d: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in d.glob("*.json")}


def _has_target(item: dict) -> bool:
    return (item.get("metric") or "none").lower() != "none"


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _raw_key(item: dict) -> tuple:
    """Raw-field identity for absolute targets the gate can't annualise."""
    return (_norm(item.get("metric")), _norm(item.get("value")),
            _norm(item.get("unit")), _norm(item.get("timeframe")))


def _fmt(item: dict) -> str:
    if not _has_target(item):
        return "none"
    g = forward_growth(item)
    growth = (f"{g['low']*100:.0f}-{g['high']*100:.0f}%"
              if g["status"] == "ok" else g["status"])
    return (f"{item['metric']} {item.get('value')}{item.get('unit') or ''} "
            f"/{item.get('timeframe')}  ->  {growth}")


def _topn(items: dict[str, dict], n: int) -> list[str]:
    ranked = sorted(items, key=lambda s: rank_key(items[s]), reverse=True)
    # keep only names that actually rank (forward_growth ok), up to n
    ranked = [s for s in ranked if rank_key(items[s]) != float("-inf")]
    return ranked[:n]


def main() -> None:
    ap = argparse.ArgumentParser(description="Gate: candidate model vs Opus-4.8 reference.")
    ap.add_argument("--candidate", default="cheap",
                    help="extractions/<name>/ to score against reference (default 'cheap')")
    args = ap.parse_args()
    cand_dir = EXTRACT_DIR / args.candidate

    cheap, ref = _load(cand_dir), _load(REF_DIR)
    slugs = sorted(set(cheap) & set(ref))
    if not slugs:
        print(f"No overlapping companies in extractions/{args.candidate} and "
              "extractions/reference yet.\n"
              f"  candidate: {len(cheap)} files in {cand_dir}\n"
              f"  ref:       {len(ref)} files in {REF_DIR}")
        return

    print(f"GATE — candidate '{args.candidate}' vs reference — "
          f"{len(slugs)} companies\n" + "=" * 64)

    # --- axis 1: has-target agreement
    has_agree = sum(_has_target(cheap[s]) == _has_target(ref[s]) for s in slugs)
    both_target = [s for s in slugs if _has_target(cheap[s]) and _has_target(ref[s])]

    # --- axis 2: derived-number agreement (among both-have-target)
    num_ok = num_total = 0
    raw_ok = raw_total = 0
    gross = []  # large numeric disagreements — the dangerous ones
    for s in both_target:
        gc, gr = forward_growth(cheap[s]), forward_growth(ref[s])
        if gc["status"] == "ok" and gr["status"] == "ok":
            num_total += 1
            d = abs(gc["low"] - gr["low"])
            if d <= NUM_TOL:
                num_ok += 1
            else:
                gross.append((s, d))
        elif gc["status"] == "needs_base" and gr["status"] == "needs_base":
            raw_total += 1
            raw_ok += _raw_key(cheap[s]) == _raw_key(ref[s])

    # --- axis 3: top-N overlap (by forward_growth)
    c3, r3 = set(_topn(cheap, 3)), set(_topn(ref, 3))
    c5, r5 = set(_topn(cheap, 5)), set(_topn(ref, 5))

    def pct(a, b):
        return f"{(a / b * 100):.0f}%" if b else "n/a"

    print(f"\n1. HAS-TARGET AGREEMENT : {has_agree}/{len(slugs)}  "
          f"({pct(has_agree, len(slugs))})   [bar: >= ~85%]")
    print(f"   both have a target   : {len(both_target)}   "
          f"both 'none': {sum(not _has_target(cheap[s]) and not _has_target(ref[s]) for s in slugs)}")

    print(f"\n2. DERIVED-NUMBER AGREEMENT (within {NUM_TOL*100:.0f}pp)")
    print(f"   annualisable pairs   : {num_ok}/{num_total}  ({pct(num_ok, num_total)})")
    print(f"   absolute-₹ raw match : {raw_ok}/{raw_total}  ({pct(raw_ok, raw_total)})")
    if gross:
        print(f"   ⚠ {len(gross)} pair(s) disagree by >{NUM_TOL*100:.0f}pp "
              f"(adjudicate — see disagreements)")

    print(f"\n3. TOP-N OVERLAP (ranked by forward_growth)   [bar: top-3 >= 2/3]")
    print(f"   top-3 overlap        : {len(c3 & r3)}/3   "
          f"cheap={sorted(c3)}  ref={sorted(r3)}")
    print(f"   top-5 overlap        : {len(c5 & r5)}/5")

    # --- disagreements for manual adjudication
    dis = []
    for s in slugs:
        c, r = cheap[s], ref[s]
        if _has_target(c) != _has_target(r):
            dis.append((s, "has-target"))
        elif _has_target(c) and _has_target(r):
            gc, gr = forward_growth(c), forward_growth(r)
            if gc["status"] == "ok" and gr["status"] == "ok":
                if abs(gc["low"] - gr["low"]) > NUM_TOL:
                    dis.append((s, "number"))
            elif gc["status"] == "needs_base" and gr["status"] == "needs_base":
                if _raw_key(c) != _raw_key(r):
                    dis.append((s, "raw-fields"))
            else:
                dis.append((s, f"status {gc['status']}/{gr['status']}"))

    print("\n" + "=" * 64)
    print(f"DISAGREEMENTS TO ADJUDICATE: {len(dis)}")
    for s, why in dis:
        print(f"\n• {s}   [{why}]")
        print(f"    cheap : {_fmt(cheap[s])}")
        print(f"    ref   : {_fmt(ref[s])}")
        cp = (cheap[s].get('passage') or '').strip().replace("\n", " ")
        rp = (ref[s].get('passage') or '').strip().replace("\n", " ")
        if cp:
            print(f"    cheap passage: {cp[:200]}")
        if rp:
            print(f"    ref   passage: {rp[:200]}")

    # absolute-only targets are invisible to the forward_growth ranking — flag it
    abs_only = [s for s in both_target
                if forward_growth(ref[s])["status"] == "needs_base"]
    if abs_only:
        print(f"\nnote: {len(abs_only)} reference target(s) are absolute ₹ amounts "
              f"(need a Screener base in step 5) and don't enter the forward_growth "
              f"top-N: {abs_only}")


if __name__ == "__main__":
    main()
