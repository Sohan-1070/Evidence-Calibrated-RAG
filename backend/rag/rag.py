from pathlib import Path

import faiss
import numpy as np
import ollama

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ==================================================
# PATHS
# ==================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PDF_PATH = BASE_DIR / "data" / "oxford_student_handbook.pdf"


# ==================================================
# LOAD EMBEDDING MODEL
# ==================================================

print("Loading embedding model...")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

print("Embedding model loaded.")


# ==================================================
# READ PDF
# ==================================================

def extract_text(pdf_path):

    reader = PdfReader(str(pdf_path))

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text()

        if text:

            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


# ==================================================
# CREATE CHUNKS
# ==================================================

def create_chunks(pages, chunk_size=800, overlap=100):

    chunks = []

    for page in pages:

        text = page["text"]

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk = text[start:end]

            if chunk.strip():

                chunks.append({
                    "text": chunk.strip(),
                    "page": page["page"]
                })

            start += chunk_size - overlap

    return chunks


# ==================================================
# CREATE FAISS INDEX
# ==================================================

def build_index(chunks):

    texts = [chunk["text"] for chunk in chunks]

    embeddings = embedding_model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embeddings = embeddings.astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    return index


# ==================================================
# RETRIEVE EVIDENCE
# ==================================================

def retrieve(question, index, chunks, top_k=5):

    query_embedding = embedding_model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    query_embedding = query_embedding.astype("float32")

    scores, indices = index.search(
        query_embedding,
        top_k
    )

    results = []

    for score, index_number in zip(
        scores[0],
        indices[0]
    ):

        if index_number == -1:
            continue

        results.append({
            "score": float(score),
            "page": chunks[index_number]["page"],
            "text": chunks[index_number]["text"]
        })

    return results


# ==================================================
# GENERATE ANSWER USING LOCAL LLM
# ==================================================

def generate_answer(question, evidence):

    evidence_text = ""

    for number, item in enumerate(evidence, start=1):

        evidence_text += (
            f"\n\nEvidence {number} "
            f"(Page {item['page']}):\n"
            f"{item['text']}"
        )

    prompt = f"""
You are a document-grounded question answering system.

Answer the user's question using ONLY the evidence provided below.

If the evidence does not contain enough information to answer,
say:

"I don't have enough evidence to answer this reliably."

Do not invent facts.

User question:
{question}

Retrieved evidence:
{evidence_text}

Give a concise answer and mention the relevant page numbers.
"""

    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


# ==================================================
# MAIN
# ==================================================

print("\nReading PDF...")

pages = extract_text(PDF_PATH)

print(f"Pages extracted: {len(pages)}")


print("\nCreating chunks...")

chunks = create_chunks(pages)

print(f"Chunks created: {len(chunks)}")


print("\nBuilding FAISS index...")

index = build_index(chunks)

print("FAISS index ready!")


# ==================================================
# QUESTION LOOP
# ==================================================

while True:

    print("\n" + "=" * 70)

    question = input(
        "Ask a question about the Oxford handbook "
        "(or type 'exit'): "
    )

    if question.lower() == "exit":

        break


    # Retrieve evidence

    evidence = retrieve(
        question,
        index,
        chunks,
        top_k=5
    )


    # Show evidence

    print("\nRETRIEVED EVIDENCE")

    print("-" * 70)

    for number, item in enumerate(
        evidence,
        start=1
    ):

        print(
            f"\nEvidence {number} | "
            f"Page {item['page']} | "
            f"Similarity {item['score']:.3f}"
        )

        print(
            item["text"][:500]
        )


    # Generate answer

    print("\n" + "=" * 70)

    print("GENERATING ANSWER...")

    answer = generate_answer(
        question,
        evidence
    )

    print("\nANSWER")

    print("-" * 70)

    print(answer)