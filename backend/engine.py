from pathlib import Path
import hashlib
import json

from backend import main

import ollama
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss

try:
    from .verification.verifier import (
        decompose_claims,
        verify_claim
    )
    from .calibration.confidence import (
        calculate_confidence
    )
except ImportError:
    from verification.verifier import (
        decompose_claims,
        verify_claim
    )
    from calibration.confidence import (
        calculate_confidence
    )


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

PDF_PATH = BASE_DIR / "data" / "oxford_student_handbook.pdf"

LLM_MODEL = "llama3.2:3b"

TOP_K = 5

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


# ============================================================
# CACHE CONFIGURATION
# ============================================================

CACHE_DIR = BASE_DIR / "data" / ".ecrag_cache"

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CACHE_INDEX = CACHE_DIR / "index.faiss"
CACHE_CHUNKS = CACHE_DIR / "chunks.json"
CACHE_META = CACHE_DIR / "metadata.json"


# ============================================================
# START APPLICATION
# ============================================================

print("\n" + "=" * 70)
print("              EVIDENCE-CALIBRATED RAG")
print("=" * 70)


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

embedding_model = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        print("\nLoading embedding model...")
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("Embedding model loaded.")
    return embedding_model


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_text(pdf_path):

    reader = PdfReader(str(pdf_path))

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        text = page.extract_text()

        if text:

            pages.append({
                "page": page_number,
                "text": text
            })

    return pages


# ============================================================
# CREATE TEXT CHUNKS
# ============================================================

def create_chunks(
    pages,
    chunk_size=800,
    overlap=100
):

    chunks = []

    for page in pages:

        text = page["text"]

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end]

            if chunk_text.strip():

                chunks.append({
                    "text": chunk_text.strip(),
                    "page": page["page"]
                })

            start += chunk_size - overlap

    return chunks


# ============================================================
# CREATE PDF HASH
# ============================================================

def get_file_hash(pdf_path):

    sha256 = hashlib.sha256()

    with open(
        pdf_path,
        "rb"
    ) as file:

        while True:

            data = file.read(1024 * 1024)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


# ============================================================
# CHECK CACHE
# ============================================================

def cache_is_valid(pdf_hash):

    if not (
        CACHE_INDEX.exists()
        and CACHE_CHUNKS.exists()
        and CACHE_META.exists()
    ):

        return False

    try:

        with open(
            CACHE_META,
            "r",
            encoding="utf-8"
        ) as file:

            metadata = json.load(file)

        return (
            metadata.get("pdf_hash")
            == pdf_hash
        )

    except Exception:

        return False


# ============================================================
# BUILD FAISS INDEX
# ============================================================

