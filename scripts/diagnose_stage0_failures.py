"""
Diagnose Stage 0 Test 4 failures.

Part A — Fineotex: are GT1/GT2 a Stage-0 chunking problem or a GT-text
         problem (encoding mismatch / non-verbatim editing)?
         Checks each GT sub_text against the FULL transcript text
         (not individual chunks). If a sub_text isn't found even in the
         full text, the GT passage itself doesn't match the PDF verbatim.

Part B — Sandhar: fallback mode was triggered (<5 raw turns detected).
         Print raw turn count + (speaker, role) list + a text sample
         to identify the actual speaker-header format.

Part C — Mold-Tek: only 5 final chunks with no fallback. Same diagnostic
         as Part B to identify why so few turns/chunks resulted.

Run: python diagnose_stage0_failures.py
"""

from pipeline.stage0_segmenter import (
    extract_pages_from_pdf,
    _split_into_turns,
    _classify_roles,
)
from test_stage0_acceptance import parse_ground_truth, normalize


# ─────────────────────────────────────────────────────────────────────────────
# Part A — Fineotex GT1/GT2: GT-text issue vs Stage-0 chunking issue
# ─────────────────────────────────────────────────────────────────────────────

def part_a():
    print("=" * 70)
    print("PART A — Fineotex GT1/GT2: full-text containment check")
    print("=" * 70)

    pages = extract_pages_from_pdf("transcripts/fineotex_chemical_Q4_FY26.pdf")
    full_text = "".join(pages.values())
    norm_full = normalize(full_text)

    gt_items = parse_ground_truth("data/fineotex_chemical_Q4_FY26_ground_truth_v1.txt")

    for item in gt_items:
        print(f"\nGT id {item['id']}")
        for i, st in enumerate(item["sub_texts"]):
            found = normalize(st) in norm_full
            status = "FOUND in full transcript text" if found else "NOT FOUND in full transcript text"
            print(f"  sub_text[{i}]: {status}")
            if not found:
                print(f"    text (first 120 chars): {st[:120]!r}")
                # Binary search for the longest matching prefix to pinpoint
                # where the mismatch starts.
                norm_st = normalize(st)
                lo, hi = 0, len(norm_st)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if norm_st[:mid] in norm_full:
                        lo = mid
                    else:
                        hi = mid - 1
                print(f"    longest matching prefix: {lo}/{len(norm_st)} chars")
                if lo < len(norm_st):
                    print(f"    mismatch starts near: ...{norm_st[max(0,lo-15):lo]}<<<HERE>>>{norm_st[lo:lo+15]}...")


# ─────────────────────────────────────────────────────────────────────────────
# Part B / C — raw turn inspection for Sandhar and Mold-Tek
# ─────────────────────────────────────────────────────────────────────────────

def inspect_raw_turns(label: str, pdf_path: str, sample_chars: int = 2500):
    print("\n" + "=" * 70)
    print(f"PART — {label}: raw turn detection")
    print("=" * 70)

    pages = extract_pages_from_pdf(pdf_path)
    full_text = "".join(pages.values())

    raw_turns = _split_into_turns(full_text)
    print(f"\nTotal raw turns detected: {len(raw_turns)}")

    if raw_turns:
        turns_with_roles = _classify_roles(raw_turns)
        seen = {}
        for speaker, text, cs, ce, role in turns_with_roles:
            if speaker not in seen:
                seen[speaker] = role
        print(f"\n{'ROLE':<12} SPEAKER")
        print("-" * 40)
        for speaker, role in seen.items():
            print(f"{role.value:<12} {speaker}")

        print("\n--- All turns (speaker | role | text snippet) ---\n")
        for speaker, text, cs, ce, role in turns_with_roles:
            snippet = text[:70].replace("\n", " ")
            print(f"{role.value:<12} {speaker:<25} | {snippet}...")

    print(f"\n--- Raw extracted text — first {sample_chars} chars ---\n")
    print(full_text[:sample_chars])


def part_b():
    inspect_raw_turns("Sandhar Technologies", "transcripts/sandhar_technologies_Q4_FY26.pdf")


def part_c():
    inspect_raw_turns("Mold-Tek Packaging", "transcripts/mold-tek_packaging_Q4_FY26.pdf")


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
