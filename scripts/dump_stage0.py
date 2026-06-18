"""
dump_stage0.py — Manual review dump for Stage 0 output

For each target transcript, writes a markdown file showing:
  - Every final chunk: chunk_id, chunk_type, speaker, analyst_speaker,
    pages, word count, turn count, and full text
  - Summary table at the top: speaker, role, turn count per chunk_type

This is a read-only debug aid — it doesn't affect the pipeline or eval scripts.

Output: scripts/debug_output/{slug}_stage0_dump.md  (one file per company)

Run from project root: python scripts/dump_stage0.py
"""

import sys
from collections import Counter
from pathlib import Path

# Add project root so pipeline imports work from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.models import ChunkType
from pipeline.stage0_segmenter import segment


COMPANIES = [
    {
        "name": "Fineotex Chemical",
        "slug": "fineotex_chemical",
        "pdf": "transcripts/fineotex_chemical_Q4_FY26.pdf",
    },
    {
        "name": "Sandhar Technologies",
        "slug": "sandhar_technologies",
        "pdf": "transcripts/sandhar_technologies_Q4_FY26.pdf",
    },
    {
        "name": "Mold-Tek Packaging",
        "slug": "mold-tek_packaging",
        "pdf": "transcripts/mold-tek_packaging_Q4_FY26.pdf",
    },
    {
        "name": "Asian Paints Limited",
        "slug": "asian_paints",
        "pdf": "transcripts/asian_paints_Q4_FY26.pdf",
    }
]

OUTPUT_DIR = Path(__file__).parent / "debug_output"


def dump_company(company: dict) -> None:
    pdf_path = company["pdf"]
    if not Path(pdf_path).exists():
        print(f"{company['name']}: SKIPPED (PDF not found: {pdf_path})")
        return

    chunks = segment(pdf_path)

    type_counts = Counter(c.chunk_type.value for c in chunks)
    qa_count = type_counts[ChunkType.QA_SESSION.value]
    opening_count = type_counts[ChunkType.OPENING_REMARKS.value]
    solo_count = type_counts[ChunkType.MANAGEMENT_SOLO.value]

    lines: list[str] = []
    lines.append(f"# Stage 0 Dump — {company['name']}\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"- Total chunks      : {len(chunks)}")
    lines.append(f"- opening_remarks   : {opening_count}")
    lines.append(f"- qa_session        : {qa_count}")
    lines.append(f"- management_solo   : {solo_count}")
    lines.append("")

    # Chunk index table
    lines.append("## Chunk index\n")
    lines.append("| chunk_id | type | speaker | analyst | pages | words | turns |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in chunks:
        pages = f"{c.page_start}–{c.page_end}" if c.page_start != c.page_end else str(c.page_start)
        analyst = c.analyst_speaker or "—"
        lines.append(
            f"| {c.chunk_id} | {c.chunk_type.value} | {c.speaker} "
            f"| {analyst} | {pages} | {c.word_count} | {len(c.turns)} |"
        )
    lines.append("")

    # Full chunk text
    lines.append("## Chunks\n")
    for c in chunks:
        pages = f"{c.page_start}–{c.page_end}" if c.page_start != c.page_end else str(c.page_start)
        lines.append("---\n")
        lines.append(f"### {c.chunk_id}  ·  {c.chunk_type.value}")
        lines.append(f"- Speaker      : {c.speaker}")
        if c.analyst_speaker:
            lines.append(f"- Analyst      : {c.analyst_speaker}")
        lines.append(f"- Pages        : {pages}")
        lines.append(f"- Words        : {c.word_count}")
        lines.append(f"- Turns        : {len(c.turns)}")
        lines.append("")
        # Turn breakdown
        for t in c.turns:
            lines.append(f"  [{t.role.value}] {t.speaker}  (pg {t.page_start}–{t.page_end})")
        lines.append("")
        lines.append("```")
        lines.append(c.text)
        lines.append("```")
        lines.append("")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{company['slug']}_stage0_dump.md"
    out_path.write_text("\n".join(lines))
    print(
        f"{company['name']}: {len(chunks)} chunks "
        f"({opening_count} opening, {qa_count} qa, {solo_count} solo) -> {out_path}"
    )


def main() -> None:
    for company in COMPANIES:
        dump_company(company)


if __name__ == "__main__":
    main()
