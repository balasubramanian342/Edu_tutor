"""
Quick standalone connectivity check for the Gemini API — run this on its
own (python test_gemini.py) to confirm your GEMINI_API_KEY works before
starting the full server. Doesn't touch retrieval or any other project
code, just the raw API call.
"""
from dotenv import load_dotenv
import os
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

if not api_key or api_key.lower().startswith("your_"):
    raise SystemExit(
        "GEMINI_API_KEY is not set in .env. Get a free key at "
        "https://aistudio.google.com/apikey and add it to .env first."
    )

client = genai.Client(api_key=api_key)

interaction = client.interactions.create(
    model=model,
    input="Say hello and confirm that the Gemini API is working.",
)

print(interaction.output_text)
