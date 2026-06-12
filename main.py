import os
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
from schemas import ExtractionResult

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_prompt(prompt_path, transcript_text):
    with open(prompt_path, "r") as f:
        prompt = f.read()
    return prompt.replace("{transcript_text}", transcript_text)

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_forward_looking_statements(transcript_text) -> ExtractionResult:
    prompt = load_prompt("prompts/prompt_v9.txt", transcript_text)

    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        response_format=ExtractionResult,
        temperature=0
    )

    return response.choices[0].message.parsed

def main():
    pdf_path = "transcripts/asian_paints_Q4_FY26.pdf"

    print("Reading PDF...")
    transcript_text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(transcript_text)} characters\n")

    print("Extracting forward-looking statements...")
    result = extract_forward_looking_statements(transcript_text)

    print(f"\n--- EXTRACTED STATEMENTS ({len(result.items)} items) ---\n")
    for i, item in enumerate(result.items, 1):
        print(f"[{i}] {item.metric} | {item.guidance_value} {item.guidance_unit or ''} | {item.timeline} | scorable={item.credibility_scorable}")
        print(f"    Speaker: {item.speaker}")
        print(f"    Passage: {item.passage[:120]}...")
        print()

if __name__ == "__main__":
    main()