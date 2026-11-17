import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found. Check your .env file.")

client = OpenAI(api_key=api_key)

question = input("Ask the AI a question: ")

response = client.responses.create(
    model="gpt-5.6",
    input=question
)

print("\nAI ANSWER:\n")
print(response.output_text)