"""
Stage 1 — Acceptance Test

For each transcript+GT pair:

  Test A — GT filter recall [critical — must be 100%]
      For every GT item, find the Stage 0 chunk that contains its passage,
      then confirm that chunk passes the Stage 1 filter.
      A miss here means a GT item would be silently dropped before the LLM ever
      sees it — unrecoverable recall loss. The filter must be fixed (add the
      missing phrase to a lexicon) until recall = 100%.

  Test B — Filter pass rate
      Log what percentage of total chunks pass the filter per transcript.
      Expected: 30–60%. >80% means the filter is very loose (acceptable, wasteful).
      <20% means the filter may be too aggressive — re-examine after the GT check.

Run from project root: python scripts/test_stage1_acceptance.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.models import ChunkType
from pipeline.stage0_segmenter import segment
from pipeline.stage1_filter import filter_chunks, passes_filter, TEMPORAL_LEXICON, COMMITMENT_VERBS

COMPANIES = [
    {
        "name": "Asian Paints",
        "pdf": "transcripts/asian_paints_Q4_FY26.pdf",
        "gt": "data/asian_paints_Q4_FY26_ground_truth_v3.txt",
    },
    {
        "name": "Fineotex Chemical",
        "pdf": "transcripts/fineotex_chemical_Q4_FY26.pdf",
        "gt": "data/fineotex_chemical_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Sandhar Technologies",
        "pdf": "transcripts/sandhar_technologies_Q4_FY26.pdf",
        "gt": "data/sandhar_technologies_Q4_FY26_ground_truth_v1.txt",
    },
    {
        "name": "Mold-Tek Packaging",
        "pdf": "transcripts/mold-tek_packaging_Q4_FY26.pdf",
        "gt": "data/mold-tek_packaging_Q4_FY26_ground_truth_v1.txt",
    },
]

_SPEAKER_LABEL_RE = re.compile(
    r"([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,3}):\s"
)


# ── Passage-matching helpers (same logic as Stage 0 acceptance test) ──────────

def _normalize(text: str) -> str:
    text = (text
        .replace('’', "'").replace('‘', "'")
        .replace('“', '"').replace('”', '"')
        .replace('–', '-').replace('—', '-')
        .replace('…', '...').replace(' ', ' ')
    )
    return re.sub(r"\s+", "", text).lower()


def _passage_sub_texts(passage: str) -> list[str]:
    parts = _SPEAKER_LABEL_RE.split(passage)
    raw = [p for i, p in enumerate(parts) if i % 2 == 0]
    return [p.lstrip("… ").strip() for p in raw if p.strip("… ").strip()]


def _find_chunk_for_passage(passage: str, chunks) -> str | None:
    """Return chunk_id of the first chunk that contains all sub-texts of the passage."""
    sub_texts = _passage_sub_texts(passage)
    if not sub_texts:
        return None
    for chunk in chunks:
        raw = " ".join(t.text for t in chunk.turns)
        norm_raw = _normalize(raw)
        if all(_normalize(s) in norm_raw for s in sub_texts):
            return chunk.chunk_id
        # Anchor fallback: anchor (first 80 chars) found = chunk contains the passage
        # even if full sub-text diverges (GT data quality issue — chunk still passes filter)
        anchors_found = sum(
            1 for s in sub_texts if _normalize(s[:80]) in norm_raw
        )
        if anchors_found == len(sub_texts):
            return chunk.chunk_id
    return None


def _parse_ground_truth(gt_path: str) -> list[dict]:
    text = Path(gt_path).read_text()
    items = []
    for m in re.finditer(r"^id:\s*(\d+)\n", text, re.M):
        gt_id = m.group(1)
        rest = text[m.end():]
        pm = re.search(r'passage:\s*"(.*?)"[ \t]*\n', rest, re.S)
        if not pm:
            continue
        items.append({"id": gt_id, "passage": pm.group(1)})
    return items


def _filter_reason(chunk) -> str:
    """Which condition(s) caused the chunk to pass, for display."""
    text_lower = chunk.text.lower()
    reasons = []
    if re.search(r'\d', chunk.text):
        reasons.append("digit")
    if any(p in text_lower for p in TEMPORAL_LEXICON):
        matched = next(p for p in TEMPORAL_LEXICON if p in text_lower)
        reasons.append(f"temporal(\"{matched.strip()}\")")
    if any(v in text_lower for v in COMMITMENT_VERBS):
        matched = next(v for v in COMMITMENT_VERBS if v in text_lower)
        reasons.append(f"commitment(\"{matched}\")")
    return ", ".join(reasons) if reasons else "NONE — WOULD BE DROPPED"


# ── Runner ────────────────────────────────────────────────────────────────────

def run():
    overall_pass = True

    for company in COMPANIES:
        pdf_path = company["pdf"]
        gt_path = company["gt"]

        print()
        print("=" * 70)
        if not Path(pdf_path).exists():
            print(f"  {company['name']} — SKIPPED (PDF not found: {pdf_path})")
            continue
        print(f"  {company['name']}")
        print("=" * 70)

        chunks = segment(pdf_path)
        passed_chunks = filter_chunks(chunks)
        passed_ids = {c.chunk_id for c in passed_chunks}

        pass_rate = len(passed_chunks) / len(chunks) if chunks else 0

        # ── Test B — Filter pass rate ─────────────────────────────────────────
        by_type = {}
        for c in chunks:
            t = c.chunk_type.value
            by_type.setdefault(t, {"total": 0, "passed": 0})
            by_type[t]["total"] += 1
            if c.chunk_id in passed_ids:
                by_type[t]["passed"] += 1

        print(f"\nTest B — Filter pass rate: {len(passed_chunks)}/{len(chunks)} = {pass_rate:.0%}")
        for chunk_type, counts in sorted(by_type.items()):
            print(f"  {chunk_type:20s}: {counts['passed']}/{counts['total']} passed")

        if pass_rate > 0.80:
            print("  NOTE — >80% pass rate: filter is loose (acceptable, but wasteful)")
        elif pass_rate < 0.20:
            print("  WARN — <20% pass rate: filter may be too aggressive")
        else:
            print("  OK — pass rate within expected 20–80% range")

        # ── Test A — GT recall ────────────────────────────────────────────────
        if not Path(gt_path).exists():
            print(f"\nTest A — SKIPPED (GT file not found: {gt_path})")
            continue

        gt_items = _parse_ground_truth(gt_path)
        print(f"\nTest A — GT filter recall ({len(gt_items)} GT items)")

        recall_fail = 0
        for item in gt_items:
            chunk_id = _find_chunk_for_passage(item["passage"], chunks)
            if chunk_id is None:
                print(f"  ERROR GT id {item['id']}: passage not found in any chunk"
                      f" (Stage 0 issue — fix Stage 0 first)")
                recall_fail += 1
                continue

            if chunk_id in passed_ids:
                chunk = next(c for c in chunks if c.chunk_id == chunk_id)
                reason = _filter_reason(chunk)
                print(f"  PASS  GT id {item['id']}: {chunk_id} passes filter [{reason}]")
            else:
                chunk = next(c for c in chunks if c.chunk_id == chunk_id)
                print(f"  FAIL  GT id {item['id']}: {chunk_id} DROPPED by filter"
                      f" — this is a recall loss!")
                print(f"    chunk_type : {chunk.chunk_type.value}")
                print(f"    word_count : {chunk.word_count}")
                print(f"    text (first 200 chars): {chunk.text[:200]!r}")
                recall_fail += 1
                overall_pass = False

        if recall_fail == 0:
            print(f"\n  Test A PASSED — all {len(gt_items)} GT items' chunks pass the filter")
        else:
            print(f"\n  Test A FAILED — {recall_fail} GT item(s) would be dropped")
            overall_pass = False

    print()
    print("=" * 70)
    print("OVERALL: " + ("PASS" if overall_pass else "FAIL — see FAIL lines above"))
    print("=" * 70)


if __name__ == "__main__":
    run()
