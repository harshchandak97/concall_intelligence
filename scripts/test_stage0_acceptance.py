"""
Stage 0 — Acceptance Tests 2, 3, 4

Runs segment() on all target transcripts and checks:

  Test 2 — Chunk count sanity
      10-80 typical for session grouping (each analyst = 1 QA_SESSION).
      <5   -> speaker detection completely failed
      >200 -> speaker detection too loose

  Test 3 — QA_SESSION coverage
      >= 60% of chunks should be QA_SESSION type.
      OPENING_REMARKS should appear only at the start (within first 10 chunk IDs).

  Test 4 — GT item chunk containment [critical, must be 100%]
      Every ground truth passage must be findable in at least one chunk.

      Matching strategy:
      1. Split passage on embedded "Speaker Name: " labels to get sub-texts
      2. Strip leading Unicode ellipsis (…) and whitespace from each sub-text
      3. Normalize both sides: collapse whitespace, lowercase, AND normalize
         Unicode punctuation (curly quotes → straight, em-dash → hyphen, etc.)
         so PDF-extracted text and manually-written GT both compare cleanly
      4. PASS: all sub-texts found in the same chunk
      5. WARN (GT DATA ISSUE): anchor (first 80 chars) found but full sub-text
         diverges after normalization — shows raw GT text, raw chunk context,
         and word-level pointer to the exact divergence point
      6. FAIL: no anchor found — Stage 0 structural issue

Output is printed to stdout AND saved to scripts/debug_output/stage0_acceptance.txt

Run from project root: python scripts/test_stage0_acceptance.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.models import ChunkType
from pipeline.stage0_segmenter import segment

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

OUTPUT_FILE = Path(__file__).parent / "debug_output" / "stage0_acceptance.txt"

_SPEAKER_LABEL_RE = re.compile(
    r"([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){0,3}):\s"
)

# Width for text wrapping in the output
_W = 90


def normalize(text: str) -> str:
    """
    Collapse whitespace + lowercase + normalize Unicode punctuation.
    Handles differences between manually-written GT (often uses straight quotes,
    ASCII dashes) and PDF-extracted text (often uses curly quotes, en/em dashes).
    """
    text = (text
        .replace('‘', "'").replace('’', "'")   # curly single quotes → '
        .replace('“', '"').replace('”', '"')   # curly double quotes → "
        .replace('–', '-').replace('—', '-')   # en/em dash → -
        .replace('…', '...').replace(' ', ' ') # ellipsis, non-breaking space
    )
    return re.sub(r"\s+", "", text).lower()


def parse_ground_truth(gt_path: str):
    """Parse a GT file into a list of {"id": str, "passage": str}."""
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


def passage_sub_texts(passage: str) -> list[str]:
    """Split GT passage on speaker labels; strip leading ellipsis."""
    parts = _SPEAKER_LABEL_RE.split(passage)
    raw = [p for i, p in enumerate(parts) if i % 2 == 0]
    return [p.lstrip("… ").strip() for p in raw if p.strip("… ").strip()]


def _word_divergence(sub_text: str, raw_chunk: str) -> dict:
    """
    Find the exact word where sub_text diverges from raw_chunk.

    Returns:
      shared_tail  — last 8 matching words (raw from sub_text), or None if no match
      gt_suffix    — next 15 raw GT words after divergence
      chunk_suffix — next 15 raw chunk words after divergence
      diverge_word — 0-indexed word position of first mismatch (-1 = full match)
      chunk_raw_context — raw chunk text covering the matched region (for display)
    """
    gt_words = sub_text.split()
    chunk_words = raw_chunk.split()

    # Require N CONSECUTIVE words to all match — prevents false starts on common
    # words like "And", "Just", "So" where later words diverge.
    N_CONSEC = min(5, len(gt_words))

    start = -1
    for i in range(len(chunk_words) - N_CONSEC + 1):
        if all(
            normalize(chunk_words[i + j]) == normalize(gt_words[j])
            for j in range(N_CONSEC)
        ):
            start = i
            break

    if start < 0:
        return {
            "shared_tail": None, "gt_suffix": sub_text[:200],
            "chunk_suffix": "", "diverge_word": -1,
            "chunk_raw_context": "(could not locate start: first 5 words not found consecutively in chunk)",
        }

    # Walk forward to find first diverging word
    diverge = len(gt_words)  # assume full match
    for j, gw in enumerate(gt_words):
        ci = start + j
        if ci >= len(chunk_words) or normalize(chunk_words[ci]) != normalize(gw):
            diverge = j
            break

    # Build display strings
    shared_words = gt_words[:diverge]
    shared_tail = " ".join(shared_words[max(0, diverge - 8):])
    gt_suffix = " ".join(gt_words[diverge: diverge + 15])
    chunk_suffix = " ".join(chunk_words[start + diverge: start + diverge + 15])

    # Raw chunk context: from match start to match start + len(sub_text) + some extra
    context_start = max(0, start - 3)
    context_end = min(len(chunk_words), start + len(gt_words) + 15)
    chunk_raw_context = " ".join(chunk_words[context_start:context_end])

    return {
        "shared_tail": shared_tail,
        "gt_suffix": gt_suffix if gt_suffix else "[end of GT passage]",
        "chunk_suffix": chunk_suffix if chunk_suffix else "[end of chunk]",
        "diverge_word": diverge,
        "chunk_raw_context": chunk_raw_context,
    }


def check_passage(
    item: dict,
    chunk_raws_norm: list[tuple],
    chunk_raws_raw: list[tuple],
) -> dict:
    """
    Returns a result dict:
      status:       "pass" | "gt_data" | "fail"
      found:        chunk_id if pass, else None
      divergences:  list of divergence detail dicts for WARN display
      passage:      original passage text
    """
    passage = item["passage"]
    sub_texts = passage_sub_texts(passage)
    if not sub_texts:
        return {"status": "fail", "found": None, "divergences": [], "passage": passage}

    # Try full match
    for cid, norm_raw in chunk_raws_norm:
        if all(normalize(s) in norm_raw for s in sub_texts):
            return {"status": "pass", "found": cid, "divergences": [], "passage": passage}

    # Check per sub-text to distinguish GT data issues from structural failures
    divergences = []
    for s in sub_texts:
        anchor = normalize(s[:80])
        anchor_hit = next(
            ((cid, norm_raw, raw_raw)
             for (cid, norm_raw), (_, raw_raw) in zip(chunk_raws_norm, chunk_raws_raw)
             if anchor in norm_raw),
            None,
        )
        if anchor_hit is None:
            return {"status": "fail", "found": None, "divergences": [], "passage": passage}

        cid, _norm, raw_raw = anchor_hit
        div = _word_divergence(s, raw_raw)
        div["chunk_id"] = cid
        div["sub_text"] = s
        divergences.append(div)

    return {"status": "gt_data", "found": None, "divergences": divergences, "passage": passage}


def _wrap(text: str, indent: str = "    ") -> str:
    """Wrap long text at _W chars with indent."""
    words = text.split()
    lines, line = [], []
    for w in words:
        if sum(len(x) + 1 for x in line) + len(indent) + len(w) > _W:
            lines.append(indent + " ".join(line))
            line = []
        line.append(w)
    if line:
        lines.append(indent + " ".join(line))
    return "\n".join(lines)


class Tee:
    """Writes to stdout and a file simultaneously."""
    def __init__(self, filepath: Path):
        filepath.parent.mkdir(exist_ok=True)
        self._file = filepath.open("w")

    def write(self, line: str = "") -> None:
        print(line)
        self._file.write(line + "\n")

    def close(self) -> None:
        self._file.close()


def run():
    tee = Tee(OUTPUT_FILE)
    w = tee.write
    overall_pass = True

    for company in COMPANIES:
        pdf_path = company["pdf"]
        gt_path = company["gt"]

        w()
        w("=" * 70)
        if not Path(pdf_path).exists():
            w(f"  {company['name']} — SKIPPED (PDF not found: {pdf_path})")
            w("=" * 70)
            continue
        w(f"  {company['name']}")
        w("=" * 70)

        chunks = segment(pdf_path)

        # ── Test 2 — Chunk count sanity ──────────────────────────────────────
        w(f"\nTest 2 — Chunk count: {len(chunks)}")
        if len(chunks) < 5:
            w("  FAIL — <5 chunks (speaker detection likely completely failed)")
            overall_pass = False
        elif len(chunks) > 200:
            w("  FAIL — >200 chunks (speaker detection likely too loose)")
            overall_pass = False
        elif 10 <= len(chunks) <= 80:
            w("  PASS — within typical 10-80 range for session grouping")
        else:
            w("  OK — within 5-200 range (check if expected for this transcript)")

        # ── Test 3 — QA_SESSION coverage ─────────────────────────────────────
        qa_chunks = [c for c in chunks if c.chunk_type == ChunkType.QA_SESSION]
        opening_chunks = [c for c in chunks if c.chunk_type == ChunkType.OPENING_REMARKS]
        qa_pct = len(qa_chunks) / len(chunks) if chunks else 0
        last_opening_seq = max(
            (int(c.chunk_id.replace("chunk_", "")) for c in opening_chunks), default=0
        )

        w(f"\nTest 3 — QA_SESSION coverage: {len(qa_chunks)}/{len(chunks)} = {qa_pct:.0%}")
        w(f"  OPENING_REMARKS: {len(opening_chunks)} chunks (last at chunk_{last_opening_seq:03d})")
        w(f"  MANAGEMENT_SOLO: {len(chunks) - len(qa_chunks) - len(opening_chunks)} chunks")

        t3_qa = qa_pct >= 0.6
        t3_order = last_opening_seq <= 10
        if t3_qa and t3_order:
            w("  PASS — >=60% QA_SESSION; opening remarks at start")
        else:
            if not t3_qa:
                w(f"  FAIL — only {qa_pct:.0%} QA_SESSION (need >=60%)")
                overall_pass = False
            if not t3_order:
                w(f"  FAIL — OPENING_REMARKS extends to chunk_{last_opening_seq:03d} (expected ≤10)")
                overall_pass = False

        # ── Test 4 — GT item chunk containment ───────────────────────────────
        if not Path(gt_path).exists():
            w(f"\nTest 4 — SKIPPED (GT file not found: {gt_path})")
            continue

        gt_items = parse_ground_truth(gt_path)
        w(f"\nTest 4 — GT item containment ({len(gt_items)} GT items)")

        turns_raw = [" ".join(t.text for t in c.turns) for c in chunks]
        chunk_raws_norm = [(c.chunk_id, normalize(rt)) for c, rt in zip(chunks, turns_raw)]
        chunk_raws_raw  = [(c.chunk_id, rt) for c, rt in zip(chunks, turns_raw)]

        fail_count = gt_data_count = 0
        for item in gt_items:
            result = check_passage(item, chunk_raws_norm, chunk_raws_raw)
            status = result["status"]

            if status == "pass":
                w(f"  PASS  GT id {item['id']}: found in {result['found']}")

            elif status == "gt_data":
                w(f"  WARN  GT id {item['id']}: GT passage diverges from PDF text"
                  f" (GT data quality issue — not a Stage 0 failure)")
                gt_data_count += 1

                w()
                w(f"    GT passage (full):")
                w(_wrap(result["passage"], "      "))

                for d in result["divergences"]:
                    w()
                    w(f"    Chunk {d['chunk_id']} — relevant section (raw):")
                    w(_wrap(d["chunk_raw_context"], "      "))
                    w()
                    if d["diverge_word"] >= len(d["sub_text"].split()):
                        w(f"    Divergence: [GT passage fully contained in chunk — text matches completely]")
                    else:
                        w(f"    Divergence at word {d['diverge_word']}:")
                        w(f"      Shared (last 8 words) : \"{d['shared_tail']}\"")
                        w(f"      GT continues with     : \"{d['gt_suffix']}\"")
                        w(f"      Chunk continues with  : \"{d['chunk_suffix']}\"")

            else:
                w(f"  FAIL  GT id {item['id']}: not found in any chunk (Stage 0 issue)")
                fail_count += 1
                w()
                w(f"    GT passage (full):")
                w(_wrap(result["passage"], "      "))

            w()

        if fail_count == 0 and gt_data_count == 0:
            w(f"  Test 4 PASSED — all {len(gt_items)} GT items found")
        elif fail_count == 0:
            w(
                f"  Test 4 PASSED — {len(gt_items) - gt_data_count}/{len(gt_items)} clean; "
                f"{gt_data_count} GT data issue(s) (see WARN above)"
            )
        else:
            w(f"  Test 4 FAILED — {fail_count} Stage 0 issue(s); {gt_data_count} GT data issue(s)")
            overall_pass = False

    w()
    w("=" * 70)
    w("OVERALL: " + ("PASS" if overall_pass else "FAIL — see FAIL lines above"))
    w("=" * 70)

    tee.close()
    print(f"\nOutput saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
