"""
Quick diagnostic — print raw pypdf-extracted text around the Q&A section
to check whether speaker names and their text appear adjacent and in order.

Usage: python raw_text_check.py
"""

from pypdf import PdfReader

PDF_PATH = "transcripts/fineotex_chemical_Q4_FY26.pdf"

reader = PdfReader(PDF_PATH)

# Print each page's raw extracted text, page by page, so we can see
# exactly how pypdf ordered the text — including where speaker names
# land relative to their statements.
for i, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""
    print(f"\n{'='*30} PAGE {i} {'='*30}\n")
    print(text)

    # Stop after we've printed a few pages past the start of Q&A
    # (first question is usually around page 4-6). Adjust as needed.
    if i >= 6:
        break
