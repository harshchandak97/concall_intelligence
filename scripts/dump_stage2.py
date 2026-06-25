"""
dump_stage2.py — Stage 2 output dump with full GT comparison

Runs Stage 0 → Stage 1 → Stage 2 on each transcript and writes a single
markdown file with everything needed for analysis:

  Per company:
    - Summary: chunks, items extracted, GT count, recall
    - GT coverage table: which GT items were matched, missed
    - Extracted items (annotated): match status, GT id, passage comparison
    - Missed GT items: GT passage + closest extracted match for diagnosis

Output: scripts/debug_output/all_companies_stage2_dump.md

Run from project root: python scripts/dump_stage2.py
Run for one company:   python scripts/dump_stage2.py sandhar
"""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.stage0_segmenter import segment
from pipeline.stage1_filter import filter_chunks
from pipeline.stage2_extractor import extract

COMPANIES = [
    {
        "name": "Asian Paints",
        "slug": "asian_paints",
        "pdf":  "transcripts/asian_paints_Q4_FY26.pdf",
        "gt":   "data/asian_paints_Q4_FY26_ground_truth_v3.txt",
    },
    {
        "name": "Fineotex Chemical",
        "slug": "fineotex_chemical",
        "pdf":  "transcripts/fineotex_chemical_Q4_FY26.pdf",
        "gt":   "data/fineotex_chemical_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Sandhar Technologies",
        "slug": "sandhar_technologies",
        "pdf":  "transcripts/sandhar_technologies_Q4_FY26.pdf",
        "gt":   "data/sandhar_technologies_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Mold-Tek Packaging",
        "slug": "mold-tek_packaging",
        "pdf":  "transcripts/mold-tek_packaging_Q4_FY26.pdf",
        "gt":   "data/mold-tek_packaging_Q4_FY26_ground_truth_v1.txt",
    },
]

OUTPUT_DIR = Path(__file__).parent / "debug_output"

_SPEAKER_LABEL_RE = re.compile(r"([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,3}):\s")


# ── Matching helpers (same logic as acceptance test) ─────────────────────────

