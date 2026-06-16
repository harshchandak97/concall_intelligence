from pypdf import PdfReader
from pipeline.stage0_segmenter import extract_pages_from_pdf, segment

pages = extract_pages_from_pdf("transcripts/fineotex_chemical_Q4_FY26.pdf")
full_text = "".join(pages.values())

chunks = segment(full_text, pages)

# Print all unique (speaker, role) pairs
seen = {}
for c in chunks:
    if c.speaker not in seen:
        seen[c.speaker] = c.role
for speaker, role in sorted(seen.items()):
    print(f"{role.value:12s}  {speaker}")