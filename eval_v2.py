#!/usr/bin/env python3
"""
eval_v2.py — Score an extraction (output/*_guidance.json) against ground truth,
on the new two-gate schema (metric, value, timeline + horizon/level/track/credibility).

GT and extraction are both JSON: {"items": [ {schema...}, ... ]}.

Matching is two-pass:
  STRICT match → metric + timeline overlap + value within tolerance  (a clean true positive)
  SOFT match   → remaining items whose passages are >=0.6 similar      (same statement,
                 but a tag/metric/value disagreement — the actionable failures)

Reports precision/recall (strict and soft) and per-tag agreement on matched pairs,
then prints a disagreement log (misses, false positives, tag mismatches).

Usage:
  python eval_v2.py --gt data/fineotex_chemical_Q4_FY26_gt_proposed.json \
                    --extraction output/fineotex_chemical_Q4_FY26_guidance.json
"""

import json
import re
import argparse
from difflib import SequenceMatcher
from typing import Optional

TAG_FIELDS = ["metric", "horizon", "level", "track", "credibility_scorable"]


def load_items(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data["items"] if isinstance(data, dict) else data


# ── value + timeline helpers (mirror decision.py semantics) ───────────────────
def parse_bounds(v: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not v:
        return (None, None)
    clean = str(v).strip().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)$", clean)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.match(r"^(\d+(?:\.\d+)?)$", clean)
    if m:
        return (float(m.group(1)), float(m.group(1)))
    return (None, None)


def value_match(a: Optional[str], b: Optional[str], tol=0.15) -> bool:
    alo, ahi = parse_bounds(a)
    blo, bhi = parse_bounds(b)
    if alo is None and blo is None:
        return True  # both binary / null
    if alo is None or blo is None:
        return False
    amid, bmid = (alo + ahi) / 2, (blo + bhi) / 2
    if amid == 0:
        return bmid == 0
    return abs(amid - bmid) / amid <= tol


def fy_set(timeline: str) -> set[int]:
    """All fiscal years a timeline spans, as a set. 'FY28-FY29' → {2028,2029}.
    Bare calendar years are also recognised: '2030' → {2030}. A 'by 2030' target
    and an 'FY30' target name the same year, so both must produce {2030} — otherwise
    a GT item dated '2030' can never match an extraction dated 'FY30'."""
    if not timeline:
        return set()
    t = timeline.upper()
    yrs = [int(y) if int(y) > 100 else 2000 + int(y)
           for y in re.findall(r"FY\s*(\d{2,4})", t)]
    # Bare 4-digit calendar years (e.g. '2030') not already captured via an FY prefix.
    stripped = re.sub(r"FY\s*\d{2,4}", " ", t)
    yrs += [int(y) for y in re.findall(r"\b20\d{2}\b", stripped)]
    if not yrs:
        return set()
    if len(yrs) >= 2:
        return set(range(min(yrs), max(yrs) + 1))
    return {yrs[0]}


def timeline_overlap(a: str, b: str) -> bool:
    sa, sb = fy_set(a), fy_set(b)
    if not sa or not sb:
        return False
    return bool(sa & sb)


def passage_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


# ── matching ──────────────────────────────────────────────────────────────────
def strict_match(gt: dict, ex: dict) -> bool:
    return (
        gt.get("metric", "").strip() == ex.get("metric", "").strip()
        and timeline_overlap(gt.get("timeline", ""), ex.get("timeline", ""))
        and value_match(gt.get("guidance_value"), ex.get("guidance_value"))
    )


def evaluate(gt_items: list[dict], ex_items: list[dict]) -> dict:
    matched_gt, matched_ex = set(), set()
    pairs = []  # (gt_idx, ex_idx, "strict"|"soft")

    # Pass 1 — strict
    for gi, gt in enumerate(gt_items):
        for ei, ex in enumerate(ex_items):
            if ei in matched_ex:
                continue
            if strict_match(gt, ex):
                matched_gt.add(gi); matched_ex.add(ei)
                pairs.append((gi, ei, "strict"))
                break

    # Pass 2 — soft (passage similarity) on the leftovers
    for gi, gt in enumerate(gt_items):
        if gi in matched_gt:
            continue
        best_ei, best_sim = None, 0.6
        for ei, ex in enumerate(ex_items):
            if ei in matched_ex:
                continue
            s = passage_sim(gt.get("passage", ""), ex.get("passage", ""))
            if s >= best_sim:
                best_ei, best_sim = ei, s
        if best_ei is not None:
            matched_gt.add(gi); matched_ex.add(best_ei)
            pairs.append((gi, best_ei, "soft"))

    strict_tp = sum(1 for _, _, k in pairs if k == "strict")
    soft_tp = len(pairs)  # strict + soft

    return {
        "pairs": pairs,
        "matched_gt": matched_gt,
        "matched_ex": matched_ex,
        "strict_tp": strict_tp,
        "soft_tp": soft_tp,
        "gt_count": len(gt_items),
        "ex_count": len(ex_items),
    }


def tag_agreement(gt_items, ex_items, pairs) -> dict:
    """Per-tag agreement over all matched pairs (strict + soft)."""
    counts = {f: [0, 0] for f in TAG_FIELDS}  # field -> [agree, total]
    for gi, ei, _ in pairs:
        gt, ex = gt_items[gi], ex_items[ei]
        for f in TAG_FIELDS:
            counts[f][1] += 1
            gv, ev = gt.get(f), ex.get(f)
            if isinstance(gv, str):
                gv = gv.strip()
            if isinstance(ev, str):
                ev = ev.strip()
            if gv == ev:
                counts[f][0] += 1
    return counts


def short(item: dict) -> str:
    v = item.get("guidance_value") or "—"
    u = item.get("guidance_unit") or ""
    return (f"{item.get('metric','?')} {v}{u} {item.get('timeline','?')} "
            f"[{item.get('level','?')}/{item.get('horizon','?')}]")


def report(name, gt_items, ex_items, res):
    pairs = res["pairs"]
    gt_n, ex_n = res["gt_count"], res["ex_count"]
    s_tp, soft_tp = res["strict_tp"], res["soft_tp"]

    strict_recall = s_tp / gt_n if gt_n else 0
    strict_prec = s_tp / ex_n if ex_n else 0
    soft_recall = soft_tp / gt_n if gt_n else 0
    soft_prec = soft_tp / ex_n if ex_n else 0

    print(f"\n{'='*70}\nEVAL — {name}")
    print(f"  GT items: {gt_n}   Extraction items: {ex_n}")
    print(f"{'='*70}")
    print(f"  STRICT (metric+timeline+value):  recall {strict_recall*100:4.0f}%   precision {strict_prec*100:4.0f}%")
    print(f"  SOFT   (passage-matched):        recall {soft_recall*100:4.0f}%   precision {soft_prec*100:4.0f}%")
    print(f"         (soft−strict = found but mis-tagged/mis-valued)")

    print(f"\n  Tag agreement on {len(pairs)} matched pairs:")
    for f, (agree, total) in tag_agreement(gt_items, ex_items, pairs).items():
        pct = (agree / total * 100) if total else 0
        print(f"    {f:22} {agree}/{total} = {pct:3.0f}%")

    # Disagreement log
    soft_only = [(gi, ei) for gi, ei, k in pairs if k == "soft"]
    if soft_only:
        print(f"\n  MIS-TAGGED (same passage, tag/value differs) — adjudicate these:")
        for gi, ei in soft_only:
            print(f"    GT : {short(gt_items[gi])}")
            print(f"    LLM: {short(ex_items[ei])}\n")

    missed = [gi for gi in range(gt_n) if gi not in res["matched_gt"]]
    if missed:
        print(f"  MISSED (in GT, not extracted) — recall failures:")
        for gi in missed:
            print(f"    {short(gt_items[gi])}")

    fps = [ei for ei in range(ex_n) if ei not in res["matched_ex"]]
    if fps:
        print(f"\n  FALSE POSITIVES (extracted, not in GT) — precision failures:")
        for ei in fps:
            print(f"    {short(ex_items[ei])}")
    print(f"{'='*70}")

    return {
        "name": name, "gt": gt_n, "ex": ex_n,
        "strict_recall": strict_recall, "strict_precision": strict_prec,
        "soft_recall": soft_recall, "soft_precision": soft_prec,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--extraction", required=True)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    gt_items = load_items(args.gt)
    ex_items = load_items(args.extraction)
    name = args.name or args.extraction.split("/")[-1].replace("_guidance.json", "")
    res = evaluate(gt_items, ex_items)
    report(name, gt_items, ex_items, res)


if __name__ == "__main__":
    main()
