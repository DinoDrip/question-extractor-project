import pdfplumber
import re
import os
from pdf2image import convert_from_path
from fpdf import FPDF
from google import genai
from pydantic import BaseModel, Field, RootModel
from typing import List
import json

#SETUP
topic = "trigonometry"
output_type=1

#gemini API
os.environ["API_KEY"] = "AIzaSyBfl8UnfevofHqQi_YCUN2RHqw-DKwSTzs"
client = genai.Client(api_key=os.environ["API_KEY"])

class Question(BaseModel):
    page_number: int = Field(description="Page number where the question appears.")
    question_number: str = Field(description="Question label, e.g., '3(a)'")
    question_text: str = Field(description="Full text of the question.")
    start_line: int = Field(description="Line number where the question begins.")
    end_line: int = Field(description="Line number where the question ends.")
    matches_topic: bool = Field(description="Whether the question matches the topic.")

class QuestionList(RootModel[List[Question]]):
    pass

input_path = r"C:\Users\Sajee\Desktop\question-extractor-project\pdfs"
#pdf_path = r"c:\Users\Sajee\Desktop\question-extractor-project\pdfs\paper.pdf"
output_path = r"c:\Users\Sajee\Desktop\question-extractor-project\output"

def extract_pdf_text(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({
                "page_number": i + 1,
                "text": text
            })
    return pages

def build_full_text(pages):
    combined = ""
    for p in pages:
        combined += f"\n\n=== PAGE {p['page_number']} ===\n{p['text']}"
    return combined

def analyse_pdf_with_gemini(full_text, topic):
    prompt = f"""
You are analysing an exam paper.

Extract ALL questions from the text below.

For each question, return:
- page_number
- question_number
- question_text
- start_line
- end_line
- matches_topic (true if the question is semantically related to "{topic}")

Return ONLY JSON matching the provided schema.

PDF text:
{full_text}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": QuestionList.model_json_schema(),
        }
    )

    parsed = QuestionList.model_validate_json(response.text)
    return parsed.root

#regex for question numbers
question_pattern = re.compile(
    r"^(Q?\s*\d+(\([a-z]\))?(\([ivx]+\))?)[\.\)]?"
)


#PROCESS START
for filename in sorted(os.listdir(input_path)):
    if filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(input_path, filename)

        #build pdf
        results = []
        print()
        print("Scanning", filename+"...")
        pages = extract_pdf_text(pdf_path)
        full_text = build_full_text(pages)
        print("    Analysing with Gemini...")

        #gemini
        results = analyse_pdf_with_gemini(full_text, topic)
        print("    Found Matches:")
        for r in results:
            if r.matches_topic:
                print(f"    >Page {r.page_number} - Q{r.question_number}")
        print()

        #img process
        if output_type ==1:
            print("    Colating Images...")
            images = convert_from_path(pdf_path)
            for r in results:
                if r.matches_topic:
                    page_index = r.page_number - 1
                    img = images[page_index]
                    save_path = os.path.join(output_path, f"{filename}-question_page{page_index+1}.png")
                    img.save(save_path)
                    print(f"    >Cropped question from page {page_index+1}")
        print()

#turn into pdf
print("Compiling to PDF...")
pdf = FPDF()
pgdown = 0
for filename in sorted(os.listdir(output_path)):
    
    if filename.endswith(".png"):
        if output_type == 1:
            pdf.add_page()
            pdf.image(os.path.join(output_path, filename), x=0, y=0, w=210)
        elif output_type ==2:
            if pgdown > 180 or pgdown==0:
                pdf.add_page()
                pgdown = 10
            pdf.image(os.path.join(output_path, filename), x=0, y=pgdown, w=210)
            pgdown+=120

        
pdf.output(os.path.join(output_path, "final_questions.pdf"))
print("Done!")
