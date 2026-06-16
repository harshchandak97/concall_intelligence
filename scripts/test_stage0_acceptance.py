"""
Stage 0 — Acceptance Tests 2, 3, 4

Runs segment() on all three target transcripts (Fineotex, Sandhar, Mold-Tek)
and checks:

  Test 2 — Chunk count sanity
      30-80 chunks expected for a ~60-page transcript.
      <10  -> speaker regex too strict (missing headers)
      >200 -> speaker regex too loose (splitting on non-headers)

  Test 3 — Q&A pairing coverage
      >= 60% of chunks should have is_qa_pair = True.

  Test 4 — GT item chunk containment [critical, must be 100%]
      Every ground truth passage must be findable inside exactly one chunk's
      text. A GT item not found in any chunk = Stage 0 failure.

      Matching approach:
      - GT passages often contain embedded "Speaker Name: ..." labels for
        multi-turn exchanges (e.g. analyst question + management answer).
        Stage 0 strips these header labels during turn-splitting, so they
        won't appear in chunk.text. We split the GT passage on these labels
        and check that every resulting text segment appears in the SAME
        chunk's text.
      - Comparison is done on whitespace-stripped, lowercased text so minor
        PDF line-break/spacing differences don't cause false failures.

Run: python test_stage0_acceptance.py
"""

import re
from pathlib import Path

from pipeline.stage0_segmenter import extract_pages_from_pdf, segment


COMPANIES = [
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

# Matches "Name:" or "First Last Title:" style labels embedded in GT passages
# at the start of the string, or right after sentence-ending punctuation.
# Used to strip speaker labels that Stage 0 removes during turn-splitting.
_SPEAKER_LABEL = re.compile(
    r"(?:^|(?<=[.?!]\s))([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,3}):\s"
)


def normalize(text: str) -> str:
    """Lowercase + strip all whitespace — robust to PDF spacing/line-break quirks."""
    return re.sub(r"\s+", "", text).lower()


def parse_ground_truth(gt_path: str):
    """
    Parse a ground truth file into a list of:
        {"id": "1", "passage": <full passage text>, "sub_texts": [...]}

    sub_texts = passage split on embedded speaker labels, with the labels
    themselves removed (these labels don't appear in chunk.text).
    """
    text = Path(gt_path).read_text()
    items = []

    for m in re.finditer(r"^id:\s*(\d+)\n", text, re.M):
        gt_id = m.group(1)
        rest = text[m.end():]

        pm = re.search(r'passage:\s*"(.*?)"\n(?=speaker:)', rest, re.S)
        if not pm:
            continue
        passage = pm.group(1)

        parts = _SPEAKER_LABEL.split(passage)
        # Even indices = text segments; odd indices = captured speaker names (discarded)
        sub_texts = [p for i, p in enumerate(parts) if i % 2 == 0 and p.strip()]

        items.append({"id": gt_id, "passage": passage, "sub_texts": sub_texts})

    return items


def find_containing_chunks(sub_texts, chunks):
    """Return chunk_ids where ALL sub_texts are found (normalized substring match)."""
    matches = []
    for chunk in chunks:
        norm_chunk = normalize(chunk.text)
        if all(normalize(st) in norm_chunk for st in sub_texts):
            matches.append(chunk.chunk_id)
    return matches


def run():
    overall_pass = True

    for company in COMPANIES:
        print(f"\n{'=' * 70}")
        print(f"  {company['name']}")
        print(f"{'=' * 70}")

        pages = extract_pages_from_pdf(company["pdf"])
        full_text = "".join(pages.values())
        chunks = segment(full_text, pages)

        # ── Test 2 — Chunk count sanity ─────────────────────────────────
        print(f"\nTest 2 — Chunk count: {len(chunks)}")
        if len(chunks) < 10:
            print("  WARNING: <10 chunks — speaker regex may be too strict")
            overall_pass = False
        elif len(chunks) > 200:
            print("  WARNING: >200 chunks — speaker regex may be too loose")
            overall_pass = False
        elif 30 <= len(chunks) <= 80:
            print("  PASS — within typical 30-80 range")
        else:
            print("  OK — within 10-200, outside typical 30-80 (check if expected)")

        # ── Test 3 — Q&A pairing coverage ───────────────────────────────
        qa_count = sum(1 for c in chunks if c.is_qa_pair)
        qa_pct = qa_count / len(chunks) if chunks else 0
        print(f"\nTest 3 — Q&A pairing: {qa_count}/{len(chunks)} = {qa_pct:.0%}")
        if qa_pct >= 0.6:
            print("  PASS — meets >=60% threshold")
        else:
            print("  WARNING — below 60% threshold")
            overall_pass = False

        # ── Test 4 — GT item chunk containment ──────────────────────────
        gt_items = parse_ground_truth(company["gt"])
        print(f"\nTest 4 — GT item containment ({len(gt_items)} GT items)")

        fail_count = 0
        for item in gt_items:
            matches = find_containing_chunks(item["sub_texts"], chunks)
            if len(matches) == 0:
                print(f"  FAIL  GT id {item['id']}: not found in any chunk")
                fail_count += 1
            elif len(matches) == 1:
                print(f"  PASS  GT id {item['id']}: found in {matches[0]}")
            else:
                print(f"  PASS  GT id {item['id']}: found in {len(matches)} chunks {matches} (check overlap)")

        if fail_count == 0:
            print(f"\n  Test 4 PASSED — all {len(gt_items)} GT items found")
        else:
            print(f"\n  Test 4 FAILED — {fail_count}/{len(gt_items)} GT items not found")
            overall_pass = False

    print(f"\n{'=' * 70}")
    print("OVERALL:", "PASS" if overall_pass else "FAIL — see warnings/failures above")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    run()
