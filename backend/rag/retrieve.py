from pathlib import Path

import faiss
import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# 1. FIND THE PDF
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

PDF_PATH = BASE_DIR / "data" / "oxford_student_handbook.pdf"


# --------------------------------------------------
# 2. EXTRACT TEXT FROM PDF
# --------------------------------------------------

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


# --------------------------------------------------
# 3. SPLIT TEXT INTO CHUNKS
# --------------------------------------------------

def create_chunks(pages, chunk_size=800, overlap=100):

    chunks = []

    for page in pages:

        text = page["text"]
        page_number = page["page"]

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text.strip(),
                    "page": page_number
                })

            start += chunk_size - overlap

    return chunks


# --------------------------------------------------
# 4. CREATE EMBEDDINGS
# --------------------------------------------------

print("\nLoading embedding model...")

model = SentenceTransformer("all-MiniLM-L6-v2")

print("Embedding model loaded.")


# --------------------------------------------------
# 5. BUILD FAISS INDEX
# --------------------------------------------------

def build_index(chunks):

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embeddings = embeddings.astype("float32")

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    return index


# --------------------------------------------------
# 6. SEARCH
# --------------------------------------------------

def search(query, index, chunks, top_k=5):

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    query_embedding = query_embedding.astype("float32")

    scores, indices = index.search(query_embedding, top_k)

    results = []

    for score, index_number in zip(scores[0], indices[0]):

        if index_number == -1:
            continue

        results.append({
            "score": float(score),
            "page": chunks[index_number]["page"],
            "text": chunks[index_number]["text"]
        })

    return results


# --------------------------------------------------
# 7. MAIN PROGRAM
# --------------------------------------------------

print("\nReading PDF...")

pages = extract_text(PDF_PATH)

print(f"Pages extracted: {len(pages)}")


print("\nCreating chunks...")

chunks = create_chunks(pages)

print(f"Chunks created: {len(chunks)}")


print("\nBuilding FAISS index...")

index = build_index(chunks)

print("FAISS index ready!")


# --------------------------------------------------
# 8. ASK QUESTIONS
# --------------------------------------------------

while True:

    print("\n" + "=" * 60)

    question = input("Ask a question (or type 'exit'): ")

    if question.lower() == "exit":
        break

    results = search(
        question,
        index,
        chunks,
        top_k=5
    )

    print("\nTOP RELEVANT EVIDENCE:\n")

    for number, result in enumerate(results, start=1):

        print(f"--- Result {number} ---")

        print(f"Page: {result['page']}")

        print(f"Similarity: {result['score']:.3f}")

        print(f"\n{result['text'][:700]}")

        print()