def build_index(chunks):

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = get_embedding_model().encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    embeddings = embeddings.astype(
        "float32"
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(embeddings)

    return index


# ============================================================
# SAVE CACHE
# ============================================================

def save_cache(
    index,
    chunks,
    pdf_hash
):

    print("\nSaving FAISS cache...")

    faiss.write_index(
        index,
        str(CACHE_INDEX)
    )


    with open(
        CACHE_CHUNKS,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            chunks,
            file,
            ensure_ascii=False,
            indent=2
        )


    metadata = {

        "pdf_hash": pdf_hash,

        "embedding_model": (
            EMBEDDING_MODEL_NAME
        ),

        "chunk_count": len(chunks)

    }


    with open(
        CACHE_META,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2
        )


    print("FAISS cache saved.")


# ============================================================
# LOAD CACHE
# ============================================================

def load_cache():

    print("\nLoading existing FAISS cache...")

    index = faiss.read_index(
        str(CACHE_INDEX)
    )


    with open(
        CACHE_CHUNKS,
        "r",
        encoding="utf-8"
    ) as file:

        chunks = json.load(file)


    print(
        f"Cached index loaded: "
        f"{len(chunks)} chunks"
    )

    return index, chunks


# ============================================================
# LOAD OR BUILD INDEX
# ============================================================

def load_or_build_index():

    print("\nChecking document cache...")

    pdf_hash = get_file_hash(
        PDF_PATH
    )


    # --------------------------------------------------------
    # USE EXISTING CACHE
    # --------------------------------------------------------

    if cache_is_valid(pdf_hash):

        print(
            "Existing document cache found."
        )

        return load_cache()


    # --------------------------------------------------------
    # CACHE DOES NOT EXIST / PDF CHANGED
    # --------------------------------------------------------

    print(
        "No valid cache found."
    )

    print(
        "Building index for this document..."
    )


    print("\nReading PDF...")

    pages = extract_text(
        PDF_PATH
    )

    print(
        f"Pages extracted: {len(pages)}"
    )


    print("\nCreating chunks...")

    chunks = create_chunks(
        pages
    )

    print(
        f"Chunks created: {len(chunks)}"
    )


    print("\nBuilding FAISS index...")

    index = build_index(
        chunks
    )

    print("FAISS index ready!")


    save_cache(
        index,
        chunks,
        pdf_hash
    )


    return index, chunks


# ============================================================
# RETRIEVE EVIDENCE
# ============================================================

def retrieve(
    question,
    index,
    chunks,
    top_k=TOP_K
):

    query_embedding = get_embedding_model().encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    query_embedding = query_embedding.astype(
        "float32"
    )


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


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_answer(
    question,
    evidence
):

    evidence_text = ""


    for number, item in enumerate(
        evidence,
        start=1
    ):

        evidence_text += (

            f"\n\nEvidence {number} "
            f"(Page {item['page']}):\n"
            f"{item['text']}"

        )


    prompt = f"""
You are an evidence-grounded question answering system.

Answer the user's question using ONLY the retrieved evidence.

IMPORTANT RULES:

1. Use the evidence provided below.
2. Do not invent facts.
3. If the evidence directly supports the answer, answer the question.
4. Do not refuse simply because the evidence is not word-for-word
   identical to the question.
5. You may combine information from multiple evidence passages.
6. If the evidence genuinely does not provide enough information,
   say exactly:

"I don't have enough evidence to answer this reliably."

7. When answering, mention the relevant page numbers.
8. Give a concise but useful answer.
9. Clearly distinguish between what the evidence explicitly states
   and what can reasonably be inferred.

USER QUESTION:

{question}

RETRIEVED EVIDENCE:

{evidence_text}
"""


    response = ollama.chat(

        model=LLM_MODEL,

        messages=[

            {
                "role": "user",
                "content": prompt
            }

        ]

    )


    return response["message"]["content"]




# ============================================================
# IN-PROCESS PIPELINE
# ============================================================

def run_pipeline(question):
    """Run the original ECRAG PDF pipeline without starting a new process."""
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    index, chunks = load_or_build_index()
    evidence = retrieve(question, index, chunks)
    answer = generate_answer(question, evidence)

    abstention_phrases = [
        "I don't have enough evidence",
        "I do not have enough evidence",
        "I lack sufficient information",
        "I don't have sufficient information",
        "I cannot answer this reliably",
        "I can't answer this reliably",
        "insufficient information",
        "insufficient evidence",
    ]

    if any(p.lower() in answer.lower() for p in abstention_phrases):
        return f"""
======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================

ANSWER
----------------------------------------------------------------------
{answer}

VERIFICATION SUMMARY
----------------------------------------------------------------------
Supported: 0
Contradicted: 0
Uncertain: 0

FINAL DECISION: ABSTAIN
CONFIDENCE: 0.000
======================================================================
"""

    claims = decompose_claims(answer)
    verification_results = [None] * len(claims)

    # Independent claim checks can run concurrently.
    if claims:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        workers = min(4, len(claims))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(verify_claim, claim, evidence): i for i, claim in enumerate(claims)}
            for future in as_completed(futures):
                i = futures[future]
                result = future.result()
                verification_results[i] = {
                    "claim": claims[i],
                    "verdict": result.get("verdict", "UNCERTAIN"),
                    "reason": result.get("reason", "")
                }

    supported = sum(r["verdict"] == "SUPPORTED" for r in verification_results)
    contradicted = sum(r["verdict"] == "CONTRADICTED" for r in verification_results)
    uncertain = sum(r["verdict"] == "UNCERTAIN" for r in verification_results)
    confidence_result = calculate_confidence(evidence, verification_results)
    confidence = float(confidence_result.get("confidence", 0.0))
    decision = "ANSWER" if confidence >= 0.80 else ("WARN" if confidence >= 0.50 else "ABSTAIN")

    evidence_text = "\n\n".join(
        f"Evidence {i} (Page {x['page']}, Similarity {x['score']:.3f}):\n{x['text']}"
        for i, x in enumerate(evidence, 1)
    )
    claims_text = "\n".join(f"{i}. {c}" for i, c in enumerate(claims, 1)) or "No claims extracted."
    verification_text = "\n\n".join(
        f"CLAIM {i}:\n{r['claim']}\nVERDICT: {r['verdict']}\nREASON: {r['reason']}"
        for i, r in enumerate(verification_results, 1)
    ) or "No claim verification was required."

    return f"""
======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================

RETRIEVED EVIDENCE
----------------------------------------------------------------------
{evidence_text}

CLAIMS
----------------------------------------------------------------------
{claims_text}

ANSWER
----------------------------------------------------------------------
{answer}

CLAIM VERIFICATION
----------------------------------------------------------------------
{verification_text}

VERIFICATION SUMMARY
----------------------------------------------------------------------
Supported: {supported}
Contradicted: {contradicted}
Uncertain: {uncertain}

EVIDENCE CONFIDENCE
----------------------------------------------------------------------
Final confidence: {confidence:.3f}
Retrieval relevance: {confidence_result.get('retrieval_relevance', 0):.3f}
Evidence coverage: {confidence_result.get('evidence_coverage', 0):.3f}
Claim support: {confidence_result.get('claim_support', 0):.3f}
Contradiction: {confidence_result.get('contradiction', 0):.3f}
Cross-document agreement: {confidence_result.get('cross_document_agreement', 0):.3f}
Source reliability: {confidence_result.get('source_reliability', 0):.3f}

FINAL DECISION: {decision}
CONFIDENCE: {confidence:.3f}
======================================================================
"""


if __name__ == '__main__':
    print('ECRAG optimized backend loaded.')


# ============================================================
# PERSISTENT RAG ENGINE COMPATIBILITY WRAPPER
# ============================================================
class RAGEngine:
    """Persistent in-process facade used by the Streamlit application.

    The underlying FAISS/embedding cache is already handled by backend.main.
    Keeping this facade lightweight preserves the existing app architecture
    while avoiding a subprocess for every PDF question.
    """
    def __init__(self):
        self.loaded = False

    def ensure_loaded(self):
        # backend.main lazily loads/reuses its persistent FAISS cache.
        if not self.loaded:
            self.loaded = True

    def run_pipeline(self, question, progress_callback=None):
        self.ensure_loaded()
        return main.run_pipeline(question, progress_callback=progress_callback)
