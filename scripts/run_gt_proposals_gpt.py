"""
scripts/run_gt_proposals_gpt.py
================================
Runs the GT proposal prompt against GPT-5.5 for each of the 5 eval companies
and saves raw JSON candidates to:
  data/ground_truth_reference/{stem}_gpt.json

These are cross-family proposals (GPT-5.5) to complement the Opus 4.8 proposals
already at {stem}_opus.json. The union of both sets is human-adjudicated to
produce the final ground truth per plan.md Step 2B.

API spec:
  - Model: gpt-5.5
  - API: OpenAI Responses API (client.responses.create)
  - Reasoning: effort=high
  - Structured output: GT candidate JSON schema enforced via text.format
  - Temperature: omitted (gpt-5.5 only supports default)

Usage:
  python scripts/run_gt_proposals_gpt.py            # run all 5 companies
  python scripts/run_gt_proposals_gpt.py --company "Sandhar Technologies"  # single
  python scripts/run_gt_proposals_gpt.py --force    # re-run even if output exists

Skips a company if the output file already exists (use --force to override).
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
PROMPT_PATH = BASE_DIR / "prompts" / "gt_proposal_prompt.md"
OUTPUT_DIR = BASE_DIR / "data" / "ground_truth_reference"

# Call dates confirmed from the first two pages of each PDF.
COMPANIES = [
    {
        "name": "Asian Paints",
        "quarter": "Q4 FY26",
        "call_date": "May 29, 2026",
        "transcript": BASE_DIR / "transcripts" / "asian_paints_Q4_FY26.pdf",
        "output_stem": "asian_paints_Q4_FY26_gt_candidates",
    },
    {
        "name": "Fineotex Chemical",
        "quarter": "Q4 FY26",
        "call_date": "May 18, 2026",
        "transcript": BASE_DIR / "transcripts" / "fineotex_chemical_Q4_FY26.pdf",
        "output_stem": "fineotex_chemical_Q4_FY26_gt_candidates",
    },
    {
        "name": "Mold-Tek Packaging",
        "quarter": "Q4 FY26",
        "call_date": "May 11, 2026",
        "transcript": BASE_DIR / "transcripts" / "mold-tek_packaging_Q4_FY26.pdf",
        "output_stem": "mold-tek_packaging_Q4_FY26_gt_candidates",
    },
    {
        "name": "Sambhv Steel Tubes",
        "quarter": "Q4 FY26",
        "call_date": "May 11, 2026",
        "transcript": BASE_DIR / "transcripts" / "Sambhv_Steel_Tubes-Q4_FY26.pdf",
        "output_stem": "sambhv_steel_tubes_Q4_FY26_gt_candidates",
    },
    {
        "name": "Sandhar Technologies",
        "quarter": "Q4 FY26",
        "call_date": "May 25, 2026",
        "transcript": BASE_DIR / "transcripts" / "sandhar_technologies_Q4_FY26.pdf",
        "output_stem": "sandhar_technologies_Q4_FY26_gt_candidates",
    },
]

MODEL = "gpt-5.5"


def load_system_prompt() -> str:
    """
    Extract the model-facing prompt from gt_proposal_prompt.md.
    Strips the human-readable preamble (everything before ## YOUR ROLE)
    and the INPUTS section (filled dynamically per company).
    """
    raw = PROMPT_PATH.read_text()
    start = raw.index("## YOUR ROLE")
    end = raw.index("## INPUTS")
    return raw[start:end].strip()


def build_user_message(company: dict, transcript_text: str) -> str:
    return (
        "## INPUTS\n\n"
        f"- **Company:** {company['name']}\n"
        f"- **Quarter / period:** {company['quarter']}\n"
        f"- **Call date:** {company['call_date']}\n"
        f"- **Transcript:**\n\n{transcript_text}\n\n"
        "---\n\n"
        "Now produce the JSON object of candidates. Be exhaustive, quote verbatim, "
        "tag per the two-gate model, and flag every uncertain item."
    )


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "".join(page.extract_text() or "" for page in reader.pages)


GT_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "quarter": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "integer"},
                    "passage": {"type": "string"},
                    "speaker": {"type": "string"},
                    "page_number": {"type": ["integer", "null"]},
                    "section": {"type": "string", "enum": ["opening_remarks", "qa"]},
                    "metric": {"type": "string"},
                    "metric_is_novel": {"type": "boolean"},
                    "guidance_value": {"type": ["string", "null"]},
                    "guidance_unit": {"type": ["string", "null"]},
                    "timeline": {"type": ["string", "null"]},
                    "horizon": {"type": "string", "enum": ["near", "medium", "long"]},
                    "level": {"type": "string", "enum": ["company", "segment", "geography"]},
                    "track": {"type": "string", "enum": ["A", "B"]},
                    "credibility_scorable": {"type": "boolean"},
                    "uncertain": {"type": "boolean"},
                    "adjudication_note": {"type": ["string", "null"]},
                },
                "required": [
                    "candidate_id", "passage", "speaker", "page_number",
                    "section", "metric", "metric_is_novel", "guidance_value",
                    "guidance_unit", "timeline", "horizon", "level", "track",
                    "credibility_scorable", "uncertain", "adjudication_note",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["company", "quarter", "candidates"],
    "additionalProperties": False,
}


def run_company(client: OpenAI, system_prompt: str, company: dict, force: bool) -> None:
    out_path = OUTPUT_DIR / f"{company['output_stem']}_gpt.json"

    if out_path.exists() and not force:
        print(f"  SKIP (already exists): {out_path.name}  — use --force to re-run")
        return

    if not company["transcript"].exists():
        print(f"  SKIP — transcript not found: {company['transcript']}")
        return

    print(f"  Reading PDF: {company['transcript'].name}")
    transcript_text = extract_pdf_text(company["transcript"])

    user_msg = build_user_message(company, transcript_text)

    print(f"  Calling {MODEL} (Responses API, reasoning=high) ...")
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        reasoning={"effort": "high"},
        text={
            "format": {
                "type": "json_schema",
                "name": "gt_candidates",
                "schema": GT_SCHEMA,
                "strict": True,
            }
        },
    )

    raw_content = response.output_text
    if response.usage:
        print(
            f"  Tokens — input: {response.usage.input_tokens}, "
            f"output: {response.usage.output_tokens}"
        )

    data = json.loads(raw_content)
    data.setdefault("company", company["name"])
    data.setdefault("quarter", company["quarter"])

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    candidate_count = len(data.get("candidates", []))
    print(f"  Saved: {out_path.name} ({candidate_count} candidates)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GT proposals via GPT-5.5")
    parser.add_argument(
        "--company",
        help="Run only this company (substring match on name). Omit to run all.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even if output file already exists.",
    )
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    system_prompt = load_system_prompt()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = COMPANIES
    if args.company:
        targets = [c for c in COMPANIES if args.company.lower() in c["name"].lower()]
        if not targets:
            print(f"No company matched '{args.company}'. Available: {[c['name'] for c in COMPANIES]}")
            return

    for company in targets:
        print(f"\n{'='*60}")
        print(f"{company['name']} | {company['quarter']} | call: {company['call_date']}")
        try:
            run_company(client, system_prompt, company, args.force)
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
