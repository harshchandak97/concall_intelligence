"""
Debug script — Test 1 (the REAL one): speaker detection completeness.

This prints the intermediate (speaker, role) list BEFORE Q&A pairing/collapsing
happens in Step 3. This is what Test 1 in the spec is meant to check:
  - All known management names -> management
  - No management speaker misclassified as analyst
  - Moderator correctly identified
  - Analyst names show up as analyst

Usage: python raw_turns_check.py
"""

from pipeline.stage0_segmenter import (
    extract_pages_from_pdf,
    _split_into_turns,
    _classify_roles,
)

PDF_PATH = "transcripts/fineotex_chemical_Q4_FY26.pdf"

pages = extract_pages_from_pdf(PDF_PATH)
full_text = "".join(pages.values())

# Step 1: raw turns (speaker, text, char_start, char_end)
raw_turns = _split_into_turns(full_text)
print(f"Total raw turns detected: {len(raw_turns)}\n")

# Step 2: roles assigned
turns_with_roles = _classify_roles(raw_turns)

# Print unique (speaker, role) pairs in order of first appearance
seen = {}
for speaker, text, cs, ce, role in turns_with_roles:
    if speaker not in seen:
        seen[speaker] = role

print(f"{'ROLE':<12} SPEAKER")
print("-" * 40)
for speaker, role in seen.items():
    print(f"{role.value:<12} {speaker}")

print(f"\nTotal unique speakers: {len(seen)}")

# Optional: print first few turns with a text snippet, so you can sanity-check
# that the (speaker, role, text) mapping looks right
print("\n--- First 10 turns (speaker | role | text snippet) ---\n")
for speaker, text, cs, ce, role in turns_with_roles[:10]:
    snippet = text[:80].replace("\n", " ")
    print(f"{role.value:<12} {speaker:<25} | {snippet}...")