def _normalize(text: str) -> str:
    text = (text
        .replace('’', "'").replace('‘', "'")
        .replace('“', '"').replace('”', '"')
        .replace('–', '-').replace('—', '-')
        .replace('…', '...').replace(' ', ' ')
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def _strip_speakers(text: str) -> str:
    parts = _SPEAKER_LABEL_RE.split(text)
    body  = [p for i, p in enumerate(parts) if i % 2 == 0]
    return " ".join(p.strip() for p in body if p.strip())


def _speaker_sub_texts(passage: str) -> list[str]:
    parts = _SPEAKER_LABEL_RE.split(passage)
    raw   = [p for i, p in enumerate(parts) if i % 2 == 0]
    return [p.lstrip("… ").strip() for p in raw if p.strip("… ").strip()]


def _match_mode(gt_passage: str, ext_passage: str) -> str | None:
    """Return match mode string if the two passages match, else None."""
    norm_gt_subs  = [_normalize(s) for s in _speaker_sub_texts(gt_passage)]
    norm_gt_full  = _normalize(gt_passage)
    norm_gt_clean = _normalize(_strip_speakers(gt_passage))
    norm_ext      = _normalize(ext_passage)
    norm_ext_clean= _normalize(_strip_speakers(ext_passage))

    if all(s in norm_ext for s in norm_gt_subs):
        return "substring"
    if norm_gt_clean and norm_gt_clean in norm_ext_clean:
        return "content-match"
    sim = SequenceMatcher(None, norm_gt_full, norm_ext).ratio()
    if sim > 0.65:
        return f"fuzzy-full({sim:.2f})"
    sim_clean = SequenceMatcher(None, norm_gt_clean, norm_ext_clean).ratio()
    if sim_clean > 0.85:
        return f"fuzzy-content({sim_clean:.2f})"
    return None


def _best_match(gt_passage: str, extracted_items) -> tuple[int | None, str, float]:
    """Return (best_item_idx, mode_or_empty, best_sim) for the closest extracted item."""
    best_idx  = None
    best_mode = ""
    best_sim  = 0.0
    norm_gt   = _normalize(gt_passage)
    norm_gt_c = _normalize(_strip_speakers(gt_passage))

    for i, item in enumerate(extracted_items):
        mode = _match_mode(gt_passage, item.passage)
        if mode:
            return i, mode, 1.0

        norm_ext = _normalize(item.passage)
        norm_ext_c = _normalize(_strip_speakers(item.passage))
        sim   = SequenceMatcher(None, norm_gt, norm_ext).ratio()
        sim_c = SequenceMatcher(None, norm_gt_c, norm_ext_c).ratio()
        s = max(sim, sim_c)
        if s > best_sim:
            best_sim  = s
            best_idx  = i
            best_mode = f"no-match (best sim {s:.2f})"

    return best_idx, best_mode, best_sim


# ── GT parser ────────────────────────────────────────────────────────────────

def _parse_gt(gt_path: str) -> list[dict]:
    text  = Path(gt_path).read_text()
    items = []
    for m in re.finditer(r"^id:\s*(\d+)\n", text, re.M):
        gt_id = m.group(1)
        rest  = text[m.end():]
        fields = {}
        for field in ("guidance", "passage", "metric", "guidance_value",
                      "guidance_unit", "timeline", "credibility_scorable"):
            fm = re.search(rf'^{field}:\s*"?(.*?)"?[ \t]*\n', rest, re.M | re.S)
            if fm:
                # For passage, use the full quoted value
                if field == "passage":
                    pm = re.search(r'passage:\s*"(.*?)"[ \t]*\n', rest, re.S)
                    fields[field] = pm.group(1) if pm else ""
                else:
                    fields[field] = fm.group(1).strip().strip('"')
        fields["id"] = gt_id
        items.append(fields)
    return items


# ── Passage comparison analysis ───────────────────────────────────────────────

def _passage_analysis(ext_passage: str, gt_passage: str) -> str:
    ext_words = len(ext_passage.split())
    gt_words  = len(gt_passage.split())
    delta     = ext_words - gt_words
    if abs(delta) <= 5:
        size_note = "same length as GT"
    elif delta > 0:
        size_note = f"{delta} words LONGER than GT (extra context included)"
    else:
        size_note = f"{abs(delta)} words SHORTER than GT (may be truncated)"

    norm_gt  = _normalize(gt_passage)
    norm_ext = _normalize(ext_passage)

    if norm_gt in norm_ext:
        coverage = "GT passage fully contained in extracted passage"
    elif norm_ext in norm_gt:
        coverage = "Extracted passage is a subset of GT passage"
    else:
        sim = SequenceMatcher(None, norm_gt, norm_ext).ratio()
        coverage = f"Partial overlap — {sim:.0%} similarity"

    return f"{size_note}. {coverage}."


# ── Main dump logic ──────────────────────────────────────────────────────────

def dump_all(companies: list[dict]) -> None:
    lines: list[str] = []
    lines.append("# Stage 2 Full Analysis Dump — All Companies")
    lines.append("")
    lines.append("For each company: extracted items with GT match annotations,")
    lines.append("missed GT items with diagnosis, and false positives.")
    lines.append("")

    total_gt = total_found = total_extracted = 0

    for company in companies:
        pdf_path = company["pdf"]
        gt_path  = company.get("gt", "")

        lines.append("\n" + "=" * 72)
        lines.append(f"# {company['name']}")
        lines.append("=" * 72 + "\n")

        if not Path(pdf_path).exists():
            lines.append(f"SKIPPED — PDF not found: {pdf_path}\n")
            print(f"{company['name']}: SKIPPED")
            continue

        print(f"{company['name']}: running Stage 0 → 1 → 2 …")
        chunks_s0 = segment(pdf_path)
        chunks_s1 = filter_chunks(chunks_s0)
        items     = extract(chunks_s1)
        print(f"  → {len(items)} items extracted")
        total_extracted += len(items)

        gt_items = _parse_gt(gt_path) if gt_path and Path(gt_path).exists() else []
        has_gt   = bool(gt_items)

        # ── Match each GT item to best extracted item ─────────────────────
        # gt_match[gt_idx] = (extracted_item_idx, mode) or None
        gt_match: list[tuple[int, str] | None] = []
        for gt in gt_items:
            idx, mode, _ = _best_match(gt["passage"], items)
            if mode.startswith("no-match"):
                gt_match.append(None)
            else:
                gt_match.append((idx, mode))

        # For each extracted item, find which GT items it matched
        # item_to_gt[item_idx] = list of (gt_idx, mode)
        item_to_gt: dict[int, list[tuple[int, str]]] = {i: [] for i in range(len(items))}
        for gi, match in enumerate(gt_match):
            if match is not None:
                item_to_gt[match[0]].append((gi, match[1]))

        # ── Summary ───────────────────────────────────────────────────────
        found_count = sum(1 for m in gt_match if m is not None)
        if has_gt:
            recall = found_count / len(gt_items)
            total_gt    += len(gt_items)
            total_found += found_count
        fp_count = sum(1 for i in range(len(items)) if not item_to_gt[i])

        lines.append("## Summary\n")
        lines.append(f"- Stage 0 chunks : {len(chunks_s0)}")
        lines.append(f"- Stage 1 chunks : {len(chunks_s1)} (after filter)")
        lines.append(f"- Stage 2 items  : {len(items)} (after union merge)")
        if has_gt:
            lines.append(f"- GT items       : {len(gt_items)}")
            lines.append(f"- GT matched     : {found_count}/{len(gt_items)} = {recall:.0%}")
            lines.append(f"- GT missed      : {len(gt_items) - found_count}")
        lines.append(f"- No GT match    : {fp_count} items (not in GT — may be valid or false positive)")
        lines.append("")

        # ── GT coverage table ─────────────────────────────────────────────
        if has_gt:
            lines.append("## Ground Truth Coverage\n")
            lines.append("| GT id | Guidance | Status | Matched item | Match mode |")
            lines.append("|---|---|---|---|---|")
            for gi, gt in enumerate(gt_items):
                match = gt_match[gi]
                status = "✅ MATCH" if match else "❌ MISS"
                if match:
                    item_no  = match[0] + 1
                    mode_str = match[1]
                else:
                    item_no  = "—"
                    mode_str = "—"
                guidance_label = gt.get("guidance", "")[:50]
                lines.append(f"| GT{gt['id']} | {guidance_label} | {status} | Item {item_no} | {mode_str} |")
            lines.append("")

        # ── Extracted items (annotated) ───────────────────────────────────
        lines.append("## Extracted Items\n")

        for i, item in enumerate(items, 0):
            matched_gts = item_to_gt[i]
            item_no     = i + 1

            if matched_gts:
                gt_labels = ", ".join(f"GT{gt_items[gi]['id']} [{mode}]" for gi, mode in matched_gts)
                match_banner = f"✅ MATCHES {gt_labels}"
            else:
                match_banner = "⚪ NO GT MATCH — not in ground truth (check if valid or false positive)"

            lines.append("---\n")
            lines.append(f"### Item {item_no}  ·  chunk `{item.chunk_id}`")
            lines.append(f"**{match_banner}**\n")
            lines.append(f"- Speaker           : {item.speaker}")
            lines.append(f"- Page              : {item.page_number}")
            lines.append(f"- Guidance value    : {item.guidance_value or '—'}")
            lines.append(f"- Unit              : {item.guidance_unit  or '—'}")
            lines.append(f"- Timeline          : {item.timeline}")
            lines.append(f"- Metric (LLM desc) : {item.metric_description}")
            lines.append("")

            lines.append("**Extracted passage:**")
            lines.append("```")
            lines.append(item.passage)
            lines.append("```")
            lines.append("")

            # For matched GT items, show passage comparison
            for gi, mode in matched_gts:
                gt = gt_items[gi]
                analysis = _passage_analysis(item.passage, gt["passage"])
                lines.append(f"**Comparison with GT{gt['id']} ({gt.get('guidance', '')}):**")
                lines.append(f"> {analysis}")
                lines.append("")
                lines.append(f"**GT{gt['id']} passage (ground truth):**")
                lines.append("```")
                lines.append(gt["passage"])
                lines.append("```")
                lines.append("")

        # ── Missed GT items ───────────────────────────────────────────────
        missed = [(gi, gt) for gi, (gt, match) in enumerate(zip(gt_items, gt_match)) if match is None]
        if missed:
            lines.append("## Missed GT Items\n")
            lines.append("These GT guidance statements were NOT found in any extracted item.\n")

            for gi, gt in missed:
                # Find closest extracted item even though it didn't meet threshold
                best_idx, best_mode, best_sim = _best_match(gt["passage"], items)

                lines.append("---\n")
                lines.append(f"### ❌ GT{gt['id']} — {gt.get('guidance', '')}")
                lines.append(f"- Metric     : {gt.get('metric', '')}")
                lines.append(f"- Value      : {gt.get('guidance_value', '—')} {gt.get('guidance_unit', '')}")
                lines.append(f"- Timeline   : {gt.get('timeline', '')}")
                lines.append(f"- Scorable   : {gt.get('credibility_scorable', '')}")
                lines.append("")

                if best_idx is not None and best_sim > 0:
                    lines.append(f"**Closest extracted item:** Item {best_idx + 1} (similarity {best_sim:.2f}) — below match threshold")
                    lines.append("")
                    lines.append("**Closest extracted passage:**")
                    lines.append("```")
                    lines.append(items[best_idx].passage)
                    lines.append("```")
                    lines.append("")
                else:
                    lines.append("**Closest extracted passage:** None (0 similarity — content not extracted at all)\n")

                lines.append("**GT passage (what should have been extracted):**")
                lines.append("```")
                lines.append(gt["passage"])
                lines.append("```")
                lines.append("")

                # Diagnosis
                gt_words = len(gt["passage"].split())
                val_str  = gt.get("guidance_value", "")
                lines.append("**Diagnosis:**")
                if best_sim < 0.20:
                    lines.append("> Content not extracted at all — the chunk containing this passage was either filtered by Stage 1 or the LLM skipped it in both runs.")
                elif best_sim < 0.50:
                    lines.append("> Some overlap with an extracted item but very different content — LLM extracted nearby content but not this specific statement.")
                else:
                    lines.append("> High overlap with an extracted item but passage boundaries differ too much to meet the match threshold. Consider whether the GT passage boundary is correct.")
                lines.append("")

    # ── Overall summary ───────────────────────────────────────────────────
    lines.append("\n" + "=" * 72)
    lines.append("# Overall Summary")
    lines.append("=" * 72 + "\n")
    if total_gt:
        overall_recall = total_found / total_gt
        lines.append(f"- Total GT items      : {total_gt}")
        lines.append(f"- GT matched          : {total_found}")
        lines.append(f"- GT missed           : {total_gt - total_found}")
        lines.append(f"- Overall recall      : {total_found}/{total_gt} = {overall_recall:.0%}")
        lines.append(f"- Total items extracted: {total_extracted}")
        lines.append(f"- **Result: {'PASS ✅ (≥70%)' if overall_recall >= 0.70 else 'FAIL ❌ (<70%)'}**")
    lines.append("")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "all_companies_stage2_dump.md"
    out_path.write_text("\n".join(lines))
    print(f"\nWritten to {out_path}")


def main() -> None:
    slug_filter = sys.argv[1].lower() if len(sys.argv) > 1 else None
    companies   = [c for c in COMPANIES if not slug_filter or slug_filter in c["slug"]]
    dump_all(companies)


if __name__ == "__main__":
    main()
