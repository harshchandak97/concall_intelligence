"""
dump_stage0.py — Manual review dump for Stage 0 output

For each target transcript, writes a markdown file showing:
  - Management roster extracted from the participant list (or fallback note)
  - Speaker -> role -> turn count summary, from raw turns before Q&A pairing
  - Every final chunk: chunk_id, speaker, role, pages, is_qa_pair, word count,
    and full text

This is a read-only debug aid — it doesn't affect the pipeline or eval scripts.

Output: debug_output/{company_slug}_stage0_dump.md  (one file per company)

Run: python dump_stage0.py
"""

from pathlib import Path
from collections import Counter, OrderedDict

from pipeline.stage0_segmenter import (
    extract_pages_from_pdf,
    segment,
    _extract_management_roster,
    _split_into_turns,
    _classify_roles,
)

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
]

OUTPUT_DIR = Path("debug_output")


def dump_company(company: dict) -> None:
    pages = extract_pages_from_pdf(company["pdf"])
    full_text = "".join(pages.values())

    # --- Management roster (from participant-list header) ------------------
    roster = _extract_management_roster(full_text)

    # --- Raw turns + role classification (before Q&A pairing) --------------
    raw_turns = _split_into_turns(full_text)
    turns_with_roles = _classify_roles(raw_turns, roster)

    speaker_roles: "OrderedDict[str, str]" = OrderedDict()
    speaker_counts: Counter = Counter()
    for speaker, _text, _cs, _ce, role in turns_with_roles:
        speaker_roles[speaker] = role.value
        speaker_counts[speaker] += 1

    # --- Final chunks (Stage 0 output) --------------------------------------
    chunks = segment(full_text, pages)
    qa_count = sum(1 for c in chunks if c.is_qa_pair)

    lines: list[str] = []
    lines.append(f"# Stage 0 Dump — {company['name']}\n")

    # Roster section
    lines.append("## Management roster (from participant list)\n")
    if roster:
        for name in sorted(roster):
            lines.append(f"- {name}")
    else:
        lines.append(
            "_No participant-list roster found — fallback heuristic used "
            "(first 4 non-moderator speakers from raw turns)._"
        )
    lines.append("")

    # Speaker summary section
    lines.append("## Speaker summary (raw turns, before Q&A pairing)\n")
    lines.append(f"Total raw turns: {len(raw_turns)}\n")
    lines.append("| Speaker | Role | Turn count |")
    lines.append("|---|---|---|")
    for speaker, role in speaker_roles.items():
        lines.append(f"| {speaker} | {role} | {speaker_counts[speaker]} |")
    lines.append("")

    # Chunks section
    lines.append(
        f"## Chunks — {len(chunks)} total "
        f"({qa_count} Q&A pairs, {len(chunks) - qa_count} solo management)\n"
    )

    for c in chunks:
        wc = len(c.text.split())
        lines.append("---\n")
        lines.append(f"### {c.chunk_id}")
        lines.append(f"- Speaker: {c.speaker}")
        lines.append(f"- Role: {c.role.value}")
        lines.append(f"- Pages: {c.page_start}-{c.page_end}")
        lines.append(f"- Q&A pair: {c.is_qa_pair}")
        lines.append(f"- Word count: {wc}")
        lines.append("")
        lines.append("```")
        lines.append(c.text)
        lines.append("```")
        lines.append("")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{company['slug']}_stage0_dump.md"
    out_path.write_text("\n".join(lines))
    print(
        f"{company['name']}: {len(chunks)} chunks, "
        f"{len(speaker_roles)} unique speakers -> {out_path}"
    )


def main() -> None:
    for company in COMPANIES:
        dump_company(company)


if __name__ == "__main__":
    main()
