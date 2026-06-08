from json import load
import os
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

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

def extract_forward_looking_statements(transcript_text):
    prompt = load_prompt("prompts/prompt_v8.txt", transcript_text)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content

def main():
    pdf_path = "transcripts/asian_paints_Q4_FY26.pdf"

    print("Reading PDF...")
    transcript_text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(transcript_text)} characters\n")

    print("Extracting forward-looking statements...")
    result = extract_forward_looking_statements(transcript_text)

    print("\n--- EXTRACTED STATEMENTS ---\n")
    print(result)

if __name__ == "__main__":
    main()