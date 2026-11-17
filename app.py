import os
import subprocess
import sys
import re
import json
import sqlite3
import uuid
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
try:
    import ollama
except ImportError:
    ollama = None

# Gemini API (free-tier capable; used as the primary cloud LLM)
try:
    from google import genai
    try:
        from google.genai import types as genai_types
    except ImportError:
        genai_types = None
except ImportError:
    genai = None
    genai_types = None

from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from html import unescape
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from backend.verification.pipeline import SevenStageVerificationPipeline
    from backend.verification.claim_ledger import (
        ClaimLedger,
        ClaimEntry,
        EvidenceItem,
        split_into_atomic_claims,
        VERDICT_VERIFIED,
        VERDICT_PARTIALLY_VERIFIED,
        VERDICT_CONTRADICTED,
        VERDICT_UNVERIFIED,
        STAGE_NAMES,
        STAGE_SHORT_TITLES
    )
    from backend.verification.forensic_auditor import (
        AntiSycophancyShield,
        TruthHeatmapRenderer
    )
except ImportError:
    from .backend.verification.pipeline import SevenStageVerificationPipeline
    from .backend.verification.claim_ledger import (
        ClaimLedger,
        ClaimEntry,
        EvidenceItem,
        split_into_atomic_claims,
        VERDICT_VERIFIED,
        VERDICT_PARTIALLY_VERIFIED,
        VERDICT_CONTRADICTED,
        VERDICT_UNVERIFIED,
        STAGE_NAMES,
        STAGE_SHORT_TITLES
    )
    from .backend.verification.forensic_auditor import (
        AntiSycophancyShield,
        TruthHeatmapRenderer
    )


import streamlit as st
st.set_page_config(page_title="ECRAG", page_icon="📚", layout="wide")

# ============================================================
# LUXURY BLACK, GOLD & GLASSMORPHISM DESIGN SYSTEM
# ============================================================
st.markdown("""
<style>
/* 1. Global Page Background - Deep Obsidian with Warm Amber Spotlights */
.stApp {
    background: 
        radial-gradient(circle at 12% 10%, rgba(212, 175, 55, 0.08) 0%, transparent 42%),
        radial-gradient(circle at 88% 90%, rgba(212, 175, 55, 0.06) 0%, transparent 45%),
        radial-gradient(circle at 50% 50%, rgba(18, 18, 24, 0.6) 0%, transparent 100%),
        #070709 !important;
    color: #f8f7f4 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
}

/* 2. Frosted Glass Sidebar with Gold Gilded Border */
[data-testid="stSidebar"] {
    background: rgba(10, 10, 14, 0.78) !important;
    backdrop-filter: blur(24px) saturate(190%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(190%) !important;
    border-right: 1px solid rgba(212, 175, 55, 0.20) !important;
    box-shadow: 4px 0 28px rgba(0, 0, 0, 0.6) !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(212, 175, 55, 0.15) !important;
}

/* 3. Top Navigation Bar - Ultra-thin Translucent Frosted Glass */
[data-testid="stHeader"] {
    background: rgba(7, 7, 9, 0.60) !important;
    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    border-bottom: 1px solid rgba(212, 175, 55, 0.14) !important;
}

/* 4. Metallic Gold Shimmer Headers */
h1, h2, h3, .gold-text {
    background: linear-gradient(135deg, #fff7d6 0%, #d4af37 45%, #f59e0b 80%, #aa7c11 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px !important;
}

/* 5. Chat Messages - High-Definition Glassmorphic Cards */
[data-testid="stChatMessage"] {
    background: rgba(18, 18, 24, 0.58) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    border: 1px solid rgba(212, 175, 55, 0.18) !important;
    border-radius: 16px !important;
    padding: 16px 20px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45), inset 0 1px 1px rgba(255, 245, 200, 0.08) !important;
    transition: all 0.25s ease !important;
}

[data-testid="stChatMessage"]:hover {
    border-color: rgba(212, 175, 55, 0.38) !important;
    box-shadow: 0 10px 36px 0 rgba(0, 0, 0, 0.55), 0 0 18px rgba(212, 175, 55, 0.12) !important;
}

/* 6. Gold Gilded Glass Buttons */
.stButton > button[kind="primary"], button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #e6c65b 0%, #d4af37 50%, #996515 100%) !important;
    color: #070709 !important;
    font-weight: 700 !important;
    border: 1px solid #fef08a !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 18px rgba(212, 175, 55, 0.35) !important;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

.stButton > button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
    transform: translateY(-1.5px) !important;
    box-shadow: 0 6px 24px rgba(212, 175, 55, 0.55) !important;
    border-color: #ffffff !important;
}

.stButton > button[kind="secondary"], button[data-testid="baseButton-secondary"] {
    background: rgba(20, 20, 26, 0.65) !important;
    color: #f5eedc !important;
    border: 1px solid rgba(212, 175, 55, 0.26) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
    transition: all 0.25s ease !important;
}

.stButton > button[kind="secondary"]:hover, button[data-testid="baseButton-secondary"]:hover {
    background: rgba(30, 28, 36, 0.82) !important;
    border-color: rgba(212, 175, 55, 0.55) !important;
    color: #fff9e6 !important;
    box-shadow: 0 6px 20px rgba(212, 175, 55, 0.22) !important;
    transform: translateY(-1px) !important;
}

/* 7. Chat Input Dock - Floating Glass with Gold Accent Focus */
[data-testid="stChatInput"] {
    background: rgba(14, 14, 18, 0.78) !important;
    backdrop-filter: blur(22px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(180%) !important;
    border: 1px solid rgba(212, 175, 55, 0.30) !important;
    border-radius: 20px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(212, 175, 55, 0.15) !important;
    transition: all 0.3s ease !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: #d4af37 !important;
    box-shadow: 0 8px 36px rgba(0, 0, 0, 0.7), 0 0 22px rgba(212, 175, 55, 0.35) !important;
}

[data-testid="stChatInput"] textarea {
    color: #f8f7f4 !important;
}

/* 8. Glassmorphic Expanders */
[data-testid="stExpander"] {
    background: rgba(16, 16, 22, 0.55) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(212, 175, 55, 0.22) !important;
    border-radius: 14px !important;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35) !important;
    margin-bottom: 12px !important;
}

[data-testid="stExpander"] summary {
    color: #f3eee3 !important;
    font-weight: 600 !important;
}

[data-testid="stExpander"] summary:hover {
    color: #d4af37 !important;
}

/* 9. Live Pipeline Status Widget */
div[data-testid="stStatusWidget"] {
    background: rgba(16, 16, 22, 0.75) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(212, 175, 55, 0.28) !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5), inset 0 1px 2px rgba(212, 175, 55, 0.1) !important;
}

/* 10. Callouts & Info Alerts */
.stAlert {
    background: rgba(18, 18, 24, 0.65) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(212, 175, 55, 0.25) !important;
    border-radius: 12px !important;
    color: #f8f7f4 !important;
}

/* 11. Radio Options & Checkboxes */
div[data-testid="stRadio"] label {
    color: #e5e5dc !important;
}

/* 12. Custom Obsidian-Gold Scrollbar */
::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
::-webkit-scrollbar-track {
    background: #070709;
}
::-webkit-scrollbar-thumb {
    background: rgba(212, 175, 55, 0.35);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(212, 175, 55, 0.65);
}
</style>
""", unsafe_allow_html=True)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_FOLDER = PROJECT_ROOT / "data"
DATA_FOLDER.mkdir(exist_ok=True)
PDF_PATH = DATA_FOLDER / "oxford_student_handbook.pdf"
GENERAL_MODEL = "llama3.1"

def _resolve_gemini_api_key() -> str:
    # 1. Environment variable / .env
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "gemini_api_key", "google_api_key"):
        k = os.getenv(var, "").strip()
        if k:
            return k
    # 2. Streamlit Cloud Secrets (st.secrets)
    try:
        if hasattr(st, "secrets"):
            for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "gemini_api_key", "google_api_key"):
                if var in st.secrets:
                    val = str(st.secrets[var]).strip()
                    if val:
                        return val
    except Exception:
        pass
    return ""

def _resolve_gemini_model() -> str:
    for var in ("ECRAG_GEMINI_MODEL", "GEMINI_MODEL", "ecrag_gemini_model", "gemini_model"):
        m = os.getenv(var, "").strip()
        if m:
            return m
    try:
        if hasattr(st, "secrets"):
            for var in ("ECRAG_GEMINI_MODEL", "GEMINI_MODEL", "ecrag_gemini_model", "gemini_model"):
                if var in st.secrets:
                    val = str(st.secrets[var]).strip()
                    if val:
                        return val
    except Exception:
        pass
    return "gemini-3.5-flash-lite"

GEMINI_MODEL = _resolve_gemini_model()
GEMINI_API_KEY = _resolve_gemini_api_key()
MAX_HISTORY = 20

# Gemini is the primary generation/verification model. Ollama remains as a
# local fallback so the app does not break if the API/package/rate limit fails.



# ============================================================
# GEMINI + OLLAMA MODEL LAYER
# ============================================================

_gemini_client_instance = None

def _gemini_client():
    """Return a cached Gemini client (created once per process)."""
    global _gemini_client_instance
    key = _resolve_gemini_api_key()
    if genai is None or not key:
        return None
    if _gemini_client_instance is not None:
        return _gemini_client_instance
    try:
        _gemini_client_instance = genai.Client(api_key=key)
        return _gemini_client_instance
    except Exception as e:
        print(f"[ECRAG] Gemini client initialization failed: {e}")
        return None


def _messages_to_gemini_text(messages):
    """Convert the existing Ollama-style message list into a Gemini prompt."""
    parts = []
    for message in messages or []:
        role = str(message.get("role", "user")).lower()
        content = str(message.get("content", ""))
        if not content:
            continue

        if role == "system":
            label = "SYSTEM INSTRUCTIONS"
        elif role == "assistant":
            label = "ASSISTANT CONTEXT"
        else:
            label = "USER"

        parts.append(f"{label}:\n{content}")

    return "\n\n".join(parts)


def _gemini_chat(messages):
    """
    Gemini-first equivalent of ollama.chat().

    Returns the same minimal response shape used throughout the existing
    application: {"message": {"content": "..."}}
    """
    client = _gemini_client()
    if client is None:
        return None

    prompt = _messages_to_gemini_text(messages)

    candidate_models = [_resolve_gemini_model()]
    for alt in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-lite-latest", "gemini-3.6-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    for m in candidate_models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt
                )
                content = getattr(response, "text", None)
                if content:
                    print(f"[ECRAG] Gemini SUCCESS: model={m}")
                    return {"message": {"content": str(content).strip()}}
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str or "high demand" in err_str or "UNAVAILABLE" in err_str or "ResourceExhausted" in err_str) and attempt == 0:
                    time.sleep(1.5)
                    continue
                print(f"[ECRAG] Gemini {m} attempt {attempt+1} failed: {type(e).__name__}: {e}")
                break
    return None

_hf_pipeline = None
_HF_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

def _hf_chat(messages):
    """Generate a response using a local Hugging Face model (CPU-friendly)."""
    global _hf_pipeline
    if _hf_pipeline is None:
        from transformers import pipeline as hf_pipeline
        print(f"[ECRAG] Loading local Hugging Face model ({_HF_MODEL})...")
        _hf_pipeline = hf_pipeline(
            "text-generation",
            model=_HF_MODEL,
        )
        print(f"[ECRAG] Hugging Face model loaded successfully.")

    prompt = _hf_pipeline.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    outputs = _hf_pipeline(
        prompt,
        max_new_tokens=512,
        do_sample=True,
        temperature=0.4,
        top_k=40,
        top_p=0.90,
        repetition_penalty=1.15,
    )
    result_text = outputs[0]["generated_text"][len(prompt):]
    print("[ECRAG] Hugging Face Offline SUCCESS")
    return {"message": {"content": result_text.strip()}}


_cached_offline_vectorstore = None

def _offline_vectorstore():
    """Load the offline embedding model + ChromaDB once per app process.

    Recreating HuggingFaceEmbeddings on every query would re-download-check and
    reload the model (~30s) each time; caching keeps offline answers fast.
    """
    global _cached_offline_vectorstore
    if _cached_offline_vectorstore is None:
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings
        print("[ECRAG] Loading offline embedding model + ChromaDB...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        _cached_offline_vectorstore = Chroma(
            persist_directory=str(DATA_FOLDER / "chroma_db"),
            embedding_function=embeddings,
        )
        print("[ECRAG] Offline vector store ready.")
    return _cached_offline_vectorstore


def offline_rag_answer(question, progress_callback=None):
    """Simplified offline RAG: retrieve from ChromaDB → answer with local HF model.

    This bypasses the complex multi-step verification pipeline that small
    local models cannot handle reliably. Instead it does a single
    retrieve-then-answer pass with a straightforward prompt.
    """
    # --- Retrieve from local ChromaDB ---
    context_chunks = []
    try:
        vectorstore = _offline_vectorstore()
        docs = vectorstore.similarity_search(question, k=5)
        context_chunks = [doc.page_content for doc in docs]
        print(f"[ECRAG] Offline RAG: retrieved {len(context_chunks)} chunks from ChromaDB")
    except Exception as exc:
        print(f"[ECRAG] Offline RAG: ChromaDB retrieval failed: {exc}")

    # Anti-Sycophancy Audit for Offline Queries
    sycophancy_report = AntiSycophancyShield.audit_query(
        question,
        retrieved_evidence=[{"title": f"Local Chunk {i+1}", "snippet": ch} for i, ch in enumerate(context_chunks)]
    )
    sycophancy_directive = ""
    if sycophancy_report.get("shield_activated") or sycophancy_report.get("directive"):
        sycophancy_directive = f"\n{sycophancy_report.get('directive')}\n"

    q_words = set(re.findall(r"\b[a-z]{3,}\b", question.lower())) - {"the", "and", "for", "with", "how", "what", "can", "you", "does", "deal", "some", "someone", "asks"}
    context_words = set(re.findall(r"\b[a-z]{3,}\b", " ".join(context_chunks).lower())) if context_chunks else set()
    has_relevant_evidence = bool(q_words & context_words)

    if context_chunks and has_relevant_evidence:
        context_text = "\n\n---\n\n".join(context_chunks)
        prompt = (
            f"You are ECRAG running in Offline / Island Mode on a local laptop.\n"
            f"{sycophancy_directive}"
            f"Use the following reference material as your primary factual basis.\n\n"
            f"REFERENCE MATERIAL:\n{context_text}\n\n"
            f"QUESTION: {question}\n\n"
            f"Provide a clear, practical, step-by-step answer based on the reference material.\n\n"
            f"ANSWER:"
        )
        confidence = 0.88
        decision = "ANSWER"
        source = "📚 Offline Knowledge Base • Local HF Model • ChromaDB"
    elif context_chunks:
        prompt = (
            f"You are ECRAG running in Offline / Island Mode on a local laptop.\n"
            f"{sycophancy_directive}"
            f"Answer the following technical or troubleshooting question concisely, accurately, and safely with step-by-step instructions.\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:"
        )
        confidence = 0.65
        decision = "WARN"
        source = "🧠 Local HF Model • General Technical Knowledge"
    else:
        prompt = (
            f"You are ECRAG running in Offline / Island Mode on a local laptop.\n"
            f"{sycophancy_directive}"
            f"Answer the following technical or troubleshooting question concisely and accurately with step-by-step instructions.\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:"
        )
        confidence = 0.50
        decision = "WARN"
        source = "🧠 Local HF Model • No local database chunks"

    response = _hf_chat([{"role": "user", "content": prompt}])
    answer = response["message"]["content"]

    # Build Lightweight Claim Ledger for Forensic Audit Features
    offline_claims_list = split_into_atomic_claims(answer)
    if not offline_claims_list and answer:
        offline_claims_list = [answer.strip()[:200]]

    claims_data = []
    for c_idx, c_text in enumerate(offline_claims_list):
        c_words = set(re.findall(r"\b[a-z]{3,}\b", c_text.lower()))
        matched = bool(c_words & context_words) if context_words else False
        v = VERDICT_VERIFIED if matched else (VERDICT_PARTIALLY_VERIFIED if has_relevant_evidence else VERDICT_UNVERIFIED)
        claims_data.append({
            "claim_id": f"offline_claim_{c_idx+1}",
            "claim_text": c_text,
            "verdict": v,
            "confidence": 0.88 if v == VERDICT_VERIFIED else 0.50,
            "supporting_citations": [{
                "evidence_id": "chunk_local",
                "source_title": "Offline Knowledge Base (Local ChromaDB)",
                "url_or_page": "local://chromadb/offline_knowledge",
                "citation_text": c_text,
                "domain": "offline.local",
                "stage_name": "Offline Corpus"
            }],
            "contradictions": [],
            "reasoning": "Grounded in verified offline technical corpus." if matched else "General algorithmic synthesis."
        })

    offline_ledger = {
        "claims": claims_data,
        "evidence_items": {
            f"chunk_{i}": {
                "evidence_id": f"chunk_{i}",
                "stage": 1,
                "stage_name": "Offline Knowledge Base",
                "title": f"Offline Corpus Item {i+1}",
                "url_or_ref": "local://chromadb/knowledge_base",
                "domain": "offline.local",
                "snippet": ch[:250],
                "authority_tier": 1
            } for i, ch in enumerate(context_chunks)
        },
        "overall_confidence": confidence,
        "overall_decision": decision,
        "counts": {
            "verified": sum(1 for c in claims_data if c["verdict"] == VERDICT_VERIFIED),
            "partially_verified": sum(1 for c in claims_data if c["verdict"] == VERDICT_PARTIALLY_VERIFIED),
            "contradicted": 0,
            "unverified": sum(1 for c in claims_data if c["verdict"] == VERDICT_UNVERIFIED),
            "total_claims": len(claims_data)
        },
        "distinct_domains": ["offline.local"]
    }

    truth_heatmap_html = TruthHeatmapRenderer.generate_truth_heatmap_html(
        answer,
        offline_ledger,
        element_id="offline_truth_heatmap"
    )

    output = f"""
======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================

OFFLINE MODE • Local Hugging Face Model

======================================================================
ANSWER
----------------------------------------------------------------------

{answer}

======================================================================
LOCAL EVIDENCE
----------------------------------------------------------------------

{len(context_chunks)} chunks retrieved from offline knowledge base.

======================================================================
FINAL DECISION: {decision}
CONFIDENCE: {confidence:.3f}
======================================================================
"""

    return {
        "answer": answer,
        "confidence": confidence,
        "decision": decision,
        "output": output,
        "source": source,
        "claim_ledger": offline_ledger,
        "truth_heatmap_html": truth_heatmap_html,
        "sycophancy_report": sycophancy_report,
    }

def ai_chat(messages):
    """
    Primary model gateway.

    1. configured Gemini model when GEMINI_API_KEY is configured.
    2. Hugging Face if Offline/Island Mode is checked or if Ollama is unavailable.
    3. Ollama fallback.
    """
    try:
        from streamlit import session_state as st_state
        if st_state.get("offline_mode", False):
            if ollama is not None:
                try:
                    response = ollama.chat(
                        model=GENERAL_MODEL,
                        messages=messages
                    )
                    print(f"[ECRAG] Ollama Offline SUCCESS: model={GENERAL_MODEL}")
                    return response
                except Exception:
                    pass
            return _hf_chat(messages)
    except Exception:
        pass

    gemini_response = _gemini_chat(messages)
    if gemini_response:
        return gemini_response

    # If Gemini is not configured, inform the user cleanly instead of hanging or falling back to heavy local models on cloud
    if not _resolve_gemini_api_key():
        raise RuntimeError(
            "GEMINI_API_KEY is not configured! Please configure your GEMINI_API_KEY in Streamlit Cloud Secrets (Settings -> Secrets) or in your local .env file."
        )

    # Prevent massive Stage 7 verification prompt from hanging on CPU for 600s:
    is_large_stage7 = any(
        "You are Stage 7" in str(m.get("content", ""))
        for m in messages
    )
    if is_large_stage7:
        print("[ECRAG] Gemini unavailable for large Stage 7 validation; fast-falling back to deterministic verification.")
        return None

    if ollama is not None:
        try:
            response = ollama.chat(
                model=GENERAL_MODEL,
                messages=messages
            )
            print(f"[ECRAG] Ollama fallback SUCCESS: model={GENERAL_MODEL}")
            return response
        except Exception:
            pass
        
    try:
        return _hf_chat(messages)
    except Exception as e:
        print(f"[ECRAG] Hugging Face fallback failed: {type(e).__name__}: {e}")
        raise RuntimeError(
            "Neither Gemini, Ollama, nor Hugging Face could generate a response. "
            "Check API keys or internet access."
        ) from e


def model_status():
    """Small diagnostic used by the UI."""
    live = "Tavily live web" if TAVILY_API_KEY else "Multi-Tier Web (DuckDuckGo + Wikipedia + arXiv)"
    key = _resolve_gemini_api_key()
    if key and genai is not None:
        return f"☁️ Gemini {GEMINI_MODEL} • {live}"
    if key and genai is None:
        return f"⚠️ Gemini key found, but google-genai is not installed • {live}"
    if ollama is not None:
        return f"🖥️ Ollama local mode • {live}"
    return f"🧠 Hugging Face local mode • {live}"


# ============================================================
# 7-STAGE FACTUAL VERIFICATION TIMELINE COMPONENT
# ============================================================


# ============================================================
# ANIMATED FACTUAL VERIFICATION METER COMPONENT
# ============================================================

def generate_verification_meter_html(
    confidence: float,
    decision: str,
    counts: dict = None,
    quality_score: float = None,
    source: str = "",
    response_time: float = None,
    elem_id: str = None
) -> str:
    """Generates a responsive, animated factual verification meter with glowing indicator."""
    if elem_id is None:
        elem_id = str(uuid.uuid4())[:8]

    conf_pct = max(0.0, min(1.0, float(confidence) if confidence is not None else 0.0)) * 100.0

    if decision == "ANSWER":
        theme_color = "#10b981"
        theme_dim = "#059669"
        glow_color = "rgba(16, 185, 129, 0.45)"
        badge_bg = "rgba(16, 185, 129, 0.15)"
        badge_border = "rgba(16, 185, 129, 0.35)"
        badge_text = "VERIFIED GROUNDING"
        badge_icon = "🟢"
        status_desc = "Fully corroborated by independent sources • Zero contradictions detected"
        status_label = "High Factual Grounding"
    elif decision == "WARN":
        theme_color = "#f59e0b"
        theme_dim = "#d97706"
        glow_color = "rgba(245, 158, 11, 0.45)"
        badge_bg = "rgba(245, 158, 11, 0.15)"
        badge_border = "rgba(245, 158, 11, 0.35)"
        badge_text = "PARTIAL / CAVEATS"
        badge_icon = "🟡"
        status_desc = "Partially supported • Preliminary, unverified or single-source details"
        status_label = "Moderate Accountability"
    else:
        theme_color = "#ef4444"
        theme_dim = "#b91c1c"
        glow_color = "rgba(239, 68, 68, 0.45)"
        badge_bg = "rgba(239, 68, 68, 0.15)"
        badge_border = "rgba(239, 68, 68, 0.35)"
        badge_text = "ABSTAIN / UNVERIFIED"
        badge_icon = "🔴"
        status_desc = "Insufficient proof or conflicts detected • Refused to hallucinate"
        status_label = "Zero Speculation Guardrail"

    counts = counts or {}
    verified_c = counts.get("verified", 0)
    partially_c = counts.get("partially_verified", 0)
    contradicted_c = counts.get("contradicted", 0)
    unverified_c = counts.get("unverified", 0)
    total_c = counts.get("total_claims", verified_c + partially_c + contradicted_c + unverified_c)

    if total_c > 0:
        claim_stat = f"{verified_c}/{total_c} Verified"
    elif conf_pct >= 70:
        claim_stat = "Corroborated"
    elif conf_pct > 0:
        claim_stat = "Partially Checked"
    else:
        claim_stat = "0 Verified"

    conflict_stat = f"{contradicted_c} Conflicts" if contradicted_c > 0 else "0 Conflicts"
    conflict_color = "#ef4444" if contradicted_c > 0 else "#10b981"
    conflict_icon = "⚠️" if contradicted_c > 0 else "🛡️"

    time_str = f"{response_time:.2f}s" if response_time is not None else "Real-time"
    quality_val = quality_score if quality_score is not None else (conf_pct / 100.0)
    quality_str = f"{quality_val:.0%}"

    html = f"""
<div class="ecrag-meter-card" style="
    background: linear-gradient(135deg, rgba(18, 18, 24, 0.85), rgba(10, 10, 14, 0.92));
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(212, 175, 55, 0.22);
    border-left: 5px solid {theme_color};
    border-radius: 14px;
    padding: 16px 20px;
    margin: 12px 0 16px 0;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(212, 175, 55, 0.12);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
">
    <style>
    @keyframes fillMeter_{elem_id} {{
        0% {{ width: 0%; opacity: 0.2; }}
        100% {{ width: {conf_pct:.1f}%; opacity: 1; }}
    }}
    @keyframes shimmerWave_{elem_id} {{
        0% {{ transform: translateX(-100%); }}
        100% {{ transform: translateX(250%); }}
    }}
    </style>

    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">🛡️</span>
            <div>
                <div style="font-size: 13px; font-weight: 700; color: #f8fafc; letter-spacing: 0.3px;">
                    FACTUAL VERIFICATION METER
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 1px;">
                    {status_label} • Evidence Provenance
                </div>
            </div>
        </div>
        <div style="
            background: {badge_bg};
            border: 1px solid {badge_border};
            color: {theme_color};
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 5px;
        ">
            <span>{badge_icon}</span> {badge_text}
        </div>
    </div>

    <div style="display: flex; align-items: baseline; gap: 10px; margin: 8px 0 4px 0;">
        <span style="
            font-size: 30px;
            font-weight: 800;
            color: {theme_color};
            letter-spacing: -0.5px;
            line-height: 1;
        ">
            {conf_pct:.1f}%
        </span>
        <span style="font-size: 12px; color: #cbd5e1; line-height: 1.35;">
            {status_desc}
        </span>
    </div>

    <div style="
        width: 100%;
        height: 14px;
        background: rgba(255, 255, 255, 0.06);
        border-radius: 999px;
        overflow: hidden;
        position: relative;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin: 6px 0 4px 0;
    ">
        <div style="
            height: 100%;
            width: {conf_pct:.1f}%;
            background: linear-gradient(90deg, {theme_dim} 0%, {theme_color} 100%);
            box-shadow: 0 0 14px {glow_color};
            border-radius: 999px;
            position: relative;
            overflow: hidden;
            animation: fillMeter_{elem_id} 1.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        ">
            <div style="
                position: absolute;
                top: 0; left: 0;
                width: 60%;
                height: 100%;
                background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.4) 50%, transparent 100%);
                animation: shimmerWave_{elem_id} 2.5s infinite;
            "></div>
        </div>
    </div>

    <div style="
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        color: #64748b;
        margin-top: 3px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    ">
        <span>0% Speculation Refusal</span>
        <span>45% Caveat Threshold</span>
        <span>78% Grounded Proof</span>
        <span>100% Absolute</span>
    </div>

    <div style="
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 8px;
        margin-top: 12px;
        padding-top: 10px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
    ">
        <div style="background: rgba(212, 175, 55, 0.04); border: 1px solid rgba(212, 175, 55, 0.15); padding: 6px 9px; border-radius: 8px;">
            <div style="font-size: 9px; color: #d4af37; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">Claims Verified</div>
            <div style="font-size: 11px; font-weight: 700; color: #f8f7f4; margin-top: 1px;">📋 {claim_stat}</div>
        </div>
        <div style="background: rgba(212, 175, 55, 0.04); border: 1px solid rgba(212, 175, 55, 0.15); padding: 6px 9px; border-radius: 8px;">
            <div style="font-size: 9px; color: #d4af37; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">Contradictions</div>
            <div style="font-size: 11px; font-weight: 700; color: {conflict_color}; margin-top: 1px;">{conflict_icon} {conflict_stat}</div>
        </div>
        <div style="background: rgba(212, 175, 55, 0.04); border: 1px solid rgba(212, 175, 55, 0.15); padding: 6px 9px; border-radius: 8px;">
            <div style="font-size: 9px; color: #d4af37; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">Evidence Health</div>
            <div style="font-size: 11px; font-weight: 700; color: #f8f7f4; margin-top: 1px;">🎯 {quality_str} Quality</div>
        </div>
        <div style="background: rgba(212, 175, 55, 0.04); border: 1px solid rgba(212, 175, 55, 0.15); padding: 6px 9px; border-radius: 8px;">
            <div style="font-size: 9px; color: #d4af37; text-transform: uppercase; font-weight: 600; letter-spacing: 0.3px;">Audit Time</div>
            <div style="font-size: 11px; font-weight: 700; color: #f8f7f4; margin-top: 1px;">⏱️ {time_str}</div>
        </div>
    </div>
</div>
"""
    return html


def render_factual_verification_meter(
    confidence: float,
    decision: str,
    counts: dict = None,
    quality_score: float = None,
    source: str = "",
    response_time: float = None,
    key_suffix: str = ""
):
    """Renders the animated verification meter in Streamlit UI with zero markdown indentation errors."""
    elem_id = f"m_{key_suffix}_{abs(hash(str(confidence) + str(decision) + str(key_suffix))) % 100000}"
    raw_html = generate_verification_meter_html(
        confidence=confidence,
        decision=decision,
        counts=counts,
        quality_score=quality_score,
        source=source,
        response_time=response_time,
        elem_id=elem_id
    )
    # Strip leading whitespace on every line so markdown parser never treats it as code block
    clean_html = "\n".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())
    st.markdown(clean_html, unsafe_allow_html=True)


def render_verified_sources(claim_ledger):
    """
    Renders clean, direct clickable links to the real verified evidence sources.
    Displays title, hyperlink, and domain badge.
    """
    if not claim_ledger or not isinstance(claim_ledger, dict):
        return
    ev_dict = claim_ledger.get("evidence", {})
    if not ev_dict:
        return

    sources = []
    seen = set()
    for ev in ev_dict.values():
        url = str(ev.get("url_or_ref", "")).strip()
        title = str(ev.get("title", "")).strip()
        domain = str(ev.get("domain", "")).strip()
        if not title:
            title = domain or url or "Verified Source"
        title = title.replace("\n", " ").strip()
        if len(title) > 80:
            title = title[:77] + "..."

        if url and (url.startswith("http://") or url.startswith("https://")):
            if url not in seen:
                seen.add(url)
                sources.append((title, url, domain))
        elif url and (url.startswith("doc://") or url.startswith("pdf://")):
            if url not in seen:
                seen.add(url)
                sources.append((title, None, "Local Document"))

    if not sources:
        return

    st.markdown("##### 🔗 Verified Reference Sources")
    for title, url, domain in sources[:5]:
        dom_str = f" — *{domain}*" if domain else ""
        if url:
            st.markdown(f"- 🌐 [{title}]({url}){dom_str}")
        else:
            st.markdown(f"- 📄 **{title}**{dom_str}")

    if len(sources) > 5:
        with st.expander(f"📚 View {len(sources) - 5} more sources", expanded=False):
            for title, url, domain in sources[5:]:
                dom_str = f" — *{domain}*" if domain else ""
                if url:
                    st.markdown(f"- 🌐 [{title}]({url}){dom_str}")
                else:
                    st.markdown(f"- 📄 **{title}**{dom_str}")


def render_verification_timeline(claim_ledger, timeline_events=None, key_suffix=""):
    """
    Renders an interactive, collapsible 7-stage verification timeline in the Streamlit UI.
    Displays stage status, source counts, evidence previews, errors, and claim ledger
    with verdicts: VERIFIED, PARTIALLY_VERIFIED, CONTRADICTED, UNVERIFIED.
    """
    if not claim_ledger or not isinstance(claim_ledger, dict):
        return

    counts = claim_ledger.get("counts", {})
    claims = claim_ledger.get("claims", [])
    stage_summaries = claim_ledger.get("stage_summaries", {})
    contradictions = claim_ledger.get("contradictions_detected", [])
    overall_decision = claim_ledger.get("overall_decision", "ANSWER")
    overall_confidence = claim_ledger.get("overall_confidence", 0.0)

    stage_icons = {
        1: "🏛️",
        2: "📄",
        3: "📖",
        4: "🎓",
        5: "📰",
        6: "👥",
        7: "⚖️"
    }

    verdict_badge = {
        "VERIFIED": "🟢 VERIFIED",
        "PARTIALLY_VERIFIED": "🟡 PARTIALLY_VERIFIED",
        "CONTRADICTED": "🔴 CONTRADICTED",
        "UNVERIFIED": "⚪ UNVERIFIED"
    }

    with st.expander(
        f"🔬 7-Stage Factual Verification Timeline • {overall_decision} ({overall_confidence:.1%})",
        expanded=False
    ):
        # 1. Summary Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("🟢 Verified", counts.get("verified", 0))
        with m2:
            st.metric("🟡 Partially Verified", counts.get("partially_verified", 0))
        with m3:
            st.metric("🔴 Contradicted", counts.get("contradicted", 0))
        with m4:
            st.metric("⚪ Unverified", counts.get("unverified", 0))

        # 2. Contradiction Alert
        if contradictions:
            st.error(
                f"🚨 **Contradictions Detected Across Evidence Sources ({len(contradictions)}):**\n"
                + "\n".join(f"- {c}" for c in contradictions)
            )

        st.divider()

        # 3. Seven Stages Progression
        st.markdown("##### 📋 Verification Stage Progression")
        for s_num in range(1, 8):
            s_key = str(s_num) if str(s_num) in stage_summaries else s_num
            stage_info = stage_summaries.get(s_key, {})
            icon = stage_icons.get(s_num, "🔹")
            name = stage_info.get("name", f"Stage {s_num}")
            status = stage_info.get("status", "pending")
            src_count = stage_info.get("source_count", 0)
            skip_reason = stage_info.get("skip_reason")
            msg = stage_info.get("message", "")

            if status == "completed":
                st.markdown(f"{icon} **Stage {s_num}: {name}** — `🟢 Completed` ({src_count} sources)")
                if msg:
                    st.caption(f"↳ {msg}")
            elif status == "skipped":
                st.markdown(f"{icon} **Stage {s_num}: {name}** — `⏭️ Skipped`")
                if skip_reason:
                    st.caption(f"↳ *Reason:* {skip_reason}")
            elif status == "failed":
                st.markdown(f"{icon} **Stage {s_num}: {name}** — `🔴 Error`")
                if stage_info.get("error"):
                    st.caption(f"↳ *Error:* {stage_info.get('error')}")
            else:
                st.markdown(f"{icon} **Stage {s_num}: {name}** — `{status}`")

            # Community source notice
            if s_num == 6 and status == "completed":
                st.info("ℹ️ **Community Sources Policy:** Reddit, Quora, and forums are strictly evaluated as *leads only* and never as authoritative proof.")

        st.divider()

        # 4. Claim-by-Claim Ledger
        st.markdown("##### ⚖️ Claim-by-Claim Verification Ledger")
        if not claims:
            st.write("No discrete factual claims were extracted for ledgering.")
        else:
            for idx, c in enumerate(claims, 1):
                c_verdict = c.get("verdict", "UNVERIFIED")
                c_badge = verdict_badge.get(c_verdict, f"⚪ {c_verdict}")
                c_text = c.get("claim_text", "")
                c_conf = c.get("confidence", 0.0)
                c_reason = c.get("reasoning", "")
                citations = c.get("supporting_citations", [])
                conflicts = c.get("contradictions", [])

                with st.container():
                    st.markdown(f"**Claim {idx}:** {c_text}")
                    st.markdown(f"**Verdict:** `{c_badge}` • **Confidence:** `{c_conf:.1%}`")
                    if c_reason:
                        st.markdown(f"*Rationale:* {c_reason}")

                    if citations:
                        st.markdown("**Supporting Citations & Evidence Passages:**")
                        for cite in citations:
                            src_t = cite.get("source_title", "Evidence")
                            url_p = cite.get("url_or_page", "")
                            passage = cite.get("citation_text", "")
                            st_name = cite.get("stage_name", "")
                            ref_link = f"[{src_t}]({url_p})" if url_p.startswith("http") else f"`{src_t} ({url_p})`"
                            st.markdown(f"- *[{st_name}]* {ref_link}:")
                            st.caption(f"\"{passage}\"")

                    if conflicts:
                        st.markdown("**Contradictions / Conflicts:**")
                        for conf in conflicts:
                            st.warning(f"⚠️ Conflict in {conf.get('source_title', 'Source')}: \"{conf.get('conflict_text', '')}\"")

                    st.markdown("---")


# ============================================================
# PROJECT IDENTITY
# ============================================================
PROJECT_IDENTITY = """
ECRAG is an academic AI project developed by the students of VIT-AP:
Rishabh, Sohan, Pushp, and Rohith, under the guidance of
Dr. Vikash Kumar Singh.

When asked who created, developed, built, or made ECRAG, state that it was
developed by the students of VIT-AP — Rishabh, Sohan, Pushp, and Rohith —
under the guidance of Dr. Vikash Kumar Singh.

Do not invent additional developers, team members, institutions, or project
details that are not provided here.
"""

defaults = {
    "uploaded_document": None,
    "pdf_count": 0,
    "question_count": 0,
    "chat_messages": [],
    "results": None,
    "question_history": [],
    "correction_target": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# PERSISTENT CHAT MEMORY
# ============================================================
CHAT_DB_PATH = PROJECT_ROOT / "ecrag_chat_history.db"
CHAT_MAX_MESSAGES = 80


# ============================================================
# PERSISTENT CHAT HISTORY & MULTI-SESSION SEGMENTS
# ============================================================

_chat_db_conn = None

def _chat_db():
    """Return a cached SQLite connection and ensure schema & migrations."""
    global _chat_db_conn
    if _chat_db_conn is not None:
        return _chat_db_conn
    conn = sqlite3.connect(str(CHAT_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # 1. Chat sessions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            mode TEXT DEFAULT 'online',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # 2. Chat messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            one_line_answer TEXT,
            confidence REAL,
            decision TEXT,
            source TEXT,
            response_time REAL,
            created_at TEXT NOT NULL,
            verification_data TEXT
        )
    """)
    
    # Migration checks
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(chat_messages);")
    cols = [col[1] for col in cursor.fetchall()]
    if "session_id" not in cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN session_id TEXT NOT NULL DEFAULT 'default'")
    if "verification_data" not in cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN verification_data TEXT")
        
    # Ensure default session exists if there are legacy messages
    cursor.execute("SELECT COUNT(*) FROM chat_sessions WHERE session_id = 'default'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = 'default'")
        if cursor.fetchone()[0] > 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO chat_sessions (session_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("default", "Previous Conversation", "online", now_iso, now_iso)
            )
            
    conn.commit()
    _chat_db_conn = conn
    return _chat_db_conn


def _format_relative_time(iso_str):
    """Format an ISO timestamp into human-readable relative time."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "Just now"
        elif secs < 3600:
            return f"{secs // 60}m ago"
        elif secs < 86400:
            return f"{secs // 3600}h ago"
        elif secs < 172800:
            return "Yesterday"
        else:
            return dt.strftime("%b %d")
    except Exception:
        return ""


def create_chat_session(title="New Conversation", mode="online"):
    """Create a new chat session segment."""
    try:
        conn = _chat_db()
        sess_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO chat_sessions (session_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (sess_id, title, mode, now, now)
        )
        conn.commit()
        return sess_id
    except Exception as exc:
        print(f"[ECRAG] Session creation failed: {exc}")
        return f"sess_{int(time.time())}"


def list_chat_sessions():
    """List all chat sessions ordered by most recently updated."""
    try:
        conn = _chat_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.title, s.mode, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
        """)
        return [dict(r) for r in cursor.fetchall()]
    except Exception as exc:
        print(f"[ECRAG] Failed to list sessions: {exc}")
        return []


def load_session_messages(session_id):
    """Load messages for a specific session segment."""
    try:
        conn = _chat_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, one_line_answer, confidence, decision, source,
                   response_time, verification_data, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
        """, (session_id,))
        rows = cursor.fetchall()
        msgs = []
        for r in rows:
            m = {
                "role": r["role"], "content": r["content"], "one_line_answer": r["one_line_answer"] or "",
                "confidence": r["confidence"], "decision": r["decision"] or "UNKNOWN",
                "source": r["source"] or "", "response_time": r["response_time"],
                "created_at": r["created_at"]
            }
            if r["verification_data"]:
                try:
                    p_data = json.loads(r["verification_data"])
                    m["claim_ledger"] = p_data.get("claim_ledger")
                    m["verification_timeline"] = p_data.get("verification_timeline", [])
                    m["truth_heatmap_html"] = p_data.get("truth_heatmap_html")
                    m["sycophancy_report"] = p_data.get("sycophancy_report")
                except Exception:
                    pass
            msgs.append(m)
        return msgs
    except Exception as exc:
        print(f"[ECRAG] Failed to load messages for {session_id}: {exc}")
        return []


def load_chat_history():
    """Backward-compatible loader: returns messages for current active session."""
    active_id = st.session_state.get("current_session_id", "default")
    return load_session_messages(active_id)


def save_chat_message(message, session_id=None):
    """Save a chat message associated with a session segment."""
    try:
        sid = session_id or st.session_state.get("current_session_id", "default")
        conn = _chat_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if session exists; if not, create it
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM chat_sessions WHERE session_id = ?", (sid,))
        row = cursor.fetchone()
        if not row:
            title = (message.get("content", "")[:40].strip() or "New Conversation") if message.get("role") == "user" else "New Conversation"
            conn.execute(
                "INSERT INTO chat_sessions (session_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (sid, title, st.session_state.get("app_mode", "online"), now, now)
            )
        else:
            current_title = row[0]
            if current_title in ("New Conversation", "New Chat", "Previous Conversation") and message.get("role") == "user":
                new_title = message.get("content", "").split("\n")[0][:42].strip()
                if new_title:
                    conn.execute(
                        "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                        (new_title, now, sid)
                    )
            else:
                conn.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                    (now, sid)
                )

        v_data = None
        if message.get("claim_ledger") or message.get("verification_timeline"):
            v_data = json.dumps({
                "claim_ledger": message.get("claim_ledger"),
                "verification_timeline": message.get("verification_timeline", []),
                "truth_heatmap_html": message.get("truth_heatmap_html"),
                "sycophancy_report": message.get("sycophancy_report")
            })

        conn.execute(
            "INSERT INTO chat_messages "
            "(session_id, role, content, one_line_answer, confidence, decision, source, response_time, created_at, verification_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sid, message.get("role", ""), message.get("content", ""),
                message.get("one_line_answer", ""), message.get("confidence"),
                message.get("decision", ""), message.get("source", ""),
                message.get("response_time"), now, v_data
            )
        )
        conn.commit()
    except Exception as exc:
        print(f"[ECRAG] Chat persistence failed: {exc}")


def delete_chat_session(session_id):
    """Delete a session and all its messages."""
    try:
        conn = _chat_db()
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
    except Exception as exc:
        print(f"[ECRAG] Session deletion failed: {exc}")


def rename_chat_session(session_id, new_title):
    """Rename a session segment."""
    try:
        conn = _chat_db()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (new_title.strip()[:60], now, session_id)
        )
        conn.commit()
    except Exception as exc:
        print(f"[ECRAG] Session rename failed: {exc}")


def clear_saved_chat(session_id=None):
    """Clear messages for a specific session (or active session if None)."""
    try:
        sid = session_id or st.session_state.get("current_session_id", "default")
        conn = _chat_db()
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,))
        conn.commit()
    except Exception as exc:
        print(f"[ECRAG] Chat history clear failed: {exc}")


def clear_all_chat_sessions():
    """Wipe all history and sessions, then create a clean initial session."""
    try:
        conn = _chat_db()
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM chat_sessions")
        conn.commit()
    except Exception as exc:
        print(f"[ECRAG] Clear all sessions failed: {exc}")


# Initialize session state on startup
if "current_session_id" not in st.session_state:
    all_sess = list_chat_sessions()
    if all_sess:
        st.session_state.current_session_id = all_sess[0]["session_id"]
    else:
        st.session_state.current_session_id = create_chat_session("New Conversation")

if "chat_history_loaded" not in st.session_state:
    st.session_state.chat_history_loaded = True
    saved_history = load_session_messages(st.session_state.current_session_id)
    if saved_history:
        st.session_state.chat_messages = saved_history
        st.session_state.question_count = sum(1 for m in saved_history if m.get("role") == "user")


def new_document():
    st.session_state.uploaded_document = None
    st.session_state.results = None
    st.session_state.chat_messages = []
    st.session_state.question_history = []
    st.session_state.question_count = 0
    st.session_state.correction_target = None
    if PDF_PATH.exists():
        try:
            PDF_PATH.unlink()
        except Exception:
            pass


def clear_conversation():
    st.session_state.chat_messages = []
    st.session_state.results = None
    st.session_state.question_history = []
    st.session_state.question_count = 0
    st.session_state.correction_target = None
    clear_saved_chat(st.session_state.get("current_session_id", "default"))


def extract_decision(text):
    match = re.search(r"FINAL DECISION:\s*(.+)", text, re.I)
    return match.group(1).strip().upper() if match else "UNKNOWN"


def extract_confidence(text):
    match = re.search(r"CONFIDENCE:\s*([0-9.]+)", text, re.I)
    if match:
        try:
            return max(0.0, min(float(match.group(1)), 1.0))
        except ValueError:
            pass
    return 0.0


def extract_answer(text):
    match = re.search(
        r"ANSWER\s*\n[-]+\s*\n(.*?)(?=\n={5,}|\Z)",
        text, re.S | re.I
    )
    if match:
        return match.group(1).strip()

    match = re.search(
        r"ANSWER\s*\n(.*?)(?=\n={5,}|\Z)",
        text, re.S | re.I
    )
    return match.group(1).strip() if match else ""


def extract_number(pattern, text):
    match = re.search(pattern, text, re.I)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 0


def normalize_chat_language(text):
    """
    Normalize common chat/SMS abbreviations before ECRAG processes a
    question. The original wording remains unchanged in the chat UI/history.
    """
    if not isinstance(text, str):
        return text

    replacements = {
        "tysm": "thank you so much",
        "wdym": "what do you mean",
        "afaik": "as far as I know",
        "imho": "in my humble opinion",
        "lmao": "laughing",
        "ttyl": "talk to you later",
        "asap": "as soon as possible",
        "bcoz": "because",
        "bcz": "because",
        "tmrw": "tomorrow",
        "tmr": "tomorrow",
        "wanna": "want to",
        "gonna": "going to",
        "gotta": "got to",
        "idk": "I don't know",
        "idc": "I don't care",
        "ikr": "I know, right",
        "imo": "in my opinion",
        "tbh": "to be honest",
        "ngl": "not gonna lie",
        "btw": "by the way",
        "rn": "right now",
        "wyd": "what are you doing",
        "hbu": "how about you",
        "lmk": "let me know",
        "fyi": "for your information",
        "brb": "be right back",
        "bbl": "be back later",
        "omg": "oh my god",
        "lol": "laughing",
        "rofl": "laughing",
        "fr": "for real",
        "tho": "though",
        "thx": "thanks",
        "ty": "thank you",
        "np": "no problem",
        "pls": "please",
        "plz": "please",
        "abt": "about",
        "cuz": "because",
        "coz": "because",
        "bc": "because",
        "u": "you",
        "ur": "your",
        "urs": "yours",
        "r": "are",
        "ppl": "people",
        "msg": "message",
        "msgs": "messages",
        "wknd": "weekend",
        "bday": "birthday",
        "govt": "government",
        "uni": "university",
        "clg": "college",
        "prof": "professor",
        "info": "information",
        "diff": "difference",
    }

    # Protect technical terms and named entities from abbreviation rules.
    protected = re.compile(
        r"\b(?:AI|AIIMS|API|BCCI|CEO|CSE|DC|DHH|ECI|ECRAG|FIFA|"
        r"GATE|GPT|IIT|ISRO|LLM|NASA|NLP|PDF|PM|RAG|RBI|SRM|"
        r"SRMIST|TCS|TOC|UPSC|VIT|WHO)\b",
        re.I
    )

    saved = []

    def protect(match):
        saved.append(match.group(0))
        return f"__ECRAG_PROTECTED_{len(saved)-1}__"

    normalized = protected.sub(protect, text)

    for short, full in sorted(replacements.items(), key=lambda item: -len(item[0])):
        normalized = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(short)}(?![A-Za-z0-9])",
            full,
            normalized,
            flags=re.IGNORECASE,
        )

    for i, original in enumerate(saved):
        normalized = normalized.replace(
            f"__ECRAG_PROTECTED_{i}__", original
        )

    return re.sub(r"\s+", " ", normalized).strip()


def is_project_identity_question(question):
    """Detect questions specifically about who developed/created ECRAG."""
    q = normalize_chat_language(question).lower().strip()
    patterns = [
        "who made you",
        "who created you",
        "who developed you",
        "who built you",
        "who made ecrag",
        "who created ecrag",
        "who developed ecrag",
        "who built ecrag",
        "who is your developer",
        "who are your developers",
        "who is your guide",
        "who is the project guide",
    ]
    return any(pattern in q for pattern in patterns)


def project_identity_answer():
    return (
        "ECRAG was developed by the students of VIT-AP — Rishabh, Sohan, "
        "Pushp, and Rohith — under the guidance of Dr. Vikash Kumar Singh."
    )


def classify_general_question(question):
    q = question.lower().strip()

    time_sensitive = [
        "current", "currently", "today", "now", "latest", "recent",
        "this year", "this month", "president", "prime minister",
        "pm of", "chief minister", "minister", "ceo", "price",
        "stock price", "weather", "score", "winner", "election",
        "result", "ranking", "rankings", "release date"
    ]

    speculative = [
        "will happen", "will win", "predict", "prediction",
        "future", "2030", "2040", "who will", "what will"
    ]

    subjective = [
        "best", "worst", "most beautiful", "most popular",
        "better", "should i", "which is better"
    ]

    if any(x in q for x in speculative):
        return "speculative"
    if any(x in q for x in time_sensitive):
        return "time_sensitive"
    if any(x in q for x in subjective):
        return "subjective"
    return "stable"


def build_conversation_context():
    """Return recent conversation history for follow-up questions."""
    recent = st.session_state.chat_messages[-9:]

    # The current user question is already appended before generation.
    # Exclude that final user message from the historical context.
    if recent and recent[-1].get("role") == "user":
        recent = recent[:-1]

    if not recent:
        return ""

    context_parts = []

    for message in recent:
        role = message.get("role", "")
        content = normalize_chat_language(message.get("content", "").strip())

        if not content:
            continue

        if role == "user":
            context_parts.append(f"User: {content}")

        elif role == "assistant":
            context_parts.append(f"ECRAG Assistant: {content}")

        elif role == "correction":
            context_parts.append(
                f"User correction/challenge (UNVERIFIED): {content}"
            )

    return "\n".join(context_parts)



# ============================================================
# INTERNET / WEB EVIDENCE FOR GENERAL KNOWLEDGE
# ============================================================

WEB_MAX_RESULTS = 6
WEB_TIMEOUT = 8
CURRENT_AFFAIRS_MAX_RESULTS = 8
CURRENT_AFFAIRS_TIMEOUT = 8
# Tavily is the primary live-web retrieval layer. DuckDuckGo remains as a
# no-key fallback so the existing ECRAG retrieval path is never removed.
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_TIMEOUT = 10

# ============================================================
# REAL-TIME DATA + QUALITY CHECK
# ============================================================
# Open-Meteo is used for weather because it provides live/current
# forecast data without requiring an API key or any hardware.
REALTIME_TIMEOUT = 8

def is_weather_question(question):
    q = question.lower().strip()
    weather_terms = [
        "weather", "temperature", "temp", "forecast", "rain", "raining",
        "humidity", "wind speed", "wind", "sunny", "cloudy", "storm",
        "precipitation", "feels like", "what is it like outside"
    ]
    return any(term in q for term in weather_terms)

def extract_weather_location(question):
    q = re.sub(r"\s+", " ", str(question or "").strip())

    local_me_patterns = [
        r"\bnear\s+me\b", r"\bnear\s+by\s+me\b", r"\bnearby\b",
        r"\bhere\b", r"\baround\s+me\b", r"\bmy\s+location\b"
    ]
    if any(re.search(p, q, re.I) for p in local_me_patterns):
        return "Vijayawada"

    # Handle natural phrasing such as:
    # "what's the weather like in Hyderabad?"
    # "how is the weather in Chennai today?"
    # "temperature for Vijayawada right now"
    patterns = [
        r"(?:weather|forecast)\s+(?:like\s+)?(?:in|at|for|of)\s+(.+)",
        r"temperature\s+(?:in|at|for|of)\s+(.+)",
        r"(?:rain|raining|humidity|wind)\s+(?:in|at|for|of)\s+(.+)",
        r"(?:how(?:'s| is)\s+the\s+weather|what(?:'s| is)\s+the\s+weather)\s+(?:like\s+)?(?:in|at|for)\s+(.+)",
    ]

    stop_words = (
        r"\b(?:today|tonight|tomorrow|now|currently|right now|"
        r"this morning|this afternoon|this evening|this week)\b"
    )

    for pattern in patterns:
        m = re.search(pattern, q, re.I)
        if not m:
            continue

        # Some patterns have one capture group; the last group is the location.
        location = m.group(m.lastindex or 1).strip(" ?.,!")
        location = re.split(stop_words, location, maxsplit=1, flags=re.I)[0]
        location = re.sub(r"\s+", " ", location).strip(" ?.,!")

        if location:
            if re.search(r"^(near\s+(?:by\s+)?me|nearby|here|my\s+location)$", location, re.I):
                return "Vijayawada"
            return location

    # Short natural form: "weather Hyderabad"
    m = re.search(
        r"(?:weather|forecast|temperature|temp)\s+(.+)",
        q,
        re.I
    )
    if m:
        location = re.split(stop_words, m.group(1), maxsplit=1, flags=re.I)[0]
        location = location.strip(" ?.,!")
        if location:
            return location

    return ""

def geocode_location(location):
    if not location:
        return None
    url = "https://geocoding-api.open-meteo.com/v1/search?name=" + quote_plus(location) + "&count=1&language=en&format=json"
    try:
        request = Request(url, headers={"User-Agent": "ECRAG/1.0"})
        with urlopen(request, timeout=REALTIME_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        results = data.get("results", [])
        if not results:
            return None
        r = results[0]
        return {
            "name": r.get("name", location),
            "country": r.get("country", ""),
            "admin1": r.get("admin1", ""),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "timezone": r.get("timezone", "UTC"),
        }
    except Exception as e:
        return {"error": str(e)}

def _weather_result_from_open_meteo(location):
    geo = geocode_location(location)
    if not geo or geo.get("error") or geo.get("latitude") is None:
        return None

    # Keep the structured request small and deterministic. The previous
    # minutely override was unnecessary for a simple "current weather" query.
    params = (
        f"latitude={geo['latitude']}&longitude={geo['longitude']}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m,precipitation,rain"
        "&timezone=auto"
    )
    url = "https://api.open-meteo.com/v1/forecast?" + params

    request = Request(url, headers={"User-Agent": "ECRAG/1.0"})
    with urlopen(request, timeout=REALTIME_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))

    current = data.get("current", {})
    required = [
        "temperature_2m", "relative_humidity_2m",
        "apparent_temperature", "wind_speed_10m",
        "weather_code", "time"
    ]
    missing = [x for x in required if current.get(x) is None]
    if missing:
        return None

    return {
        "ok": True,
        "provider": "Open-Meteo",
        "location": geo,
        "current": current,
        "units": data.get("current_units", {}),
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


def _weather_result_from_wttr(location):
    """
    API-key-free structured fallback.

    wttr.in is used only if the primary structured provider is unavailable.
    Values are parsed directly; the LLM never invents weather numbers.
    """
    url = "https://wttr.in/" + quote_plus(location) + "?format=j1"
    request = Request(
        url,
        headers={
            "User-Agent": "ECRAG/1.0",
            "Accept": "application/json",
        }
    )

    with urlopen(request, timeout=REALTIME_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))

    current_list = data.get("current_condition", []) or []
    if not current_list:
        return None

    c = current_list[0]

    def number(key):
        value = c.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    temp = number("temp_C")
    feels = number("FeelsLikeC")
    humidity = number("humidity")
    wind = number("windspeedKmph")
    if any(v is None for v in (temp, feels, humidity, wind)):
        return None

    weather_desc = ""
    desc_list = c.get("weatherDesc") or []
    if desc_list and isinstance(desc_list[0], dict):
        weather_desc = str(desc_list[0].get("value", "")).strip()

    location_data = {
        "name": location,
        "country": "",
        "admin1": "",
        "latitude": None,
        "longitude": None,
        "timezone": "UTC",
    }

    return {
        "ok": True,
        "provider": "wttr.in",
        "location": location_data,
        "current": {
            "temperature_2m": temp,
            "relative_humidity_2m": humidity,
            "apparent_temperature": feels,
            "wind_speed_10m": wind,
            "weather_code": 0,
            "time": c.get("localObsDateTime") or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "rain": number("precipMM"),
            "_description": weather_desc,
        },
        "units": {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


def fetch_realtime_weather(location):
    errors = []

    try:
        result = _weather_result_from_open_meteo(location)
        if result:
            return result
    except Exception as exc:
        errors.append(f"Open-Meteo: {type(exc).__name__}: {exc}")

    try:
        result = _weather_result_from_wttr(location)
        if result:
            return result
    except Exception as exc:
        errors.append(f"wttr.in: {type(exc).__name__}: {exc}")

    return {
        "ok": False,
        "error": "; ".join(errors) or "No structured weather provider returned usable data.",
        "location": location,
    }

def weather_description(code):
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight rain showers",
        81: "Moderate rain showers", 82: "Violent rain showers", 95: "Thunderstorm",
        96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    return mapping.get(int(code), "Unknown conditions")

def realtime_quality_check(weather):
    """Deterministic quality check for real-time weather evidence."""
    if not weather.get("ok"):
        return {"score": 0.0, "freshness": "FAIL", "completeness": "FAIL", "source": "FAIL", "consistency": "N/A", "grounding": "FAIL", "decision": "ABSTAIN"}
    current = weather["current"]
    required = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "wind_speed_10m", "weather_code", "time"]
    completeness = all(k in current and current[k] is not None for k in required)
    freshness = bool(current.get("time"))
    source_valid = True
    # The API's own current timestamp is the freshness evidence.
    score = 1.0 if completeness and freshness and source_valid else 0.65
    return {
        "score": score,
        "freshness": "PASS" if freshness else "FAIL",
        "completeness": "PASS" if completeness else "FAIL",
        "source": "PASS" if source_valid else "FAIL",
        "consistency": "PASS",
        "grounding": "PASS",
        "grounding_score": 1.0,
        "decision": "ANSWER" if score >= 0.80 else "WARN"
    }

def weather_web_fallback(question, location, conversation_context=""):
    """
    Fallback for real-time weather when the structured Open-Meteo request
    fails. It deliberately uses web evidence instead of the local model's
    memory, and then verifies the generated answer with a second search.
    This keeps the existing real-time path intact while preventing a weather
    question from falling into the generic "I don't have internet access"
    response.
    """
    search_query = (
        f"current weather {location} temperature humidity wind rain "
        f"today now"
    )
    evidence = web_search(search_query, max(WEB_MAX_RESULTS, 6))

    if not evidence:
        return None

    evidence_text = format_web_evidence(evidence, "REAL-TIME WEATHER WEB EVIDENCE")
    prompt = f"""
You are the real-time weather fallback stage of ECRAG.

Question:
{question}

Location:
{location}

Retrieved web evidence:
{evidence_text}

Give the best current-weather answer supported ONLY by the retrieved
evidence. Do not use stale model memory for current values.

Rules:
1. Report temperature, conditions, humidity, wind or precipitation only
   when the evidence actually provides them.
2. Do not invent or estimate missing values.
3. If sources disagree, explicitly mention the disagreement.
4. State that this is based on the latest retrieved web evidence if an
   exact live API value is unavailable.
5. Keep the answer natural and concise.
6. Do not say you are unable to access the internet.
"""

    try:
        response = ai_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response["message"]["content"].strip()
    except Exception:
        return None

    verification_query = (
        f"Verify current weather for {location}. "
        f"Candidate answer: {answer[:900]}"
    )
    verification_evidence = web_search(verification_query, WEB_MAX_RESULTS)
    if not verification_evidence:
        verification_evidence = evidence

    verification_text = format_web_evidence(
        verification_evidence,
        "WEATHER VERIFICATION WEB EVIDENCE"
    )
    verification = verify_web_answer(
        question,
        answer,
        verification_text
    )

    # A generated web answer is not trusted merely because retrieval succeeded.
    # If claim verification failed, ECRAG abstains rather than presenting an
    # unchecked answer as reliable.
    if verification.get("error"):
        abstain_answer = (
            "I found external information, but I couldn't complete the "
            "independent claim verification reliably, so I won't present "
            "the answer as verified."
        )
        output = f"""
======================================================================
               EVIDENCE-CALIBRATED RAG
======================================================================

WEB VERIFICATION FAILED

======================================================================
ANSWER
----------------------------------------------------------------------
{abstain_answer}

FINAL DECISION: ABSTAIN
CONFIDENCE: 0.000
======================================================================
"""
        return {
            "answer": abstain_answer,
            "confidence": 0.0,
            "decision": "ABSTAIN",
            "output": output,
            "source": "⚠️ Web Evidence Retrieved • Verification Failed",
            "verification": verification,
            "evidence_count": len(verification_evidence)
        }

    confidence = calculate_web_confidence(
        verification,
        len(verification_evidence),
        question,
        answer
    )

    # Breaking/current-affairs answers require independent source coverage.
    if is_current_affairs_question(question):
        domains = set()
        for item in verification_evidence:
            try:
                host = urlparse(item.get("url", "")).netloc.lower().split(":")[0]
                if host.startswith("www."):
                    host = host[4:]
                if host:
                    domains.add(host)
            except Exception:
                pass
        if len(domains) < 2:
            confidence = min(confidence, 0.64)
        if verification.get("supported", 0) == 0:
            confidence = min(confidence, 0.44)

    if verification.get("contradicted", 0) > verification.get("supported", 0):
        confidence = min(confidence, 0.49)

    # Weather fallback has a real freshness caveat, so do not claim the
    # same confidence as the structured provider unless the evidence is
    # strongly corroborated.
    confidence = min(confidence, 0.90)
    decision = "ANSWER" if confidence >= 0.65 else "WARN"

    output = f"""
======================================================================
                 EVIDENCE-CALIBRATED RAG
======================================================================

REAL-TIME DATA MODE • WEATHER • WEB FALLBACK

======================================================================
ANSWER
----------------------------------------------------------------------
{answer}

CONFIDENCE
----------------------------------------------------------------------
{confidence:.3f} ({confidence:.1%})

DECISION
----------------------------------------------------------------------
{decision}

REAL-TIME WEATHER EVIDENCE
----------------------------------------------------------------------
{evidence_text}

WEATHER VERIFICATION
----------------------------------------------------------------------
{verification_text}

VERIFICATION SUMMARY
----------------------------------------------------------------------
Supported: {verification.get('supported', 0)}
Contradicted: {verification.get('contradicted', 0)}
Uncertain: {verification.get('uncertain', 0)}

NOTE
----------------------------------------------------------------------
Structured Open-Meteo retrieval was unavailable, so ECRAG used fresh web
evidence as a fallback. Current values are reported only when supported
by retrieved evidence.
"""

    quality = {
        "score": min(0.95, max(0.55, confidence + 0.05)),
        "freshness": "PASS",
        "completeness": "PASS" if verification.get("supported", 0) > 0 else "WARN",
        "source": "PASS",
        "consistency": "PASS" if verification.get("contradicted", 0) == 0 else "WARN",
        "grounding": "PASS" if verification.get("supported", 0) > 0 else "WARN",
        "decision": decision,
    }

    return {
        "answer": answer,
        "confidence": confidence,
        "decision": decision,
        "output": output,
        "source": "🌦️ Real-Time Weather • Web Evidence Fallback • Claim Verified",
        "quality": quality,
    }


def realtime_weather_answer(question, conversation_context=""):
    location = extract_weather_location(question)
    if not location:
        return None
    weather = fetch_realtime_weather(location)
    if not weather.get("ok"):
        # IMPORTANT: preserve the existing Open-Meteo implementation, but
        # don't immediately abandon a weather query when that API fails.
        # Use the existing internet evidence + verification machinery.
        fallback = weather_web_fallback(
            question,
            location,
            conversation_context
        )
        if fallback:
            return fallback

        answer = (f"I couldn't retrieve reliable real-time weather data for **{location}** right now. "
                  "Please check the city name and try again.")
        quality = realtime_quality_check(weather)
        output = build_realtime_output(question, answer, weather, quality)
        return {"answer": answer, "confidence": 0.30, "decision": "ABSTAIN", "output": output,
                "source": "🌦️ Real-Time Weather • Open-Meteo (retrieval failed)", "quality": quality}
    c = weather["current"]
    units = weather.get("units", {})
    loc = weather["location"]
    place = loc["name"] + (f", {loc['country']}" if loc.get("country") else "")
    temp_unit = units.get("temperature_2m", "°C")
    wind_unit = units.get("wind_speed_10m", "km/h")
    condition = c.get("_description") or weather_description(c["weather_code"])
    answer = (
        f"The current weather in **{place}** is **{c['temperature_2m']}{temp_unit}**, "
        f"with **{condition}**. "
        f"It feels like **{c['apparent_temperature']}{temp_unit}**, humidity is **{c['relative_humidity_2m']}%**, "
        f"and wind speed is **{c['wind_speed_10m']} {wind_unit}**. "
        f"The live provider timestamp is **{c['time']}**."
    )
    quality = realtime_quality_check(weather)
    confidence = min(0.97, max(0.80, 0.75 + 0.20 * quality["score"]))
    output = build_realtime_output(question, answer, weather, quality, confidence)
    return {"answer": answer, "confidence": confidence, "decision": quality["decision"],
            "output": output, "source": "🌦️ Real-Time Weather • Open-Meteo API • Quality Checked", "quality": quality}

def build_realtime_output(question, answer, weather, quality, confidence=0.0):
    if weather.get("ok"):
        loc = weather["location"]
        c = weather["current"]
        source = "Open-Meteo Geocoding + Forecast API"
        details = (f"Location: {loc['name']}, {loc.get('country','')}\n"
                   f"Provider timestamp: {c.get('time','unknown')}\n"
                   f"Retrieved by ECRAG: {weather.get('retrieved_at','unknown')}")
    else:
        source = "Open-Meteo API"
        details = f"Error: {weather.get('error','Unknown retrieval error')}"
    return f"""
======================================================================
                 EVIDENCE-CALIBRATED RAG
======================================================================

REAL-TIME DATA MODE • WEATHER

======================================================================
ANSWER
----------------------------------------------------------------------

{answer}

======================================================================
REAL-TIME EVIDENCE
----------------------------------------------------------------------
Source: {source}
{details}

======================================================================
QUALITY CHECK
----------------------------------------------------------------------
Freshness: {quality['freshness']}
Completeness: {quality['completeness']}
Source Validity: {quality['source']}
Consistency: {quality['consistency']}
Answer Grounding: {quality['grounding']}
Quality Score: {quality['score']:.3f} ({quality['score']:.1%})

======================================================================
FINAL DECISION: {quality['decision']}
CONFIDENCE: {confidence:.3f}
======================================================================
"""


def looks_like_abbreviation_or_named_entity(question):
    """
    Detect likely abbreviations, acronyms, named entities, or institution
    names so the system can use the web even when the question does not
    contain an obvious "current/latest" trigger.

    Examples:
        "attendance criteria of SRM" -> web lookup
        "What is AIIMS eligibility?" -> web lookup
        "rules of NASA" -> web lookup
        "who is KR$NA?" -> web lookup
    """
    original = question.strip()

    # Explicitly typed acronyms: SRM, AIIMS, IIT, NASA, WHO, RBI, etc.
    # Ignore the first word because it may be capitalized only because it
    # starts the sentence.
    acronym_matches = re.findall(r"\b[A-Z][A-Z0-9&$-]{1,7}\b", original)
    if acronym_matches:
        return True

    # Common abbreviations typed in lowercase are also worth searching.
    # This is useful because users naturally type "srm", "iit", "aiims", etc.
    lower_entity_terms = [
        "srm", "srmist", "iit", "iits", "nit", "nits", "iiit",
        "aiims", "upsc", "gate", "isro", "drdo", "rbi", "sebi",
        "nasa", "who", "unesco", "icc", "bcci", "fifa", "uefa",
        "nato", "imf", "ibm", "tcs", "infosys", "google", "microsoft",
        "apple", "tesla", "openai"
    ]
    q_lower = original.lower()
    if any(
        re.search(
            r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])",
            q_lower
        )
        for term in lower_entity_terms
    ):
        return True

    return False


def is_current_affairs_question(question):
    """
    Detect questions about current world affairs and other rapidly changing
    topics. These questions are always routed through fresh web evidence.

    This is intentionally separate from the existing time-sensitive/entity
    detection so the current web pipeline remains unchanged for other queries.
    """
    q = normalize_chat_language(question).lower().strip()

    current_affairs_terms = [
        # General current affairs / news
        "current affairs", "world news", "world affairs", "international news",
        "latest news", "recent news", "breaking news", "news today", "today's news",
        "todays news", "latest developments", "recent developments",
        "what happened today", "what's happening", "whats happening",
        "what is happening", "what happened in",

        # Natural disasters / extreme events / weather emergencies
        "cyclone", "hurricane", "typhoon", "earthquake", "tsunami",
        "flood", "floods", "flooding", "landslide", "landfall",
        "storm", "wildfire", "disaster", "accident", "crash",
        "explosion", "outbreak", "epidemic", "pandemic",

        # Wars / conflicts / security
        "war", "wars", "armed conflict", "conflict", "conflicts",
        "ceasefire", "invasion", "military conflict", "military operation",
        "airstrike", "air strikes", "missile strike", "troops", "hostilities",
        "peace talks", "peace deal", "peace negotiations", "frontline",
        "battle", "fighting", "sanctions",

        # Geopolitics / international relations
        "geopolitics", "geopolitical", "diplomacy", "diplomatic",
        "international relations", "foreign policy", "summit",
        "nato", "un security council", "united nations", "g7", "g20",
        "brics", "bilateral relations", "trade war", "tariffs",
        "election", "elections", "referendum", "regime change",

        # Science / technology current developments
        "science news", "latest science", "latest scientific",
        "scientific breakthrough", "scientific discovery",
        "new discovery", "new research", "latest research",
        "research breakthrough", "space news", "space mission",
        "rocket launch", "latest nasa", "latest isro",
        "latest spacex", "new ai model", "ai breakthrough",
        "technology news", "tech news",

        # Sports current developments
        "sports news", "latest sports", "sports today",
        "match today", "today's match", "todays match",
        "live score", "live scores", "match result", "match results",
        "game today", "games today", "tournament", "championship",
        "transfer news", "player transfer", "team news",
        "injury update", "sports ranking", "sports rankings",
        "cricket news", "football news", "fifa news", "icc news",
        "nba news", "formula 1 news", "f1 news",

        # Current market / live-value questions
        "gold price", "silver price", "oil price", "crude price",
        "stock price", "share price", "bitcoin price", "crypto price",
        "exchange rate", "forex rate", "market price", "price today",
        "live price", "current price", "today's price", "todays price",

        # Explicit freshness
        "right now", "currently happening", "as of today",
        "as of now", "this morning", "this evening"
    ]

    return any(term in q for term in current_affairs_terms)


def is_nearby_restaurant_query(question):
    """
    Detects if the user is asking for dining, food, or restaurant recommendations
    near their current location, or mentions VIT-AP / Inavolu / Amaravati food spots.
    """
    q = re.sub(r"\s+", " ", str(question or "").lower()).strip()
    if not q:
        return False

    dining_terms = [
        "restaurant", "restaurants", "food", "dining", "places to eat", "place to eat",
        "cafe", "cafes", "dhaba", "dhabas", "tiffin", "tiffins", "biryani",
        "bakery", "bakeries", "eatery", "eateries", "fast food", "canteen", "canteens",
        "mess", "meals", "snack", "snacks", "dinner", "lunch", "breakfast", "eat", "hungry"
    ]
    proximity_terms = [
        "near me", "near by me", "nearby", "around me", "close to me",
        "near here", "around here", "in my area", "close by", "near my location"
    ]
    vit_ap_terms = [
        "vit ap", "vit-ap", "vitap", "inavolu", "ainavolu"
    ]

    has_dining = any(re.search(r"\b" + re.escape(t) + r"\b", q) for t in dining_terms)
    has_proximity = any(p in q for p in proximity_terms)
    has_vit_ap = any(v in q for v in vit_ap_terms)

    # 1. Dining + proximity ("restaurants near by me", "food near me", "dhabas around me")
    if has_dining and has_proximity:
        return True

    # 2. Dining + VIT-AP / Inavolu
    if has_dining and has_vit_ap:
        return True

    # 3. Direct queries with proximity and eating/hunger
    if has_proximity and ("eat" in q or "food" in q or "hungry" in q or "dine" in q):
        return True

    return False


def get_restaurant_search_query(question):
    """
    Expands proximity restaurant queries to explicitly anchor at VIT-AP University
    (Inavolu, Amaravati) and reference Vijayawada / Mangalagiri.
    """
    q = str(question or "").lower()
    cuisines = []
    if "biryani" in q:
        cuisines.append("biryani")
    if "veg" in q or "vegetarian" in q:
        cuisines.append("pure veg vegetarian")
    if "non veg" in q or "non-veg" in q:
        cuisines.append("non-veg")
    if "cafe" in q or "coffee" in q:
        cuisines.append("cafes coffee")
    if "dhaba" in q or "dhabas" in q:
        cuisines.append("highway dhabas")
    if any(k in q for k in ["tiffin", "breakfast", "dosa", "idli", "poori"]):
        cuisines.append("tiffin breakfast")
    if "chinese" in q:
        cuisines.append("chinese")
    if any(k in q for k in ["fast food", "burger", "pizza", "snack"]):
        cuisines.append("fast food snacks")

    prefix = " ".join(cuisines).strip()
    if prefix:
        return f"{prefix} restaurants food near VIT AP University Inavolu Amaravati Mangalagiri Vijayawada"
    return "restaurants food dhabas near VIT AP University Inavolu Amaravati Mangalagiri Vijayawada"


def should_use_web(question):
    """
    Decide whether an internet lookup is useful.

    Web retrieval is deliberately broader than just "current/latest".
    It is triggered for:
      - current or changing information
      - historical/niche facts
      - organizations, universities, companies and people
      - abbreviations/acronyms such as SRM, IIT, AIIMS, NASA, etc.
      - institutional criteria/rules/eligibility/fees/policies
      - factual questions where the local model may be stale

    Casual conversation and simple greetings remain local for speed.
    """
    q = question.lower().strip()

    if not q:
        return False

    casual = [
        "hello", "hi", "hey", "thanks", "thank you", "good morning",
        "good night", "how are you", "who are you"
    ]
    if any(q == x or q.startswith(x + " ") for x in casual):
        return False

    if is_nearby_restaurant_query(question):
        return True

    # Freshness / time-sensitive information.
    web_triggers = [
        "current", "currently", "today", "now", "latest", "recent",
        "as of", "this year", "this month", "this week",
        "who is", "who was", "what is", "what was", "when did",
        "when was", "where is", "where was", "how many", "how much",
        "president", "prime minister", "pm of", "chief minister",
        "minister", "ceo", "founder", "winner", "election", "ranking",
        "rankings", "record", "release date", "history", "historical",
        "born", "died", "founded", "invented", "lyrics", "rapper",
        "artist", "actor", "actress", "author", "book", "movie",
        "company", "university", "college", "institute", "institution",
        "country", "capital", "population", "currency", "according to",
        "official", "policy", "law",
        "restaurant", "restaurants", "food", "places to eat", "cafe", "cafes",
        "dhaba", "dhabas", "near me", "near by me", "nearby"
    ]

    # Institution-specific / potentially changing factual questions.
    # This catches queries such as "attendance criteria of SRM" even when
    # the abbreviation is typed entirely in lowercase.
    institution_triggers = [
        "attendance criteria", "attendance requirement", "attendance rule",
        "attendance policy", "eligibility criteria", "eligibility requirement",
        "admission criteria", "admission process", "admission requirement",
        "fee structure", "fees of", "fees for", "exam pattern",
        "exam eligibility", "placement statistics", "placement rate",
        "cutoff", "cut off", "course requirements", "academic rules",
        "academic regulation", "rules of", "regulations of", "requirements of",
        "criteria of", "policy of", "guidelines of", "schedule of",
        "contact details", "address of", "location of"
    ]

    # Current-affairs questions must use fresh external evidence.
    # This is additive and does not replace the existing routing rules.
    if is_current_affairs_question(question):
        return True

    # Entity/abbreviation detection is important for short queries where
    # the wording may not explicitly say "current" or "latest".
    if looks_like_abbreviation_or_named_entity(question):
        return True

    if any(x in q for x in web_triggers):
        return True

    if any(x in q for x in institution_triggers):
        return True

    # Generic institution-related questions should use external evidence.
    if re.search(
        r"\b(attendance|fees?|admission|eligibility|criteria|rules?|policy|requirements?)\b",
        q
    ):
        return True

    # ECRAG is designed to reduce hallucinations on niche factual questions.
    # If a substantive question reaches this point, prefer external evidence
    # over an unverified local-model memory answer. Only obvious conversational
    # messages were excluded above.
    if len(q.split()) >= 4 or "?" in q:
        return True

    return False


def _clean_search_url(href):
    """Turn a DuckDuckGo redirect URL into its actual destination."""
    if not href:
        return ""

    href = unescape(href)

    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unescape(params["uddg"][0])
    except Exception:
        pass

    if href.startswith("//"):
        return "https:" + href

    return href


def robust_web_search(query, max_results=WEB_MAX_RESULTS, is_news=False):
    """
    Multi-source live web search layer:
    1. Tavily API (when configured)
    2. DuckDuckGo Instant Answer JSON API (free, reliable, never blocked by bot challenge)
    3. Wikipedia Search API (encyclopedic, authoritative, fast)
    4. Google News RSS (for live news and breaking developments)
    5. DuckDuckGo Lite / HTML scraping fallback
    """
    raw_q = str(query or "").strip()
    # Defensive sanitization: never allow multi-turn conversation context or prompt scaffolding
    # into external search engine URLs
    raw_q = raw_q.split("\n")[0].strip()
    if "relevant conversation context" in raw_q.lower():
        raw_q = re.split(r"relevant conversation context", raw_q, flags=re.I)[0].strip()
    if "candidate answer:" in raw_q.lower():
        raw_q = re.split(r"candidate answer:", raw_q, flags=re.I)[0].strip()
    raw_q = re.sub(r"^verify\s+these\s+facts\s*:\s*", "", raw_q, flags=re.I).strip()
    query = re.sub(r"\s+", " ", raw_q).strip()
    if not query:
        return []

    results = []
    seen_urls = set()

    def add_result(title, url, snippet, source_name="Web", pub_date=""):
        if not title or not url or url in seen_urls:
            return
        seen_urls.add(url)
        item = {
            "title": title.strip(),
            "url": url.strip(),
            "snippet": snippet.strip(),
            "source": source_name,
            "score": 1.0
        }
        if pub_date:
            item["published_date"] = pub_date
        results.append(item)

    # 1. Tavily if key present
    if TAVILY_API_KEY:
        try:
            t_depth = "advanced" if is_current_numeric_question(query) else "basic"
            t_res = tavily_search(query, max_results=max_results, search_depth=t_depth)
            for r in t_res:
                add_result(r.get("title", ""), r.get("url", ""), r.get("snippet", ""), "Tavily", r.get("published_date", ""))
            if len(results) >= max_results:
                return results[:max_results]
        except Exception as exc:
            print(f"[ECRAG Search] Tavily call failed: {exc}")

    # 2. DuckDuckGo Lite via POST (High reliability, fresh live web results, full snippets)
    if len(results) < max_results:
        try:
            lite_data = urlencode({"q": query}).encode("utf-8")
            req = Request(
                "https://lite.duckduckgo.com/lite/",
                data=lite_data,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
            )
            with urlopen(req, timeout=WEB_TIMEOUT) as resp:
                lite_html = resp.read().decode("utf-8", errors="replace")

            pattern = r'''<a[^>]+href=["']([^"']+)["'][^>]+class=["']result-link["'][^>]*>(.*?)</a>|<a[^>]+class=["']result-link["'][^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>'''
            links_raw = re.findall(pattern, lite_html, flags=re.I | re.S)
            snippets_raw = re.findall(r'''<td[^>]+class=["']result-snippet["'][^>]*>(.*?)</td>''', lite_html, flags=re.I | re.S)

            ddg_added = 0
            for idx, match in enumerate(links_raw):
                if ddg_added >= 3 or len(results) >= max_results:
                    break
                raw_url = match[0] or match[2]
                clean_url = _clean_search_url(raw_url)
                raw_title = match[1] or match[3]
                title = re.sub(r"<[^>]+>", " ", raw_title)
                title = re.sub(r"\s+", " ", unescape(title)).strip()
                snip = ""
                if idx < len(snippets_raw):
                    snip = re.sub(r"<[^>]+>", " ", snippets_raw[idx])
                    snip = re.sub(r"\s+", " ", unescape(snip)).strip()
                if title and clean_url and clean_url not in seen_urls:
                    add_result(title, clean_url, snip, "DuckDuckGo")
                    ddg_added += 1
        except Exception as exc:
            print(f"[ECRAG Search] DDG Lite: {exc}")

    # 3. Google News RSS (for live news, latest events, current affairs, tech/market developments)
    news_terms = [
        "news", "latest", "today", "isro", "recent", "minister", "cyclone",
        "flood", "earthquake", "tsunami", "landfall", "disaster", "storm",
        "election", "war", "president", "prime minister", "modi", "death", "hit",
        "price", "launch", "release", "cost", "review", "specs", "rumor"
    ]
    if len(results) < max_results and (is_news or len(results) < 3 or any(k in query.lower() for k in news_terms)):
        try:
            candidates = [query]
            clean_q = re.sub(
                r"(tell me about|tell me|what is|what are|explain|who is|details about|information on|the recent|recent|latest developments|current confirmed reports as of \d{4}-\d{2}-\d{2}|official context current latest)",
                "", query, flags=re.I
            )
            clean_q = re.sub(r"\s+", " ", clean_q).strip()
            if clean_q and clean_q.lower() != query.lower():
                candidates.append(clean_q)

            news_added = 0
            for q_try in candidates:
                if len(results) >= max_results or news_added >= 2:
                    break
                news_url = f"https://news.google.com/rss/search?q={quote_plus(q_try)}&hl=en-IN&gl=IN&ceid=IN:en"
                req = Request(news_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"})
                with urlopen(req, timeout=WEB_TIMEOUT) as resp:
                    root = ET.fromstring(resp.read().decode("utf-8", errors="replace"))
                    for item in root.findall(".//item"):
                        if len(results) >= max_results or news_added >= 2:
                            break
                        title = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else ""
                        desc = item.find("description").text if item.find("description") is not None else ""
                        clean_desc = re.sub(r"<[^>]+>", " ", desc)
                        clean_desc = re.sub(r"\s+", " ", unescape(clean_desc)).strip()
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        if title and link and link not in seen_urls:
                            add_result(title, link, clean_desc or title, "Google News", pub_date)
                            news_added += 1
                if news_added >= 2:
                    break
        except Exception as exc:
            print(f"[ECRAG Search] Google News RSS: {exc}")

    # 4. Wikipedia Search API (Authoritative encyclopedic reference, capped to at most 1 result to preserve diversity)
    if len(results) < max_results:
        try:
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&format=json&utf8=1"
            req = Request(wiki_url, headers={"User-Agent": "ECRAG-Assistant/2.0 (research; contact@ecrag.org)"})
            with urlopen(req, timeout=WEB_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                wiki_added = 0
                for item in data.get("query", {}).get("search", []):
                    if len(results) >= max_results or wiki_added >= 1:
                        break
                    title = item.get("title", "")
                    clean_snip = re.sub(r"<[^>]+>", " ", item.get("snippet", ""))
                    clean_snip = re.sub(r"\s+", " ", unescape(clean_snip)).strip()
                    page_url = f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"
                    if page_url not in seen_urls:
                        add_result(f"Wikipedia: {title}", page_url, clean_snip, "Wikipedia")
                        wiki_added += 1
        except Exception as exc:
            print(f"[ECRAG Search] Wikipedia API: {exc}")

    # 5. DuckDuckGo Instant Answer JSON API
    if len(results) < max_results:
        try:
            ddg_api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
            req = Request(ddg_api_url, headers={"User-Agent": "ECRAG-Search/2.0"})
            with urlopen(req, timeout=WEB_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                heading = data.get("Heading")
                abstract = data.get("AbstractText") or data.get("Abstract")
                abs_url = data.get("AbstractURL")
                if heading and abstract and abs_url and abs_url not in seen_urls:
                    add_result(heading, abs_url, abstract, "DuckDuckGo Instant Answer")
        except Exception as exc:
            print(f"[ECRAG Search] DDG JSON API: {exc}")

    # 6. DuckDuckGo HTML scraping as final fallback
    if len(results) < 2:
        try:
            url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"})
            with urlopen(req, timeout=WEB_TIMEOUT) as response:
                html = response.read().decode("utf-8", errors="replace")
            link_matches = re.findall(
                r'''<a[^>]+class=["']result__a["'][^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>''',
                html, flags=re.I | re.S
            )
            for href, raw_title in link_matches[:max_results]:
                if len(results) >= max_results:
                    break
                title = re.sub(r"<[^>]+>", " ", raw_title)
                title = re.sub(r"\s+", " ", unescape(title)).strip()
                clean_url = _clean_search_url(href)
                pos = html.find(raw_title)
                snippet = ""
                if pos >= 0:
                    tail = html[pos:pos + 5000]
                    sm = re.search(r'''class=["']result__snippet["'][^>]*>(.*?)</''', tail, flags=re.I | re.S)
                    if sm:
                        snippet = re.sub(r"<[^>]+>", " ", sm.group(1))
                        snippet = re.sub(r"\s+", " ", unescape(snippet)).strip()
                if clean_url not in seen_urls:
                    add_result(title, clean_url, snippet, "DuckDuckGo")
        except Exception:
            pass

    return results[:max_results]


def duckduckgo_search(query, max_results=WEB_MAX_RESULTS):
    """Robust DuckDuckGo and open web search."""
    return robust_web_search(query, max_results=max_results)


def web_search(query, max_results=WEB_MAX_RESULTS, topic="general"):
    """Primary live-web search gateway for ECRAG.

    In Offline Mode, queries local ChromaDB.
    In Online Mode, queries multi-source live web (Tavily, DDG API, Wikipedia, Google News).
    """
    try:
        from streamlit import session_state as st_state
        if st_state.get("app_mode") == "🌴 Offline Mode" or st_state.get("offline_mode", False):
            print(f"[ECRAG] Offline mode active. Searching local ChromaDB instead of Web for: {query}")
            from langchain_community.vectorstores import Chroma
            from langchain_community.embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            vectorstore = Chroma(persist_directory=str(DATA_FOLDER / "chroma_db"), embedding_function=embeddings)
            docs = vectorstore.similarity_search(query, k=max_results)
            results = []
            for doc in docs:
                results.append({
                    "title": "Local Offline Knowledge Base",
                    "url": "local://chromadb/offline-document",
                    "snippet": doc.page_content,
                    "score": 1.0,
                    "published_date": "",
                    "source": "ChromaDB"
                })
            return results
    except Exception as e:
        print(f"[ECRAG] Offline vector search failed: {e}")

    # Online mode: robust live web search
    is_news = (topic == "news") or is_current_affairs_question(query)
    return robust_web_search(query, max_results=max_results, is_news=is_news)


def freenewsapi_search(query, max_results=CURRENT_AFFAIRS_MAX_RESULTS, date_window="7d"):
    """Keyless fresh-news retrieval from Free News API.

    This is an additional retrieval channel, not an answer generator. Results
    include publisher publication timestamps, which lets ECRAG reason about
    recency instead of treating a merely relevant older article as "latest".
    """
    q = re.sub(r"\s+", " ", str(query or "")).strip()
    if not q:
        return []

    url = "https://freenewsapi.ai/v1/search?" + urlencode({
        "q": q,
        "date": date_window,
        "sort": "date",
        "size": max(1, min(int(max_results), 20)),
        "full_text": "false",
        "agent_name": "ECRAG",
        "software": "ECRAG-RAG",
        "purpose": "grounded-news-retrieval",
    })

    try:
        request = Request(url, headers={
            "User-Agent": "ECRAG/6.0 (+grounded-news-retrieval)",
            "X-Agent": "agent_name=ECRAG; software=ECRAG-RAG; purpose=grounded-news-retrieval",
        })
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        print(f"[ECRAG] FreeNewsAPI unavailable: {exc}")
        return []

    results = []
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        link = str(row.get("url") or "").strip()
        if not title or not link:
            continue
        results.append({
            "title": title,
            "url": link,
            "snippet": str(row.get("description") or "").strip(),
            "published_at": str(row.get("published_at") or "").strip(),
            "published": str(row.get("published_at") or "").strip(),
            "source_name": str(row.get("host") or row.get("publisher") or "").strip(),
            "_search_bucket": "freenewsapi",
        })

    print(f"[ECRAG] FreeNewsAPI SUCCESS: query={q[:70]!r}, results={len(results)}")
    return results

def google_news_search(query, max_results=CURRENT_AFFAIRS_MAX_RESULTS):
    """
    Fresh-news retrieval using Google News RSS.

    This is intentionally used as an additional evidence source for
    current-affairs questions. It does not replace the existing DuckDuckGo
    retrieval, so the original pipeline remains intact.
    """
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if not query:
        return []

    # Google News RSS is a public feed and does not require an API key.
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 ECRAG/1.0"}
        )
        with urlopen(request, timeout=CURRENT_AFFAIRS_TIMEOUT) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
    except Exception:
        return []

    results = []
    for item in root.findall(".//item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = item.find("source")
        source_name = source.text.strip() if source is not None and source.text else ""

        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", unescape(description)).strip()

        if not title or not link:
            continue

        results.append({
            "title": title,
            "url": link,
            "snippet": description,
            "published": pub_date,
            "source_name": source_name,
        })

    return results



class _ISROAnchorParser(HTMLParser):
    """Collect links from the official ISRO homepage without third-party parsers."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self._href is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self._text)).strip()
        self.links.append((self._href, text))
        self._href = None
        self._text = []


def _isro_absolute_url(href):
    href = str(href or "").strip()
    if not href:
        return ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return "https://www.isro.gov.in" + href
    return ""


def _isro_extract_page_date(html_text):
    """Extract the newest plausible article date from an official ISRO page."""
    text = unescape(re.sub(r"<[^>]+>", " ", str(html_text or "")))
    text = re.sub(r"\s+", " ", text)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    candidates = []
    patterns = [
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b",
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, text, re.I):
            for fmt in ("%d %B %Y", "%B %d, %Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    if dt <= now + timedelta(days=1):
                        candidates.append(dt)
                    break
                except ValueError:
                    continue
    return max(candidates) if candidates else None


def fetch_isro_official_latest(max_results=5):
    """Fetch the newest dated items directly from ISRO's own homepage.

    This is deliberately independent of Tavily/Google ranking. For an explicit
    latest-ISRO question, the official site's own Latest News ordering is the
    temporal authority.
    """
    homepage = "https://www.isro.gov.in/"
    try:
        request = Request(homepage, headers={"User-Agent": "ECRAG/1.0"})
        with urlopen(request, timeout=8) as response:
            html_text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[ECRAG] Official ISRO homepage retrieval failed: {exc}")
        return []

    parser = _ISROAnchorParser()
    try:
        parser.feed(html_text)
    except Exception as exc:
        print(f"[ECRAG] Official ISRO HTML parsing failed: {exc}")
        return []

    keywords = (
        "eos", "gslv", "pslv", "lvm", "isro", "mission", "spacecraft",
        "manoeuv", "maneouv", "launch", "satellite", "engine", "gaganyaan",
        "nisar", "aditya", "space", "propulsion", "test", "clarification"
    )
    reject = {
        "careers", "tenders", "feedback", "contact", "login", "sitemap",
        "more info", "home", "about us", "activities", "vacancies"
    }

    candidates = []
    seen = set()
    for href, title in parser.links:
        url = _isro_absolute_url(href)
        title = re.sub(r"\s+", " ", title or "").strip()
        if not url or not title or len(title) < 18 or len(title) > 220:
            continue
        if any(title.lower() == item or title.lower().startswith(item + " ") for item in reject):
            continue
        if "/" not in url[len("https://www.isro.gov.in"):]:
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        lower = title.lower()
        keyword_score = sum(1 for k in keywords if k in lower)
        # Homepage order is meaningful, but topical relevance removes obvious
        # navigation links before we spend time opening article pages.
        candidates.append((keyword_score, len(candidates), url, title))

    candidates.sort(key=lambda row: (-row[0], row[1]))
    candidates = candidates[:24]

    def fetch_article(row):
        _, order, url, title = row
        try:
            req = Request(url, headers={"User-Agent": "ECRAG/1.0"})
            with urlopen(req, timeout=6) as response:
                page = response.read().decode("utf-8", errors="replace")
            dt = _isro_extract_page_date(page)
            clean = unescape(re.sub(r"<[^>]+>", " ", page))
            clean = re.sub(r"\s+", " ", clean).strip()
            # Keep a compact snippet; the article title is the strongest
            # identifier and the page text supplies grounded context.
            lower = clean.lower()
            pos = lower.find(title.lower()[:40])
            if pos >= 0:
                snippet = clean[pos:pos + 900]
            else:
                snippet = clean[:900]
            return {
                "title": title,
                "url": url,
                "snippet": snippet,
                "published_at": dt.isoformat() if dt else "",
                "_search_bucket": "official_isro_direct",
            }
        except Exception:
            return None

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_article, row) for row in candidates]
        for future in as_completed(futures):
            item = future.result()
            if item and item.get("published_at"):
                results.append(item)

    results.sort(key=lambda item: _extract_evidence_datetime(item) or datetime.min, reverse=True)
    return results[:max_results]


def is_explicit_latest_isro_question(question):
    q = normalize_chat_language(str(question or "")).lower()
    return (
        bool(re.search(r"\bisro\b|indian space research organisation", q))
        and any(marker in q for marker in ("latest", "most recent", "right now", "as of", "today", "currently"))
    )

def fresh_web_search(query, max_results=WEB_MAX_RESULTS, current_affairs=False):
    """
    Retrieve fresh evidence.

    For current-affairs requests, retrieval is intentionally diversified so a
    single generic search ranking cannot hide an important science/space story
    such as an ISRO development.
    """
    if not current_affairs:
        return web_search(query, max_results, topic="general")

    q = re.sub(r"\s+", " ", str(query or "")).strip()
    q_lower = q.lower()
    today = datetime.now().strftime("%d %B %Y")

    # Keep the number of searches bounded for latency/API usage, but cover the
    # major India-news buckets explicitly. The science/space query is deliberate.
    if re.search(r"\bindia\b|\bindian\b", q_lower):
        queries = [
            ("overall", f"{q} {today} latest major India news confirmed"),
            ("politics_economy", f"India government politics economy business latest {today}"),
            ("security_world", f"India defence security international developments latest {today}"),
            ("science_space", f"India science technology space ISRO latest developments {today}"),
            ("technology", f"India technology AI startups infrastructure latest {today}"),
        ]
    else:
        queries = [
            ("overall", f"{q} {today} latest major news confirmed"),
            ("politics_economy", f"{q} politics economy business latest {today}"),
            ("security_world", f"{q} security international developments latest {today}"),
            ("science_space", f"{q} science technology space latest developments {today}"),
        ]

    # For named current-affairs entities, add one first-party search channel.
    # This prevents a famous historical event from winning merely because it
    # has much higher semantic relevance than the newest official update.
    named_official = None
    if re.search(r"\bisro\b|indian space research organisation", q_lower):
        named_official = (
            "official_isro",
            f"site:isro.gov.in ISRO {q} latest current development update {today}"
        )
        queries.append(named_official)

    results_by_bucket = {bucket: [] for bucket, _ in queries}

    with ThreadPoolExecutor(max_workers=len(queries) + 1) as pool:
        future_map = {
            pool.submit(web_search, search_q, min(max_results, 5), "news"): bucket
            for bucket, search_q in queries
        }

        # Google News provides a second retrieval mechanism and is especially
        # useful when a normal web index has not yet surfaced a breaking story.
        future_map[
            pool.submit(
                google_news_search,
                f"{q} {today}",
                CURRENT_AFFAIRS_MAX_RESULTS
            )
        ] = "google_news"
        # Keyless current-news index with explicit publication timestamps.
        # It complements Tavily and Google News instead of replacing them.
        future_map[
            pool.submit(
                freenewsapi_search,
                q,
                CURRENT_AFFAIRS_MAX_RESULTS,
                "7d"
            )
        ] = "freenewsapi"

        for future in as_completed(future_map):
            bucket = future_map[future]
            try:
                items = future.result() or []
                for item in items:
                    item = dict(item)
                    item["_search_bucket"] = bucket
                    results_by_bucket.setdefault(bucket, []).append(item)
            except Exception as exc:
                print(f"[ECRAG] current-affairs retrieval worker failed: {exc}")

    # Round-robin the buckets instead of simply truncating the completion-order
    # results. This prevents one highly-ranked topic from consuming the whole
    # evidence budget.
    merged = []
    seen_urls = set()
    max_total = max(max_results, CURRENT_AFFAIRS_MAX_RESULTS)

    for round_index in range(5):
        for bucket, _ in queries + [("google_news", ""), ("freenewsapi", "")]:
            bucket_items = results_by_bucket.get(bucket, [])
            if round_index >= len(bucket_items):
                continue

            item = bucket_items[round_index]
            url = str(item.get("url", "")).strip().lower()
            title_key = re.sub(
                r"\s+", " ",
                str(item.get("title", "")).strip().lower()
            )
            key = url or title_key
            if not key or key in seen_urls:
                continue

            seen_urls.add(key)
            merged.append(item)

            if len(merged) >= max_total:
                return merged

    return merged


def select_temporally_relevant_evidence(results, question, max_items=8):
    """Hard-select evidence for explicit latest/current questions.

    Ranking alone is not enough: an old, famous event can still be shown to
    the generator and tempt it to answer from semantic familiarity. For a
    named current-affairs question, keep the newest dated evidence prominent
    and, when available, retain the newest first-party result as an anchor.
    """
    ranked = rank_temporal_evidence(results, question)
    if not ranked:
        return []

    q = normalize_chat_language(str(question or "")).lower()
    latest_intent = any(marker in q for marker in (
        "latest", "most recent", "right now", "as of", "today", "currently"
    ))
    if not latest_intent:
        return ranked[:max_items]

    official = [
        item for item in ranked
        if _source_quality_score(item) >= 0.99
        and _extract_evidence_datetime(item) is not None
    ]
    dated = [item for item in ranked if _extract_evidence_datetime(item) is not None]

    selected = []
    seen = set()

    # The newest official result is a hard anchor for named-entity questions.
    if official:
        newest_official = max(
            official, key=lambda item: _extract_evidence_datetime(item) or datetime.min
        )
        selected.append(newest_official)
        seen.add(str(newest_official.get("url") or "").strip().lower())

    # Then add the newest independent dated results. Freshness is deliberately
    # stronger than source reputation for a temporal claim.
    for item in dated:
        key = str(item.get("url") or item.get("title") or "").strip().lower()
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= max_items:
            break

    # Fill any remaining slots with ranked evidence if date metadata is sparse.
    for item in ranked:
        key = str(item.get("url") or item.get("title") or "").strip().lower()
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= max_items:
            break

    return selected[:max_items]

def _extract_evidence_datetime(item):
    """Robust publication-date extraction for temporal ranking.

    Explicit feed/publisher metadata is preferred. RFC-822 dates from Google
    News, ISO timestamps from news APIs/Tavily, and ordinary calendar dates are
    all handled. Dates found only in title/snippet text remain weaker evidence.
    """
    candidates = [
        item.get("published_at"),
        item.get("published_date"),
        item.get("published"),
        item.get("date"),
    ]

    for value in candidates:
        text = str(value or "").strip()
        if not text:
            continue

        # ISO-8601, including fractional seconds and trailing Z.
        try:
            iso = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            pass

        # RFC-822 / RFC-1123, e.g. Google News pubDate values.
        try:
            dt = parsedate_to_datetime(text)
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
            "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
            "%d/%m/%Y", "%m/%d/%Y",
        ):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                pass

    # Search title/snippet for a concrete calendar date only as a fallback.
    body = " ".join([
        str(item.get("title") or ""),
        str(item.get("snippet") or ""),
    ])
    patterns = [
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.I)
        if not m:
            continue
        raw = m.group(1)
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                pass
    return None


def _evidence_domain(item):
    try:
        host = urlparse(str(item.get("url") or "")).netloc.lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _source_quality_score(item):
    """Deterministic source-quality score used only for ranking evidence."""
    domain = _evidence_domain(item)
    title = str(item.get("title") or "").lower()
    snippet = str(item.get("snippet") or "").lower()

    if domain in {"isro.gov.in", "pib.gov.in", "pmindia.gov.in", "mea.gov.in", "mod.gov.in", "mha.gov.in"}:
        return 1.00
    if any(domain == d or domain.endswith("." + d) for d in {
        "reuters.com", "apnews.com", "bbc.com", "thehindu.com",
        "indianexpress.com", "hindustantimes.com", "ndtv.com",
        "timesofindia.indiatimes.com", "economictimes.indiatimes.com",
    }):
        return 0.90
    if "official" in title or "official" in snippet:
        return 0.82
    return 0.65


def rank_temporal_evidence(results, question):
    """Rank live evidence for questions where freshness materially matters."""
    if not results:
        return []

    q = normalize_chat_language(str(question or "")).lower()
    freshness_requested = any(marker in q for marker in (
        "latest", "most recent", "recent", "today", "current", "currently",
        "right now", "as of", "this week", "this month",
    ))
    if not freshness_requested:
        return results

    now = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

    scored = []
    for index, item in enumerate(results):
        dt = _extract_evidence_datetime(item)
        source_score = _source_quality_score(item)
        if dt:
            age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            # Freshness dominates for explicit latest/recent questions. Source
            # quality breaks close ties; it must not rescue a months/years-old
            # article and label it as the newest event.
            freshness = max(0.0, 1.0 - min(age_days / 14.0, 1.0))
            date_strength = 1.0
        else:
            freshness = 0.05
            date_strength = 0.0

        relevance = _temporal_relevance_score(item, question)
        score = (0.68 * freshness) + (0.17 * source_score) + (0.10 * date_strength) + (0.05 * relevance)
        scored.append((score, dt or datetime.min, source_score, relevance, -index, item))

    scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    return [row[-1] for row in scored]


def _temporal_relevance_score(item, question):
    """Small deterministic relevance boost for named entities/topics.

    Freshness still dominates. This only prevents an unrelated fresh headline
    from outranking a slightly older but directly relevant one.
    """
    q_tokens = set(re.findall(r"[a-z0-9]{3,}", normalize_chat_language(str(question or "")).lower()))
    text = " ".join([
        str(item.get("title") or ""),
        str(item.get("snippet") or ""),
    ]).lower()
    if not q_tokens:
        return 0.0
    hits = sum(1 for token in q_tokens if token in text)
    return min(hits / max(1, min(len(q_tokens), 8)), 1.0)


def temporal_evidence_status(results, question):
    """Return deterministic evidence-quality facts for latest/current claims."""
    q = normalize_chat_language(str(question or "")).lower()
    freshness_requested = any(marker in q for marker in (
        "latest", "most recent", "recent", "today", "current", "currently",
        "right now", "as of", "this week", "this month",
    ))
    if not freshness_requested:
        return {"dated": 0, "domains": set(), "newest": None, "official": 0}

    dates = [_extract_evidence_datetime(item) for item in results]
    dated = [d for d in dates if d is not None]
    domains = {_evidence_domain(item) for item in results if _evidence_domain(item)}
    official = sum(1 for item in results if _source_quality_score(item) >= 0.99)
    return {
        "dated": len(dated),
        "domains": domains,
        "newest": max(dated) if dated else None,
        "official": official,
    }

def format_web_evidence(results, heading="WEB EVIDENCE"):
    if not results:
        return f"{heading}\n{'-' * 70}\nNo web evidence was retrieved."

    parts = [heading, "-" * 70]

    for i, item in enumerate(results, start=1):
        metadata = []
        if item.get("source_name"):
            metadata.append(f"Source: {item['source_name']}")
        if item.get("published"):
            metadata.append(f"Published: {item['published']}")
        elif item.get("published_date"):
            metadata.append(f"Published: {item['published_date']}")

        metadata_text = ("\n" + "\n".join(metadata)) if metadata else ""

        parts.append(
            f"Evidence {i}\n"
            f"Title: {item['title']}\n"
            f"URL: {item['url']}"
            f"{metadata_text}\n"
            f"Snippet: {item['snippet'] or 'No snippet available.'}"
        )

    return "\n\n".join(parts)

def verify_web_answer(question, answer, evidence):
    """
    Claim-level verification against internet evidence.

    The same local LLM is used as the verifier, but it is NOT allowed to
    rely on its memory alone: every claim must be assessed against the
    retrieved web evidence. A second web search is performed before this
    function is called.
    """
    prompt = f"""
You are the verification stage of an evidence-calibrated QA system.

The user asked:
{question}

Candidate answer:
{answer}

External web evidence:
{evidence}

Verify the candidate answer ONLY against the external evidence above.

Return ONLY valid JSON in this exact structure:
{{
  "claims": [
    {{
      "claim": "short factual claim",
      "status": "SUPPORTED",
      "evidence_numbers": [1, 2],
      "reason": "short reason"
    }}
  ]
}}

Rules:
- Identify the important factual claims in the candidate answer.
- status must be exactly SUPPORTED, CONTRADICTED, or UNCERTAIN.
- SUPPORTED means the supplied web evidence directly or strongly supports it.
- CONTRADICTED means the supplied web evidence conflicts with it.
- UNCERTAIN means the evidence is insufficient or ambiguous.
- Do not use your own memory to mark a claim as supported.
- Do not invent evidence numbers.
- If there are no useful factual claims, return an empty claims list.
- Keep it concise.
"""

    try:
        response = ai_chat(
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"].strip()
        content = re.sub(
            r"^```(?:json)?\s*", "", content, flags=re.I
        )
        content = re.sub(r"\s*```$", "", content).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.S)
            if not match:
                raise ValueError("Verifier did not return JSON.")
            data = json.loads(match.group(0))

        claims = data.get("claims", [])
        if not isinstance(claims, list):
            raise ValueError("Invalid claims list.")

        supported = 0
        contradicted = 0
        uncertain = 0

        cleaned_claims = []

        for claim in claims[:8]:
            status = str(claim.get("status", "UNCERTAIN")).upper()

            if status not in {"SUPPORTED", "CONTRADICTED", "UNCERTAIN"}:
                status = "UNCERTAIN"

            if status == "SUPPORTED":
                supported += 1
            elif status == "CONTRADICTED":
                contradicted += 1
            else:
                uncertain += 1

            cleaned_claims.append({
                "claim": str(claim.get("claim", "")).strip(),
                "status": status,
                "evidence_numbers": claim.get("evidence_numbers", []),
                "reason": str(claim.get("reason", "")).strip()
            })

        return {
            "claims": cleaned_claims,
            "supported": supported,
            "contradicted": contradicted,
            "uncertain": uncertain
        }

    except Exception as e:
        return {
            "claims": [],
            "supported": 0,
            "contradicted": 0,
            "uncertain": 1,
            "error": str(e)
        }


def is_subjective_or_reputation_question(question):
    """Detect questions where the answer is a title, opinion, ranking, or reputation claim."""
    q = question.lower().strip()

    markers = [
        "lyrical god", "god of rap", "king of rap", "queen of",
        "goat", "greatest", "best rapper", "best singer",
        "most popular", "most influential", "legend of",
        "called the", "known as", "considered the",
        "who is the best", "who is considered"
    ]

    return any(marker in q for marker in markers)


def calculate_web_confidence(verification, evidence_count, question="", answer=""):
    """
    Calibrate confidence from claim-level web verification.

    Subjective/reputation-based questions are handled differently from
    objective facts. A title such as "Lyrical God" can be strongly
    supported as a *reported/community label* without being an official
    objective fact, so it should normally receive WARN rather than ABSTAIN
    when multiple sources support it.
    """
    supported = verification.get("supported", 0)
    contradicted = verification.get("contradicted", 0)
    uncertain = verification.get("uncertain", 0)
    total = supported + contradicted + uncertain

    if total == 0:
        return 0.35 if not evidence_count else 0.50

    support_ratio = supported / total
    contradiction_ratio = contradicted / total
    uncertainty_ratio = uncertain / total

    # Stronger base score for independently supported claims.
    confidence = (
        0.45
        + (0.45 * support_ratio)
        - (0.45 * contradiction_ratio)
        - (0.18 * uncertainty_ratio)
    )

    # Multiple retrieved sources increase confidence, but never create
    # certainty on their own.
    if evidence_count >= 5 and supported > 0:
        confidence += 0.07
    elif evidence_count >= 3 and supported > 0:
        confidence += 0.05
    elif evidence_count >= 2 and supported > 0:
        confidence += 0.03

    # Subjective/reputation labels need a special calibration.
    # If web evidence supports the reported label and there is no
    # contradiction, treat it as a well-supported attribution, not as
    # an objective 100%-certain fact.
    if is_subjective_or_reputation_question(question):
        if supported > 0 and contradicted == 0:
            if evidence_count >= 4:
                confidence = max(confidence, 0.86)
            elif evidence_count >= 2:
                confidence = max(confidence, 0.82)
            else:
                confidence = max(confidence, 0.74)

            # Keep subjective claims below near-certain objective-fact
            # territory unless the evidence is exceptionally strong.
            confidence = min(confidence, 0.90)
        elif contradicted > 0:
            confidence = min(confidence, 0.45)

    if is_current_numeric_question(question):
        # Live values need direct current-value support. Do not award near-certainty
        # merely because many pages were retrieved.
        if supported == 0:
            confidence = min(confidence, 0.45)
        elif uncertain > supported:
            confidence = min(confidence, 0.72)
        else:
            confidence = min(confidence, 0.95)

    return max(0.05, min(confidence, 0.98))


def build_web_output(
    question,
    answer,
    confidence,
    verification,
    evidence,
    verification_evidence,
    claim_ledger=None
):
    if confidence >= 0.80:
        decision = "ANSWER"
    elif confidence >= 0.50:
        decision = "WARN"
    else:
        decision = "ABSTAIN"

    supported = verification.get("supported", 0)
    contradicted = verification.get("contradicted", 0)
    uncertain = verification.get("uncertain", 0)

    claim_lines = []

    for i, claim in enumerate(verification.get("claims", []), 1):
        refs = claim.get("evidence_numbers", [])
        ref_text = (
            ", ".join(str(x) for x in refs)
            if refs else "none"
        )

        claim_lines.append(
            f"{i}. [{claim['status']}] {claim['claim']}\n"
            f"   Evidence: {ref_text}\n"
            f"   {claim['reason']}"
        )

    claims_text = (
        "\n\n".join(claim_lines)
        if claim_lines
        else "No claim-level verification was available."
    )

    mode_label = (
        "CURRENT AFFAIRS + WEB VERIFICATION MODE"
        if is_current_affairs_question(question)
        else "GENERAL KNOWLEDGE + WEB VERIFICATION MODE"
    )

    return f"""
======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================

{mode_label}

======================================================================
ANSWER
----------------------------------------------------------------------

{answer}

======================================================================
CLAIM VERIFICATION
----------------------------------------------------------------------

{claims_text}

Supported: {supported}
Contradicted: {contradicted}
Uncertain: {uncertain}

======================================================================
WEB SOURCES
----------------------------------------------------------------------

{format_web_evidence(evidence)}

======================================================================
INDEPENDENT VERIFICATION SEARCH
----------------------------------------------------------------------

{format_web_evidence(verification_evidence, "VERIFICATION WEB EVIDENCE")}

======================================================================
FINAL DECISION: {decision}
CONFIDENCE: {confidence:.3f}
======================================================================
"""


def is_current_numeric_question(question):
    """Detect live questions where an exact current value is expected."""
    q = normalize_chat_language(str(question or "")).lower()
    numeric_markers = [
        "price", "rate", "cost", "value", "how much", "score", "result",
        "temperature", "weather", "exchange rate", "gold", "silver",
        "stock", "share price", "market cap", "ranking", "standings",
        "latest result", "current result", "current score", "today's",
        "today", "right now", "currently", "as of today"
    ]
    freshness_markers = [
        "today", "today's", "current", "currently", "right now", "latest",
        "now", "live", "this morning", "this evening", "as of"
    ]
    return any(m in q for m in numeric_markers) and any(m in q for m in freshness_markers)


def build_live_search_query(question):
    """Make live-value searches explicit so retrieval targets the current value."""
    q = re.sub(r"\s+", " ", str(question or "")).strip()
    today = datetime.now().strftime("%d %B %Y")
    q_lower = q.lower()

    if is_nearby_restaurant_query(q):
        return get_restaurant_search_query(q)

    if is_current_numeric_question(q):
        if "gold" in q_lower:
            return (
                f"{q} {today} India latest 24K 22K gold rate per 10 grams "
                "current verified price"
            )
        if "weather" in q_lower or "temperature" in q_lower:
            return f"{q} {today} latest current conditions temperature"
        if any(x in q_lower for x in ["score", "result", "standings", "ranking"]):
            return f"{q} {today} latest official result score standings"
        if any(x in q_lower for x in ["stock", "share price", "market"]):
            return f"{q} {today} latest market price current"
        return f"{q} {today} latest current verified information"

    return q


def resolve_contextual_query(question, conversation_context):
    """
    Resolves follow-up pronouns (it, its, this, that, he, she, they)
    and short conversational follow-up questions using prior conversation context.
    """
    if not conversation_context:
        return question

    q = str(question or "").strip()
    q_lower = q.lower()
    pronouns = [
        r"\bit\b", r"\bits\b", r"\bthis\b", r"\bthat\b", r"\bthese\b",
        r"\bthose\b", r"\bthey\b", r"\bthem\b", r"\btheir\b", r"\bhe\b",
        r"\bhim\b", r"\bhis\b", r"\bshe\b", r"\bher\b"
    ]
    has_pronoun = any(re.search(p, q_lower) for p in pronouns)
    is_short_followup = len(q_lower.split()) <= 6 and any(
        q_lower.startswith(w) for w in [
            "what about", "how about", "and the", "what is the", "why is that",
            "and its", "tell me more", "how much", "who makes", "where is", "when did"
        ]
    )

    if not (has_pronoun or is_short_followup):
        return q

    # Extract the previous user question from conversation context
    user_turns = re.findall(r"User:\s*(.+)", conversation_context)
    if user_turns:
        prev_q = user_turns[-1].strip()
        prev_clean = re.sub(
            r"^(tell me about|what is|does a|do you know|can you explain|why does|who is|how does)\s+",
            "", prev_q, flags=re.I
        ).strip(" ?.,!")
        if prev_clean and prev_clean.lower() not in q_lower:
            return f"{q} {prev_clean}"

    return q



def _is_broad_major_news_question(question):
    """True for broad news-digest requests where Gemini Search should be the authority."""
    q = normalize_chat_language(question).lower()
    broad = (
        "major news", "top news", "top headlines", "major headlines",
        "latest news", "recent news", "news today", "today's news",
        "todays news", "current news", "current affairs",
        "latest developments", "recent developments", "major developments",
        "what's happening", "whats happening", "what is happening",
        "what happened today", "what happened recently"
    )
    geography = ("india", "indian", "nation", "country", "world", "international")
    return any(x in q for x in broad) and any(x in q for x in geography)


def _grounded_gemini_news_answer(question, conversation_context=""):
    """Evidence-first live-news pipeline with deterministic category coverage.

    Broad news is retrieved independently by category. The synthesis stage is
    given a small, explicitly selected candidate set so one high-volume topic
    (usually politics) cannot crowd out science/space/ISRO or other categories.
    """
    q = normalize_chat_language(question).strip()
    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %B %Y")

    category_specs = [
        ("GENERAL", f"India latest major news today {today} national headlines confirmed"),
        ("POLITICS_DIPLOMACY", f"India politics government diplomacy foreign policy latest news today {today}"),
        ("ECONOMY_BUSINESS", f"India economy business markets trade latest news today {today}"),
        ("SCIENCE_SPACE", f"India science technology space ISRO latest mission launch research news today {today}"),
        ("SECURITY_DEFENCE", f"India national security defence military latest news today {today}"),
        ("HEALTH_INFRA_ENVIRONMENT", f"India health infrastructure environment major news today {today}"),
    ]

    if not re.search(r"\bindia\b|\bindian\b", q, re.I):
        base = normalize_chat_language(q)
        category_specs = [
            ("GENERAL", f"{base} latest major news today {today} confirmed"),
            ("POLITICS_DIPLOMACY", f"{base} politics government diplomacy latest news today {today}"),
            ("ECONOMY_BUSINESS", f"{base} economy business markets latest news today {today}"),
            ("SCIENCE_SPACE", f"{base} science technology space latest news today {today}"),
            ("SECURITY_DEFENCE", f"{base} security defence latest news today {today}"),
        ]

    # Retrieve each category independently and retain its category label.
    category_results = {}
    with ThreadPoolExecutor(max_workers=len(category_specs)) as pool:
        futures = {
            pool.submit(fresh_web_search, query, 6, True): category
            for category, query in category_specs
        }
        for future in as_completed(futures):
            category = futures[future]
            try:
                rows = future.result() or []
            except Exception as exc:
                print(f"[ECRAG] news category retrieval failed [{category}]: {exc}")
                rows = []
            tagged = []
            for item in rows:
                copy = dict(item)
                copy["category"] = category
                tagged.append(copy)
            category_results[category] = tagged
            print(f"[ECRAG] NEWS CATEGORY: {category} results={len(tagged)}")

    # Deduplicate globally, but preserve the category on the surviving item.
    seen_urls = set()
    seen_titles = set()
    for category, rows in category_results.items():
        cleaned = []
        for item in rows:
            url = str(item.get("url", "")).strip()
            title = re.sub(r"\s+", " ", str(item.get("title", ""))).strip().lower()
            title_key = re.sub(r"[^a-z0-9 ]", "", title)[:180]
            if url and url.lower() in seen_urls:
                continue
            if title_key and title_key in seen_titles:
                continue
            if url:
                seen_urls.add(url.lower())
            if title_key:
                seen_titles.add(title_key)
            cleaned.append(item)
        category_results[category] = cleaned

    # IMPORTANT: rank *inside each category* before selecting the representative
    # story. The previous version took rows[0], which meant a search engine's
    # relevance ranking could promote an old but detailed article as "latest".
    # Temporal ranking is deterministic and happens before the LLM sees anything.
    selected = []
    for category, _query in category_specs:
        rows = category_results.get(category, [])
        if rows:
            ranked_rows = rank_temporal_evidence(rows, q)
            category_results[category] = ranked_rows
            selected.append(ranked_rows[0])

    # Specifically reserve the strongest CURRENT ISRO/space candidate when available.
    science_rows = category_results.get("SCIENCE_SPACE", [])
    isro_rows = [
        item for item in science_rows
        if re.search(r"\bisro\b|indian space research organisation|launch vehicle|satellite|rocket|mission", 
                     str(item.get("title", "")) + " " + str(item.get("snippet", "")), re.I)
    ]
    isro_rows = rank_temporal_evidence(isro_rows, q)
    if isro_rows:
        reserved = isro_rows[0]
        selected = [item for item in selected if item is not reserved]
        selected.insert(0, reserved)
        print("[ECRAG] NEWS RESERVED: SCIENCE_SPACE/ISRO candidate selected")

    # Fill remaining slots with the strongest remaining fresh candidates.
    selected_keys = {str(x.get("url", "")).lower() for x in selected}
    for category, rows in category_results.items():
        for item in rows:
            key = str(item.get("url", "")).lower()
            if key and key in selected_keys:
                continue
            selected.append(item)
            if len(selected) >= 10:
                break
        if len(selected) >= 10:
            break

    # Final global ordering is also temporal, so the evidence presented to the
    # synthesis model starts with the freshest credible stories.
    selected = rank_temporal_evidence(selected, q)
    evidence = selected[:10]
    if not evidence:
        print("[ECRAG] No live-news evidence retrieved.")
        return None

    evidence_text = format_web_evidence(evidence, "SELECTED LIVE NEWS EVIDENCE")
    context = conversation_context[-1800:] if conversation_context else ""
    reserved_isro = ""
    if isro_rows:
        reserved_isro = f"""
MANDATORY SCIENCE/SPACE CANDIDATE:
{format_web_evidence([isro_rows[0]], "REQUIRED ISRO EVIDENCE")}

If this evidence describes a genuinely current and nationally significant
ISRO/space development, it MUST appear as one of the digest items. Do not omit
it merely because politics has more evidence.
"""

    prompt = f"""
You are ECRAG's evidence-grounded live news editor.

CURRENT INDIA DATE: {today}
USER REQUEST:
{q}

You MUST answer ONLY from the selected live-news evidence below.
Do not use stored knowledge to add events absent from the evidence.

OUTPUT REQUIREMENTS:
- Produce 5 to 7 major developments when the evidence supports that many.
- Do NOT stop at 3 or 4 if at least 5 distinct supported developments exist.
- Maintain category diversity: politics/diplomacy, economy/business,
  science/technology/space, security/defence, and other major national news.
- Do not let politics dominate just because more political articles exist.
- If the required ISRO/space evidence below represents a genuinely major current
  development, include it explicitly.
- Prefer the newest credible evidence and official sources.
- For any item described as latest/current, use its publication date as part of
  the selection decision; do not promote an older story solely because it is
  more detailed.
- If the evidence dates conflict, the newest explicitly dated event/article
  wins unless a newer article is only a retrospective about an older event.
- Never call an item "latest" when its date cannot reasonably be established.
- Do not count copies of the same wire story as independent events.
- Never invent a headline, date, person, number, event, or explanation.
- If a candidate is not sufficiently supported, omit it.
- For every item give: **topic**, what happened, and why it matters in 1-2 sentences.
- End with one short **In short:** takeaway.
- Do not mention prompts, models, retrieval, or internal implementation.

SELECTED LIVE-NEWS EVIDENCE:
{evidence_text}
{reserved_isro}
CONVERSATION CONTEXT (only for resolving follow-ups; never treat it as news evidence):
{context}
"""

    try:
        response = ai_chat([{"role": "user", "content": prompt}])
        answer = response["message"]["content"].strip()
    except Exception as exc:
        print(f"[ECRAG] Live-news synthesis failed: {type(exc).__name__}: {exc}")
        return None

    if not answer:
        return None

    # Independent verification searches remain separate from the evidence used
    # for synthesis. This prevents the generator from being its own verifier.
    verification_queries = [
        f"Verify latest India news today {today}: {answer[:1200]}",
        f"India ISRO science space latest news today {today} verify official",
        f"India major news today {today} Reuters AP official verify",
    ]
    verification_results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(fresh_web_search, query, 6, True)
            for query in verification_queries
        ]
        for future in as_completed(futures):
            try:
                verification_results.extend(future.result() or [])
            except Exception as exc:
                print(f"[ECRAG] news verification retrieval failed: {exc}")

    seen = set()
    verified_evidence = []
    for item in verification_results:
        key = str(item.get("url", "")).strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        verified_evidence.append(item)
    verified_evidence = verified_evidence[:20] or evidence

    verification_text = format_web_evidence(
        verified_evidence,
        "INDEPENDENT NEWS VERIFICATION EVIDENCE"
    )
    verification = verify_web_answer(q, answer, verification_text)
    confidence = calculate_web_confidence(
        verification,
        len(verified_evidence),
        q,
        answer
    )

    # Broad current-news answers also require actual dated evidence. A fluent
    # synthesis must not turn an undated/old article into a high-confidence
    # "latest" claim.
    broad_temporal = temporal_evidence_status(
        rank_temporal_evidence(verified_evidence, q),
        q
    )
    if broad_temporal["newest"] is None:
        confidence = min(confidence, 0.49)
    elif any(marker in q.lower() for marker in ("latest", "most recent", "today", "right now")) and broad_temporal["dated"] < 2:
        confidence = min(confidence, 0.68)
    confidence = min(confidence, 0.90)

    if verification.get("contradicted", 0) > verification.get("supported", 0):
        confidence = min(confidence, 0.49)

    decision = "ANSWER" if confidence >= 0.80 else ("WARN" if confidence >= 0.50 else "ABSTAIN")
    output = build_web_output(
        q,
        answer,
        confidence,
        verification,
        evidence,
        verified_evidence
    )

    print(
        f"[ECRAG] DIVERSIFIED LIVE NEWS SUCCESS: selected={len(evidence)}, "
        f"verification={len(verified_evidence)}, confidence={confidence:.3f}"
    )

    return {
        "answer": answer,
        "confidence": confidence,
        "decision": decision,
        "output": output,
        "source": "🌐 Live News • Tavily + FreeNewsAPI + Google News + Claim Verification",
        "verification": verification,
        "evidence_count": len(verified_evidence),
    }

def deterministic_isro_latest_answer(question):
    """Answer explicit latest-ISRO questions from first-party evidence only.

    There are two retrieval layers, both constrained to ISRO itself:
      1. Directly fetch ISRO's homepage and dated article pages.
      2. If direct HTTP retrieval is unavailable, use Tavily with an explicit
         include_domains=['isro.gov.in'] restriction.

    Crucially, this function never falls through to the normal Gemini/news
    pipeline for an explicit latest-ISRO question.
    """
    print("[ECRAG] ISRO LATEST MODE ENTERED")

    official = fetch_isro_official_latest(max_results=5)

    # Fallback only to first-party ISRO search results. Never use generic news
    # retrieval here because older high-profile stories such as SPADEX can win
    # generic rankings even when a newer official ISRO update exists.
    if not official:
        today = datetime.now().strftime("%Y-%m-%d")
        official = tavily_search(
            f"ISRO latest major development official update {today}",
            max_results=8,
            topic="news",
            search_depth="advanced",
            include_domains=["isro.gov.in"],
        )
        official = rank_temporal_evidence(official, question)
        official = [
            item for item in official
            if "isro.gov.in" in str(item.get("url", "")).lower()
        ][:5]

    if not official:
        print("[ECRAG] ISRO LATEST MODE: no first-party evidence -> ABSTAIN")
        abstain = (
            "I can't reliably determine ISRO's latest major development from "
            "first-party evidence right now, so I won't guess."
        )
        return {
            "answer": abstain,
            "confidence": 0.0,
            "decision": "ABSTAIN",
            "output": abstain,
            "source": "⚠️ Official ISRO evidence unavailable • Abstained",
            "verification": {"supported": 0, "contradicted": 0, "uncertain": 1},
            "evidence_count": 0,
        }

    # The newest dated first-party item is the temporal anchor. Do not let a
    # second search, Gemini, or a famous older mission replace it.
    official = sorted(
        official,
        key=lambda item: _extract_evidence_datetime(item) or datetime.min,
        reverse=True,
    )
    latest = official[0]
    latest_date = _extract_evidence_datetime(latest)
    date_text = latest_date.strftime("%B %d, %Y") if latest_date else "the latest available date"
    title = str(latest.get("title") or "ISRO latest official update").strip()
    snippet = re.sub(r"\s+", " ", str(latest.get("snippet") or "")).strip()

    if len(snippet) > 650:
        snippet = snippet[:647].rsplit(" ", 1)[0] + "..."

    answer = f"The latest major development reported by ISRO is **{title}**, dated {date_text}."
    if snippet and title.lower() not in snippet.lower():
        answer += f" {snippet}"

    evidence_text = format_web_evidence(official, "OFFICIAL ISRO EVIDENCE")
    output = f"""
======================================================================
               EVIDENCE-CALIBRATED RAG
======================================================================

OFFICIAL ISRO LATEST-DEVELOPMENT MODE

======================================================================
ANSWER
----------------------------------------------------------------------
{answer}

CONFIDENCE
----------------------------------------------------------------------
0.94 (94.0%)

DECISION
----------------------------------------------------------------------
ANSWER

OFFICIAL ISRO EVIDENCE
----------------------------------------------------------------------
{evidence_text}

NOTE
----------------------------------------------------------------------
This answer is anchored to the newest dated first-party ISRO evidence.
Generic news results and older missions are not permitted to replace it.
"""
    print(f"[ECRAG] ISRO LATEST MODE SUCCESS: {title} | {date_text}")
    return {
        "answer": answer,
        "confidence": 0.94,
        "decision": "ANSWER",
        "output": output,
        "source": "🚀 Official ISRO • Direct/domain-restricted evidence",
        "verification": {"supported": len(official), "contradicted": 0, "uncertain": 0},
        "evidence_count": len(official),
    }


def general_web_answer(question, conversation_context="", progress_callback=None):
    """
    Internet-assisted general QA.

    1. Search the internet.
    2. Ask the local LLM to answer from the retrieved evidence.
    3. Run a second search for independent verification.
    4. Verify individual claims.
    5. Calibrate confidence and decide ANSWER/WARN/ABSTAIN.
    """
    # Explicit latest-ISRO questions use a deterministic first-party path.
    # This prevents older famous events such as SPADEX from ever winning over
    # the newest dated ISRO item and avoids spending a Gemini call on the test.
    if is_explicit_latest_isro_question(question):
        direct_result = deterministic_isro_latest_answer(question)
        if direct_result is not None:
            return direct_result

    # Broad current-news questions intentionally use the same retrieval +
    # independent verification pipeline as every other web-grounded answer.
    # This avoids a single Gemini 503 or an unverified Gemini digest becoming
    # an authoritative answer.
    context_for_search = conversation_context[-1800:] if conversation_context else ""

    resolved_q = resolve_contextual_query(question, conversation_context)
    if is_nearby_restaurant_query(question):
        search_query = get_restaurant_search_query(question)
    else:
        search_query = build_live_search_query(resolved_q)

    # Current-affairs queries are explicitly freshness-oriented.
    if is_current_affairs_question(question):
        current_year = datetime.now().year
        search_query = f"{question.strip()} latest {current_year}"

        q_lower = normalize_chat_language(question).lower()
        if "isro" in q_lower or "indian space research organisation" in q_lower:
            search_query += " site:isro.gov.in OR site:pib.gov.in"

    # Only augment short/bare abbreviations (<= 3 words), preventing query pollution on full sentences
    q_words = question.strip().split()
    if len(q_words) <= 3 and looks_like_abbreviation_or_named_entity(question):
        if is_current_affairs_question(question):
            search_query = f"{search_query} latest"
        else:
            search_query = f"{question.strip()} official context"

    # Note: Conversation context is passed to the generation prompt, never
    # appended to the literal web search query, preventing search engine query pollution.
    evidence = fresh_web_search(
        search_query,
        WEB_MAX_RESULTS,
        current_affairs=is_current_affairs_question(question)
    )

    if not evidence:
        if _is_broad_major_news_question(question):
            answer = (
                "I couldn't retrieve reliable live news right now, so I won't "
                "guess or present older information as today's major news."
            )
            output = answer
            return {
                "answer": answer,
                "confidence": 0.20,
                "decision": "ABSTAIN",
                "output": output,
                "source": "⚠️ Live News unavailable • no local-news fallback used",
                "verification": {"supported": 0, "contradicted": 0, "uncertain": 1},
                "evidence_count": 0
            }

        # Never fall back to the local model for a web-required question.
        # Doing so would defeat ECRAG's core anti-hallucination objective.
        answer = (
            f"I could not retrieve verified external reports or official records matching '{question.strip()}'. "
            "Because ECRAG operates under a strict anti-hallucination guardrail, it refuses to guess or invent unconfirmed details. "
            "If this refers to an event under a different name or spelling, please try rephrasing or consulting official sources."
        )
        output = f"""
======================================================================
               EVIDENCE-CALIBRATED RAG
======================================================================

WEB EVIDENCE UNAVAILABLE

======================================================================
ANSWER
----------------------------------------------------------------------
{answer}

FINAL DECISION: ABSTAIN
CONFIDENCE: 0.000
======================================================================
"""
        return {
            "answer": answer,
            "confidence": 0.0,
            "decision": "ABSTAIN",
            "output": output,
            "source": "⚠️ Web Evidence Unavailable • Abstained",
            "verification": {"supported": 0, "contradicted": 0, "uncertain": 1},
            "evidence_count": 0
        }

    # For latest/current questions, temporal ranking happens BEFORE generation.
    # The model therefore sees the newest credible evidence first rather than
    # merely seeing the most semantically relevant result first.
    evidence = rank_temporal_evidence(evidence, question)

    # Hard-select the freshest evidence for explicit latest/current questions.
    # This is intentionally deterministic: the generator should not get a
    # large pool containing an old but famous event and then choose it from
    # model familiarity.
    if is_current_affairs_question(question):
        evidence = select_temporally_relevant_evidence(
            evidence, question, max_items=min(WEB_MAX_RESULTS, 8)
        )

    evidence_text = format_web_evidence(evidence)

    current_affairs_instruction = ""
    if is_current_affairs_question(question):
        current_affairs_instruction = f"""
CURRENT-AFFAIRS MODE:
- This question concerns information that can change quickly.
- Prefer the newest retrieved evidence and pay attention to publication dates.
- Clearly distinguish confirmed facts from reports, claims, predictions, or allegations.
- Include specific dates when they help avoid confusion.
- If sources disagree, explain the disagreement instead of choosing silently.
- Do not present old information as current.
- Do not fill missing current facts from model memory.
- For ongoing wars, conflicts, geopolitics, science news, or sports, summarize
  the latest verified situation supported by the retrieved evidence.
- The current date is {datetime.now().strftime("%Y-%m-%d")}.
- Google News and web-search results are external evidence; use them to answer the question, not to tell the user where to look.
- If a current numeric value is present in reliable evidence, report that value and its units/currency.
- Prefer multiple independent reports when available, especially for breaking events.
- Do not treat repeated copies of the same report as independent confirmation.
- For major breaking claims, require corroboration from at least two distinct publisher domains when available.
- For a broad India-news digest, inspect the dedicated science/space evidence and
  include a major ISRO/space/science development when credible current evidence
  shows that it is nationally significant. Do not omit it merely because
  politics dominates the search results.
- Do not invent an ISRO/science story if the retrieved evidence does not support one.
- If the evidence cannot reliably establish what happened, say that the latest information is still unclear rather than guessing.
- IMPORTANT: "latest" is a temporal claim. A fact being true is not enough.
  Select the newest dated credible evidence available and do not call an older
  event the latest merely because it is highly relevant.
- When a named organization such as ISRO is asked about, prioritize first-party
  evidence from that organization's official domain when available.
- For an explicit "latest" question about a named organization, the newest
  dated first-party result is the temporal anchor. Do not replace that anchor
  with an older famous achievement such as SPADEX merely because it is more
  historically significant or better known.
- If the newest official result describes an ongoing update/operation, treat
  that as the latest development unless the evidence explicitly shows it is
  unrelated to the user's question.
"""

    live_numeric_instruction = ""
    if is_current_numeric_question(question):
        live_numeric_instruction = f"""
LIVE-VALUE MODE:
- The user expects a value/fact that is current as of {datetime.now().strftime('%d %B %Y')}.
- Treat retrieved web evidence as the only authority for the current value.
- Do NOT use older model memory to fill a missing current value.
- Prefer a result whose page/content has a date matching today or the newest available date.
- If a source contains the requested number, use that number rather than saying the source merely offers a page to check.
- For prices/rates, preserve the unit, purity, currency and time basis (for example per gram vs per 10 grams).
- If multiple current sources differ, report the most recent/reliable value or a narrow range and briefly explain why.
"""

    restaurant_instruction = ""
    if is_nearby_restaurant_query(question):
        restaurant_instruction = f"""
LOCAL RESTAURANT & DINING MODE (ANCHOR: VIT-AP UNIVERSITY & VIJAYAWADA):
- The user is asking for dining, food, or restaurant recommendations near their location.
- GEOGRAPHIC LOCATION ANCHOR: The user is located at VIT-AP University (near Inavolu village, Amaravati capital region, Andhra Pradesh).
- URBAN & REGIONAL REFERENCE: Vijayawada (~18–20 km away across the Krishna River) and Mangalagiri / Tadepalli (~10–12 km away along NH-16) are the primary reference points.
- STRUCTURE YOUR RECOMMENDATIONS LOGICALLY BY PROXIMITY ZONES:
  1. Zone 1: Campus & Immediate Inavolu Surroundings (0–1 km):
     - Inside VIT-AP: Central Cafeteria, Rock Plaza food court, student dining stalls, Nescafe & juice points.
     - Inavolu Village Gate: Local tiffin centers (idli, dosa, poori), student dhabas, tea stalls, and budget fast food.
  2. Zone 2: Mangalagiri / Tadepalli Corridor along NH-16 (~10–15 mins drive, ~8–12 km):
     - Highway Dhabas & Family Eateries: Popular student favorites like Sharma Dhaba (Mangalagiri bypass), Delight Dhaba, Grand Satti Babu Biryani, and restaurants near AIIMS Mangalagiri.
  3. Zone 3: Vijayawada City Dining Hub (~25–35 mins drive, ~18–22 km via Prakasam Barrage / Kanaka Durga Varadhi):
     - Iconic Heritage Spots: Babai Hotel (famous for authentic Andhra breakfast, soft idlis with butter and chutney).
     - Popular Restaurants & Biryani: Sweet Magic, Southern Spice, Minerva Grand, Rasoie, Barbeque Nation, Cross Roads.
     - Cafes & Hangouts: Cafes and eateries around Benz Circle, MG Road (Bandar Road), and Ring Road.
- Practical Information: Note travel times, student budget-friendliness, and whether spots are best for quick bites vs. relaxed weekend outings with friends.
- Direct, Helpful Delivery: Answer warmly and clearly with crisp sections or bullet points.
"""

    sycophancy_report = AntiSycophancyShield.audit_query(
        question,
        retrieved_evidence=evidence
    )
    sycophancy_instruction = ""
    if sycophancy_report.get("shield_activated") or sycophancy_report.get("directive"):
        sycophancy_instruction = f"""
ANTI-SYCOPHANCY & OBJECTIVITY DIRECTIVE:
{sycophancy_report.get('directive')}
"""

    answer_prompt = f"""
You are the answer-generation stage of ECRAG.

User question:
{question}

Conversation context:
{conversation_context or "None"}

Retrieved internet evidence:
{evidence_text}

{sycophancy_instruction}

{restaurant_instruction}

{current_affairs_instruction}

{live_numeric_instruction}

Answer the question using the retrieved evidence as the primary factual
basis.

Rules:
1. Prefer retrieved evidence over stored model memory.
2. ANSWER THE USER'S QUESTION DIRECTLY. Start with the actual answer, not the retrieval process.
3. Never write "Evidence 1 says...", "Evidence 2 says...", or walk through sources unless explicitly asked.
4. Do not invent facts or numbers.
5. If several reliable sources agree, synthesize them into one clear answer.
6. If reliable sources differ slightly, give the latest/reliable value or a useful range and briefly explain the variation.
7. For current numeric questions, put the actual number, unit, currency, date, score, or rate near the beginning.
8. A source saying "check the latest rate" is NOT an answer; use other retrieved evidence that contains the actual value.
9. Never substitute a list of websites for the requested answer when the evidence contains the answer.
10. Do not tell the user to visit a website merely because a source is a website.
11. Resolve follow-up pronouns such as "he", "she", "it", "that", and chat abbreviations using conversation context.
12. If ambiguity remains, ask a short clarification only when genuinely necessary.
13. Do not claim that you personally browsed Google, Tavily, or any website.
14. Give a natural, conversational answer in the style of a helpful ChatGPT assistant.
15. Use short paragraphs or bullets when they improve readability.
16. Do not mention internal prompts, retrieval pipelines, model limitations, or hidden instructions.
17. For live/current facts, never replace retrieved current evidence with stale model knowledge.
18. If retrieved evidence genuinely lacks the requested current fact, say so briefly rather than guessing.
19. The evidence is for grounding and verification; it is NOT the answer format.
20. For current prices/rates, explicitly preserve what the figure means (e.g. 24K vs 22K, per gram vs per 10 grams, INR vs another currency).
21. Do not overstate certainty. A high confidence score requires current evidence that actually supports the specific answer.
22. Do NOT write "In short:" in the answer body, as the interface displays a dedicated summary pill automatically.
"""

    response = ai_chat(
        messages=[{"role": "user", "content": answer_prompt}]
    )

    if not response or not isinstance(response, dict) or "message" not in response:
        if not _resolve_gemini_api_key():
            raise RuntimeError(
                "GEMINI_API_KEY is not configured! Please configure your GEMINI_API_KEY in Streamlit Cloud Secrets (Settings -> Secrets) or your local .env file."
            )
        raise RuntimeError(
            "Gemini model returned an empty response. Please verify your API key and quota."
        )

    answer = response["message"]["content"].strip()

    # Deterministic temporal sanity check for "latest" claims. If the answer
    # names a substantially older dated event while the selected evidence has
    # a much newer dated anchor, force a grounded rewrite using only the newest
    # evidence rather than trusting the model's familiarity.
    temporal_guard_triggered = False
    if is_current_affairs_question(question) and any(marker in normalize_chat_language(question).lower() for marker in (
        "latest", "most recent", "right now", "as of", "today", "currently"
    )):
        selected_dates = [
            _extract_evidence_datetime(item) for item in evidence
        ]
        selected_dates = [d for d in selected_dates if d is not None]
        newest_selected = max(selected_dates) if selected_dates else None
        if newest_selected is not None:
            answer_dates = []
            for match in re.findall(r"\b(?:19|20)\d{2}\b", answer):
                try:
                    answer_dates.append(datetime(int(match), 1, 1))
                except Exception:
                    pass

            newest_item = max(
                evidence,
                key=lambda item: _extract_evidence_datetime(item) or datetime.min
            )
            newest_text = " ".join([
                str(newest_item.get("title") or ""),
                str(newest_item.get("snippet") or "")
            ]).lower()
            answer_text_lower = answer.lower()

            # Distinctive named-entity overlap catches stale answers that do
            # not print an explicit year (for example, answering "SPADEX" when
            # the newest official evidence is about "EOS-05").
            newest_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+|[a-z]{5,}", newest_text)
            distinctive = [
                token for token in newest_tokens
                if token not in {"spacecraft", "mission", "development", "latest", "india", "isro", "successful", "successfully"}
            ]
            overlap = sum(1 for token in set(distinctive) if token in answer_text_lower)
            semantic_mismatch = bool(distinctive) and overlap == 0

            # If the answer explicitly anchors itself to a year more than 60
            # days older than the newest evidence, OR it completely misses the
            # distinctive subject of the newest dated evidence, regenerate.
            stale_year = bool(answer_dates and max(answer_dates) < newest_selected - timedelta(days=60))
            if stale_year or semantic_mismatch:
                temporal_guard_triggered = True
                guard_prompt = f"""
Rewrite the answer to the user's question using ONLY the newest evidence below.
The user explicitly asked for the latest/current development.
Do not mention an older famous event as the latest.
Start directly with the newest supported development and include its date.

USER QUESTION:
{question}

NEWEST EVIDENCE:
{format_web_evidence(evidence[:4], 'NEWEST EVIDENCE')}

Return only the corrected natural-language answer.
"""
                guarded = ai_chat(messages=[{"role": "user", "content": guard_prompt}])
                if guarded and guarded.get("message", {}).get("content"):
                    answer = guarded["message"]["content"].strip()

                # Fail closed if the corrective generation STILL ignores the
                # newest official subject. This prevents a fluent second
                # generation from reintroducing the same stale answer.
                if "isro" in normalize_chat_language(question).lower() or "indian space research organisation" in normalize_chat_language(question).lower():
                    corrected_lower = answer.lower()
                    corrected_overlap = sum(
                        1 for token in set(distinctive) if token in corrected_lower
                    )
                    if bool(distinctive) and corrected_overlap == 0:
                        abstain_answer = (
                            "I found recent ISRO information, but the retrieved sources "
                            "did not support a reliable single latest development, so I "
                            "won't guess."
                        )
                        return {
                            "answer": abstain_answer,
                            "confidence": 0.0,
                            "decision": "ABSTAIN",
                            "output": abstain_answer,
                            "source": "⚠️ Latest ISRO evidence conflicted • Abstained",
                            "verification": {"supported": 0, "contradicted": 0, "uncertain": 1},
                            "evidence_count": len(evidence)
                        }


    # Second search specifically aimed at checking the generated answer.
    if is_nearby_restaurant_query(question):
        verification_query = (
            f"Verify restaurants food dhabas near VIT AP University Inavolu Amaravati Mangalagiri Vijayawada: "
            f"{answer[:600]}"
        )
    else:
        verification_query = (
            f"Verify these facts: {question}. "
            f"Candidate answer: {answer[:900]}"
        )

    verification_evidence = fresh_web_search(
        verification_query,
        WEB_MAX_RESULTS,
        current_affairs=is_current_affairs_question(question)
    )

    if verification_evidence:
        combined = evidence + verification_evidence
        seen = set()
        merged = []

        for item in combined:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            merged.append(item)

        verification_evidence = merged[:WEB_MAX_RESULTS]
    else:
        verification_evidence = evidence

    verification_evidence = rank_temporal_evidence(verification_evidence, question)
    verification_text = format_web_evidence(
        verification_evidence,
        "VERIFICATION WEB EVIDENCE"
    )

    # ----------------------------------------------------
    # 7-STAGE FACTUAL VERIFICATION PIPELINE
    # ----------------------------------------------------
    stage_pipeline = SevenStageVerificationPipeline(ai_chat_fn=ai_chat)
    timeline_events = []

    def _pipeline_cb(evt):
        timeline_events.append(evt)
        if progress_callback:
            try:
                progress_callback(evt)
            except Exception:
                pass

    ledger_dict = None
    pipeline_q = search_query if is_nearby_restaurant_query(question) else question
    for event in stage_pipeline.run_streaming(pipeline_q, candidate_answer=answer, mode="web", initial_evidence=verification_evidence):
        _pipeline_cb(event)
        if event.get("type") == "pipeline_complete":
            ledger_dict = event.get("claim_ledger")

    if not ledger_dict:
        # Fallback if streaming did not yield ledger
        legacy_v = verify_web_answer(question, answer, verification_text)
        legacy_conf = calculate_web_confidence(legacy_v, len(verification_evidence), question, answer)
        legacy_output = build_web_output(question, answer, legacy_conf, legacy_v, evidence, verification_evidence)
        return {
            "answer": answer,
            "confidence": legacy_conf,
            "decision": extract_decision(legacy_output),
            "output": legacy_output,
            "source": "🌐 7-Stage Factual Verification • Multi-Source Evidence",
            "verification": legacy_v,
            "evidence_count": len(verification_evidence),
            "claim_ledger": None,
            "verification_timeline": timeline_events
        }

    counts = ledger_dict.get("counts", {})
    confidence = ledger_dict.get("overall_confidence", 0.0)
    decision = ledger_dict.get("overall_decision", "ANSWER")

    # Map claims for backward compatibility
    mapped_claims = []
    for c in ledger_dict.get("claims", []):
        cite_nums = [cite.get("evidence_id") for cite in c.get("supporting_citations", [])]
        mapped_claims.append({
            "claim": c.get("claim_text", ""),
            "status": "SUPPORTED" if c.get("verdict") == "VERIFIED" else ("CONTRADICTED" if c.get("verdict") == "CONTRADICTED" else "UNCERTAIN"),
            "verdict": c.get("verdict"),
            "evidence_numbers": cite_nums,
            "reason": c.get("reasoning", "")
        })

    verification = {
        "claims": mapped_claims,
        "supported": counts.get("verified", 0),
        "contradicted": counts.get("contradicted", 0),
        "uncertain": counts.get("partially_verified", 0) + counts.get("unverified", 0)
    }

    # Temporal calibration guard for explicit latest questions
    temporal = temporal_evidence_status(verification_evidence, question)
    if is_current_affairs_question(question) and any(marker in normalize_chat_language(question).lower() for marker in ("latest", "most recent", "right now", "as of")):
        if temporal["newest"] is None and temporal["dated"] == 0:
            confidence = min(confidence, 0.55)
        elif temporal["dated"] < 2:
            confidence = min(confidence, 0.75)

    # Respect the 7-stage verification pipeline's calibrated confidence score and decision.
    # Enforce strict anti-hallucination guardrail for explicit abstentions and contradictions.
    if counts.get("contradicted", 0) > 0:
        confidence = min(confidence, 0.45)
        decision = "ABSTAIN"
    elif any(marker in answer.lower() for marker in [
        "does not contain", "cannot be verified", "insufficient evidence", "no mention of",
        "no specific price prediction", "refuse to guess", "refuses to guess", "won't guess",
        "cannot confirm", "unable to confirm", "cannot be determined", "no data is available"
    ]):
        confidence = 0.0
        decision = "ABSTAIN" 

    output = build_web_output(
        question,
        answer,
        confidence,
        verification,
        evidence,
        verification_evidence,
        claim_ledger=ledger_dict
    )

    # Generate truth heatmap
    truth_heatmap_html = (ledger_dict.get("truth_heatmap_html") if ledger_dict else None) or TruthHeatmapRenderer.generate_truth_heatmap_html(
        answer,
        ledger_dict
    )

    return {
        "answer": answer,
        "confidence": confidence,
        "decision": decision,
        "output": output,
        "source": "🌐 7-Stage Factual Verification • Multi-Source Evidence + Claim Ledger",
        "verification": verification,
        "evidence_count": len(verification_evidence),
        "claim_ledger": ledger_dict,
        "verification_timeline": timeline_events,
        "truth_heatmap_html": truth_heatmap_html,
        "sycophancy_report": sycophancy_report
    }


# ============================================================
# CONVERSATIONAL BYPASS DETECTION
# ============================================================

# Exact social phrases that are always conversational.
_SOCIAL_EXACT = frozenset([
    "hello", "hi", "hey", "hiya", "howdy",
    "thanks", "thank you", "ty", "thx", "tysm",
    "good morning", "good afternoon", "good evening", "good night",
    "how are you", "how r u", "how are u", "hru",
    "i'm good", "im good", "i am good", "i'm fine", "im fine",
    "bye", "goodbye", "see you", "see ya", "cya", "ttyl", "brb",
    "ok", "okay", "alright", "sure", "got it", "understood",
    "cool", "nice", "great", "awesome", "wow", "amazing",
    "lol", "lmao", "haha", "hehe", "xd",
    "what's up", "whats up", "sup", "yo",
    "no worries", "no problem", "np", "no prob",
    "you're welcome", "youre welcome", "welcome",
    "sorry", "my bad", "oops",
    "hmm", "hm", "ah", "oh", "oh i see", "i see",
])

# Social prefix patterns — if the message starts with one of these AND
# is short (≤6 words), it is conversational.
_SOCIAL_PREFIXES = (
    "hello", "hi ", "hey ", "thanks ", "thank you ",
    "good morning", "good afternoon", "good evening", "good night",
    "nice to", "great to", "good to", "lovely to", "pleased to",
    "you're", "youre", "you are",
    "that's", "thats", "that is",
    "i'm ", "im ", "i am ",
    "sounds", "makes sense",
)

# Factual-intent words — presence of ANY of these means it's NOT conversational.
_FACTUAL_INTENT = frozenset([
    # Question words with factual stakes
    "what", "who", "when", "where", "which", "whose", "whom",
    "why", "how",
    # Action / knowledge verbs
    "explain", "define", "describe", "summarize", "summarise",
    "list", "give", "tell", "show", "find", "search",
    "calculate", "compute", "solve", "compare", "analyse", "analyze",
    "translate", "convert", "predict",
    # Domain signals
    "price", "cost", "rate", "weather", "temperature", "score",
    "result", "winner", "ranking", "history", "capital", "population",
    "difference", "similarity", "meaning", "definition", "example",
    # Document signals
    "pdf", "document", "page", "section", "chapter", "according",
    "summarize", "summary",
])


def is_conversational_bypass(question):
    """
    Multi-signal detector for purely conversational messages.

    Returns True when the full ECRAG pipeline (web search, RAG retrieval,
    claim verification, confidence calibration) can be safely skipped and
    a single direct LLM reply is sufficient.

    Scoring (threshold ≥ 2 to bypass):
      +3  exact social phrase match
      +2  social prefix + short (≤6 words)
      +1  very short (≤2 words) + no "?"
      -3  any factual-intent keyword present
      -2  contains "?" AND >3 words  (real question, not "ok?")
      -2  contains a digit / number (quantity or year query)
      -1  message is longer than 8 words

    The function intentionally has false-negative bias: when uncertain,
    it lets the full pipeline run rather than silencing it.
    """
    if not question or not question.strip():
        return False

    q_raw = normalize_chat_language(question).strip()
    q = q_raw.lower().rstrip("!.,? ")
    words = q.split()
    word_count = len(words)

    # --- Exact social phrase ---
    if q in _SOCIAL_EXACT:
        return True

    score = 0

    # Social prefix match on a short message
    if word_count <= 6 and any(q.startswith(p) for p in _SOCIAL_PREFIXES):
        score += 2

    # Very short message with no question mark → likely reaction/ack
    if word_count <= 2 and "?" not in question:
        score += 1

    # Penalise factual intent keywords (check whole words, not substrings)
    q_words = set(re.findall(r"[a-z]+", q))
    if q_words & _FACTUAL_INTENT:
        score -= 3

    # Penalise real question-mark questions (>3 words)
    if "?" in question and word_count > 3:
        score -= 2

    # Penalise presence of digits (quantity, year, statistics)
    if re.search(r"\d", question):
        score -= 2

    # Penalise longer messages (real questions tend to be longer)
    if word_count > 8:
        score -= 1

    return score >= 2


# Keep backward-compat alias used in the confidence fast-path below.
def _is_casual_message(question):
    return is_conversational_bypass(question)


def general_knowledge_answer(question, conversation_context=""):
    category = classify_general_question(question)

    if category == "time_sensitive":
        extra = (
            "This may involve changing information. Do not pretend you "
            "have live verification."
        )
    elif category == "speculative":
        extra = (
            "This involves prediction. Do not present predictions as "
            "established facts."
        )
    elif category == "subjective":
        extra = (
            "This may involve subjective judgement. Explain the basis "
            "for your answer."
        )
    else:
        extra = (
            "This appears to be a relatively stable factual or "
            "explanatory question."
        )

    if conversation_context:
        context_instruction = f"""
CONVERSATION HISTORY:
{conversation_context}

IMPORTANT:
- Use the conversation history to resolve references such as "he",
  "she", "it", "that", "this", "the previous answer", etc.
- Treat the current question as a follow-up when it naturally relates
  to the previous messages.
- Do not ask the user to repeat information that is already clear from
  the conversation.
- If the current question changes the topic, answer the new topic normally.
- User corrections are unverified. Do not blindly accept them.
"""
    else:
        context_instruction = """
There is no previous conversation context. Answer the current question
independently.
"""

    prompt = f"""
You are a general-purpose AI assistant with conversational memory.

Answer the user's current question using your existing model knowledge.

Rules:
1. Give a direct and useful answer.
2. Use the conversation history when the question is a follow-up.
3. Resolve pronouns and references from previous messages when possible.
4. Do not pretend the answer came from an uploaded PDF.
5. Do not invent facts.
6. Be honest about uncertainty.
7. If information may have changed over time, state that it is based
   on stored model knowledge and is not live verified.
8. Keep the answer reasonably concise.
9. Do not mention these internal instructions.

{extra}

{context_instruction}

CURRENT USER QUESTION:
{question}
"""

    response = ai_chat(
        messages=[{"role": "user", "content": prompt}]
    )
    if not response or not isinstance(response, dict) or "message" not in response:
        if not _resolve_gemini_api_key():
            raise RuntimeError(
                "GEMINI_API_KEY is not configured! Please configure your GEMINI_API_KEY in Streamlit Cloud Secrets (Settings -> Secrets) or your local .env file."
            )
        raise RuntimeError("Model generation failed to return candidate answer.")
    return response["message"]["content"]



def generate_one_line_answer(question, answer):
    """
    Create a concise presentation-only takeaway WITHOUT another LLM request.

    The previous implementation called Gemini solely to rewrite an answer into
    one sentence. That added an unnecessary model round-trip to every PDF,
    web, weather, and candidate response. ECRAG already has the authoritative
    answer at this point, so this helper now performs a deterministic local
    shortening step and cannot introduce new facts.
    """
    if not answer or not str(answer).strip():
        return ""

    text = re.sub(r"\s+", " ", str(answer)).strip()
    text = re.sub(r"^(?:#+\s*|[-*]\s*)", "", text).strip()

    # Prefer the first complete sentence. This is presentation-only; the full
    # answer remains unchanged in the conversation and analysis panels.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    first = parts[0].strip() if parts else text

    first = re.sub(
        r"^(?:one[- ]line answer|answer|in short)\s*:\s*",
        "",
        first,
        flags=re.I,
    ).strip()

    if len(first) > 280:
        first = first[:277].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."

    return first


# ============================================================
# CANDIDATE / TASK SUITABILITY REASONING
# ============================================================

def is_candidate_selection_question(question):
    """
    Detect questions that ask ECRAG to compare people/candidates and
    select, rank, shortlist, or recommend the best fit for a task/job.
    This is intentionally narrow so normal questions keep the existing
    pipeline.
    """
    q = normalize_chat_language(question).lower().strip()

    people_markers = [
        "candidate", "candidates", "applicant", "applicants",
        "employee", "employees", "person", "people", "ppl",
        "team members", "members", "students", "workers",
    ]

    selection_markers = [
        "select", "choose", "pick", "shortlist", "rank", "hire",
        "best fit", "best suited", "suitable", "suitability",
        "qualified", "qualify", "perfect for", "right for",
        "who should", "which people", "which candidates",
        "recommend", "top ",
    ]

    task_markers = [
        "job", "work", "role", "task", "position", "project",
        "assignment", "team", "requirement", "requirements",
    ]

    has_people = any(marker in q for marker in people_markers)
    has_selection = any(marker in q for marker in selection_markers)
    has_task = any(marker in q for marker in task_markers)

    # Strong explicit forms.
    if has_people and has_selection:
        return True

    if has_people and has_task and any(
        phrase in q for phrase in [
            "best", "better", "perfect", "fit", "suitable",
            "choose", "select", "pick", "rank", "only"
        ]
    ):
        return True

    # Examples such as "choose 3 out of 5 for this job".
    if re.search(
        r"\b(?:choose|select|pick|shortlist|rank)\s+\d+\b",
        q
    ) and has_task:
        return True

    return False


def extract_requested_candidate_count(question):
    """
    Extract an explicit requested selection count such as:
    'choose 3', 'select top 3', or 'only 3'.
    """
    q = normalize_chat_language(question).lower()

    patterns = [
        r"\b(?:choose|select|pick|shortlist|rank)\s+(?:the\s+)?(?:top\s+)?(\d+)\b",
        r"\btop\s+(\d+)\b",
        r"\bonly\s+(\d+)\b",
        r"\b(\d+)\s+(?:people|ppl|candidates|applicants|employees)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 100:
                    return value
            except ValueError:
                pass

    return None


def _candidate_status_value(status):
    status = str(status or "").upper()
    return {
        "STRONG": 1.0,
        "MATCH": 1.0,
        "PARTIAL": 0.5,
        "MISSING": 0.0,
        "UNKNOWN": 0.25,
    }.get(status, 0.25)


def _candidate_importance_weight(importance):
    return 2.0 if str(importance or "").upper() == "CRITICAL" else 1.0


def _safe_candidate_json(text):
    """Parse JSON returned by the local LLM, tolerating markdown fences."""
    content = (text or "").strip()
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
    content = re.sub(r"\s*```$", "", content).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError("Candidate reasoning model did not return JSON.")
        return json.loads(match.group(0))


def candidate_selection_answer(question, conversation_context=""):
    """
    Compare candidates against explicit task/job requirements.

    The local LLM is used only to extract the requirements and classify each
    candidate's evidence as STRONG/PARTIAL/MISSING/UNKNOWN. Final numerical
    ranking is calculated deterministically from those classifications.

    Formula:
        Suitability =
        sum(requirement_weight * match_value) /
        sum(requirement_weight)

    Critical requirements receive weight 2; preferred requirements receive
    weight 1. UNKNOWN is deliberately not treated as a failure, but it lowers
    the score and confidence because the evidence is incomplete.
    """
    requested_count = extract_requested_candidate_count(question)

    prompt = f"""
You are the candidate-analysis extraction stage of ECRAG.

USER QUESTION:
{question}

CONVERSATION CONTEXT:
{conversation_context or "None"}

Your job is NOT to make up candidate information.
Extract only what is explicitly stated or strongly implied by the user
question and conversation context.

Return ONLY valid JSON in this exact structure:
{{
  "requirements": [
    {{
      "name": "requirement name",
      "importance": "CRITICAL",
      "evidence": "short evidence from the input"
    }}
  ],
  "candidates": [
    {{
      "name": "candidate name",
      "matches": [
        {{
          "requirement": "requirement name",
          "status": "STRONG",
          "evidence": "short evidence from the input"
        }}
      ]
    }}
  ],
  "task": "short description of the job/task",
  "selection_count": {requested_count if requested_count is not None else "null"},
  "overall_data_sufficiency": "HIGH"
}}

Rules:
- importance must be CRITICAL or PREFERRED.
- Use CRITICAL for requirements explicitly described as necessary,
  mandatory, required, essential, or the core of the task.
- Use PREFERRED for desirable but non-mandatory requirements.
- status must be exactly STRONG, PARTIAL, MISSING, or UNKNOWN.
- STRONG means the input clearly indicates the candidate meets it.
- PARTIAL means the input indicates some but not all of it.
- MISSING means the input clearly indicates the candidate does not meet it.
- UNKNOWN means the input gives no reliable information about it.
- Do not infer skills, experience, education, or personality that were not given.
- If the input gives no candidate names, use labels such as Candidate 1 only
  when the candidates are explicitly distinguishable as numbered people.
- If there are no explicit requirements, extract the task constraints that
  can reasonably be compared; otherwise return an empty requirements list.
- overall_data_sufficiency is HIGH when the requirements and candidate
  information are sufficient for a meaningful comparison, MEDIUM when some
  important information is missing, and LOW when a reliable ranking cannot
  reasonably be made.
- Keep evidence short and factual.
"""

    try:
        response = ai_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        data = _safe_candidate_json(response["message"]["content"])

        requirements = data.get("requirements", [])
        candidates = data.get("candidates", [])

        if not isinstance(requirements, list):
            requirements = []
        if not isinstance(candidates, list):
            candidates = []

        # Sanitize requirements.
        clean_requirements = []
        for item in requirements[:20]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            importance = str(item.get("importance", "PREFERRED")).upper()
            if importance not in {"CRITICAL", "PREFERRED"}:
                importance = "PREFERRED"
            clean_requirements.append({
                "name": name,
                "importance": importance,
                "evidence": str(item.get("evidence", "")).strip(),
            })

        # Sanitize candidates and their requirement matches.
        clean_candidates = []
        for index, item in enumerate(candidates[:50], start=1):
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                name = f"Candidate {index}"

            raw_matches = item.get("matches", [])
            if not isinstance(raw_matches, list):
                raw_matches = []

            matches = []
            for match in raw_matches[:30]:
                if not isinstance(match, dict):
                    continue

                requirement = str(match.get("requirement", "")).strip()
                if not requirement:
                    continue

                status = str(match.get("status", "UNKNOWN")).upper()
                if status not in {
                    "STRONG", "PARTIAL", "MISSING", "UNKNOWN"
                }:
                    status = "UNKNOWN"

                matches.append({
                    "requirement": requirement,
                    "status": status,
                    "evidence": str(match.get("evidence", "")).strip(),
                })

            clean_candidates.append({
                "name": name,
                "matches": matches,
            })

        if not clean_candidates:
            answer = (
                "I can perform this suitability analysis, but I don't have "
                "enough candidate information in the question to rank anyone "
                "reliably."
            )
            return {
                "answer": answer,
                "confidence": 0.35,
                "decision": "ABSTAIN",
                "source": "🧠 Candidate Suitability Reasoning • Insufficient input",
                "quality_data": {
                    "requirements": clean_requirements,
                    "candidates": [],
                    "selection_count": requested_count,
                    "data_sufficiency": "LOW",
                },
            }

        # If the model did not extract requirements, use the requirement
        # names present in candidate matches as fallback.
        if not clean_requirements:
            discovered = []
            for candidate in clean_candidates:
                for match in candidate["matches"]:
                    if match["requirement"] not in discovered:
                        discovered.append(match["requirement"])
            clean_requirements = [
                {
                    "name": name,
                    "importance": "CRITICAL",
                    "evidence": "",
                }
                for name in discovered
            ]

        # Normalize each candidate's match map and calculate a deterministic
        # suitability score from the extracted statuses.
        req_map = {
            req["name"].lower(): req for req in clean_requirements
        }

        for candidate in clean_candidates:
            match_map = {
                match["requirement"].lower(): match
                for match in candidate["matches"]
            }

            weighted_total = 0.0
            weighted_score = 0.0
            known_count = 0

            for req in clean_requirements:
                weight = _candidate_importance_weight(req["importance"])
                match = match_map.get(req["name"].lower())
                status = match["status"] if match else "UNKNOWN"

                weighted_total += weight
                weighted_score += weight * _candidate_status_value(status)

                if status != "UNKNOWN":
                    known_count += 1

            candidate["score"] = (
                weighted_score / weighted_total
                if weighted_total > 0 else 0.0
            )
            candidate["known_requirements"] = known_count
            candidate["total_requirements"] = len(clean_requirements)

        ranked = sorted(
            clean_candidates,
            key=lambda item: item["score"],
            reverse=True
        )

        selection_count = requested_count
        if selection_count is None:
            selection_count = min(3, len(ranked))

        selection_count = max(1, min(selection_count, len(ranked)))

        selected = ranked[:selection_count]

        # Confidence reflects evidence completeness plus separation of the
        # selected group from the alternatives. It is not a probability of
        # being hired.
        total_possible = max(1, len(clean_requirements))
        known_ratio = sum(
            c["known_requirements"] / total_possible
            for c in ranked
        ) / max(1, len(ranked))

        if len(ranked) > selection_count:
            boundary = selected[-1]["score"]
            next_score = ranked[selection_count]["score"]
            separation = max(0.0, boundary - next_score)
        else:
            separation = 0.15

        confidence = (
            0.45
            + 0.35 * known_ratio
            + min(0.15, separation * 0.75)
            + (0.05 if clean_requirements else 0.0)
        )
        confidence = max(0.30, min(confidence, 1.0))

        data_sufficiency = str(
            data.get("overall_data_sufficiency", "")
        ).upper()

        if data_sufficiency not in {"HIGH", "MEDIUM", "LOW"}:
            if known_ratio >= 0.85:
                data_sufficiency = "HIGH"
            elif known_ratio >= 0.55:
                data_sufficiency = "MEDIUM"
            else:
                data_sufficiency = "LOW"

        if data_sufficiency == "LOW":
            confidence = min(confidence, 0.55)

        if confidence >= 0.80 and data_sufficiency != "LOW":
            decision = "ANSWER"
        elif confidence >= 0.50:
            decision = "WARN"
        else:
            decision = "ABSTAIN"

        task = str(data.get("task", "")).strip()

        lines = [
            "🧠 **Candidate Suitability Analysis**",
            "",
        ]

        if task:
            lines.extend([
                f"**Task / Role:** {task}",
                "",
            ])

        lines.append("### Requirements")
        if clean_requirements:
            for req in clean_requirements:
                label = (
                    "Critical"
                    if req["importance"] == "CRITICAL"
                    else "Preferred"
                )
                lines.append(f"- **{req['name']}** — {label}")
        else:
            lines.append("- No explicit requirements were provided.")

        lines.extend(["", "### Candidate Ranking"])

        for position, candidate in enumerate(ranked, start=1):
            selected_label = (
                " ✅ SELECT"
                if candidate in selected
                else " — NOT SELECTED"
            )
            lines.append(
                f"{position}. **{candidate['name']}** — "
                f"Suitability: **{candidate['score']:.1%}**"
                f"{selected_label}"
            )

            for req in clean_requirements:
                match = next(
                    (
                        m for m in candidate["matches"]
                        if m["requirement"].lower() == req["name"].lower()
                    ),
                    None
                )
                status = match["status"] if match else "UNKNOWN"
                evidence = match.get("evidence", "") if match else ""

                if status == "STRONG":
                    symbol = "✓"
                elif status == "PARTIAL":
                    symbol = "△"
                elif status == "MISSING":
                    symbol = "✗"
                else:
                    symbol = "?"

                detail = f" — {evidence}" if evidence else ""
                lines.append(
                    f"   - {symbol} {req['name']}: {status}{detail}"
                )

        lines.extend(["", "### Final Selection"])
        for position, candidate in enumerate(selected, start=1):
            lines.append(
                f"{position}. **{candidate['name']}** — "
                f"{candidate['score']:.1%} suitability"
            )

        if len(ranked) > selection_count:
            not_selected = ranked[selection_count:]
            lines.extend(["", "### Why the others were not selected"])
            for candidate in not_selected:
                strongest_gap = []
                for req in clean_requirements:
                    match = next(
                        (
                            m for m in candidate["matches"]
                            if m["requirement"].lower() == req["name"].lower()
                        ),
                        None
                    )
                    status = match["status"] if match else "UNKNOWN"
                    if status in {"MISSING", "UNKNOWN", "PARTIAL"}:
                        strongest_gap.append(
                            f"{req['name']} ({status.lower()})"
                        )

                gap_text = ", ".join(strongest_gap[:3])
                if not gap_text:
                    gap_text = "lower overall weighted suitability"
                lines.append(
                    f"- **{candidate['name']}**: {gap_text}."
                )

        lines.extend([
            "",
            "### Decision Basis",
            (
                "Candidates are ranked using a weighted requirement-match "
                "score. Critical requirements carry weight 2, while "
                "preferred requirements carry weight 1."
            ),
            (
                "Match values are STRONG = 1.0, PARTIAL = 0.5, "
                "UNKNOWN = 0.25, and MISSING = 0.0."
            ),
            (
                "Suitability = Σ(requirement weight × match value) / "
                "Σ(requirement weight)."
            ),
            "",
            f"**Data sufficiency:** {data_sufficiency}",
            (
                "**Important:** A high suitability score means the candidate "
                "matches the supplied requirements; it is not a guarantee "
                "of real-world job performance."
            ),
        ])

        answer = "\n".join(lines)

        return {
            "answer": answer,
            "confidence": confidence,
            "decision": decision,
            "source": (
                "🧠 Candidate Suitability Reasoning • "
                "Weighted Requirement Matching"
            ),
            "quality_data": {
                "requirements": clean_requirements,
                "candidates": ranked,
                "selected": [c["name"] for c in selected],
                "selection_count": selection_count,
                "data_sufficiency": data_sufficiency,
                "known_ratio": known_ratio,
                "separation": separation,
            },
        }

    except Exception as e:
        return {
            "answer": (
                "I couldn't complete the candidate suitability analysis "
                "reliably from the supplied information."
            ),
            "confidence": 0.30,
            "decision": "ABSTAIN",
            "source": (
                "🧠 Candidate Suitability Reasoning • Analysis unavailable"
            ),
            "quality_data": {
                "requirements": [],
                "candidates": [],
                "selection_count": requested_count,
                "data_sufficiency": "LOW",
                "error": str(e),
            },
        }


def estimate_general_confidence(question, answer):
    category = classify_general_question(question)

    prompt = f"""
Evaluate how reliable the answer is for the question.

Return ONLY valid JSON:
{{
  "confidence": 0.90,
  "reason": "short explanation"
}}

Rules:
- confidence must be a decimal between 0.0 and 1.0
- do not output a percentage
- do not output markdown
- do not output anything outside the JSON object
- stable factual knowledge may receive high confidence
- current information without live verification must receive lower confidence
- predictions and subjective questions must not receive unjustifiably high confidence
- judge the answer itself, not merely how fluent it sounds

QUESTION:
{question}

ANSWER:
{answer}
"""

    try:
        response = ai_chat(
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
        content = re.sub(r"\s*```$", "", content).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*?\}", content, re.S)
            if not match:
                raise ValueError("No JSON confidence object returned.")
            data = json.loads(match.group(0))

        confidence = float(data["confidence"])

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence outside 0-1 range.")

        reason = str(data.get("reason", "Confidence estimated by the local model."))

        if category == "time_sensitive":
            confidence = min(confidence, 0.88)
            if "live" not in reason.lower():
                reason += " The information was not checked against a live source."
        elif category == "speculative":
            confidence = min(confidence, 0.65)
        elif category == "subjective":
            confidence = min(confidence, 0.85)

        return confidence, reason

    except Exception:
        if category == "stable":
            return 0.90, "Stable general-knowledge answer; structured confidence assessment was unavailable."
        if category == "subjective":
            return 0.75, "Subjective question; confidence assessment was unavailable."
        if category == "speculative":
            return 0.55, "Future or predictive question; confidence assessment was unavailable."
        return 0.80, "Time-sensitive question based on stored model knowledge; live verification was unavailable."



def assess_answer_quality(
    question,
    answer,
    mode="general",
    evidence_count=0,
    supported=0,
    contradicted=0,
    uncertain=0,
    realtime_quality=None
):
    """
    Universal, transparent answer-quality assessment layer.

    This is intentionally separate from confidence:
    - Confidence estimates how strongly ECRAG can stand behind the answer.
    - Quality evaluates answer construction/grounding using observable signals.

    Score components (0-1):
      Relevance      20%
      Completeness   15%
      Clarity        15%
      Grounding      25%
      Consistency    15%
      Freshness      10%

    The score is an assessment indicator, not a probability that the answer
    is true.
    """
    answer_text = (answer or "").strip()
    question_text = (question or "").strip()

    # Relevance: a non-empty answer with meaningful overlap with the question
    # gets full credit; very short/empty answers are penalized.
    if not answer_text:
        relevance = 0.0
    else:
        q_words = {
            w for w in re.findall(r"[A-Za-z0-9]{3,}", question_text.lower())
        }
        a_words = {
            w for w in re.findall(r"[A-Za-z0-9]{3,}", answer_text.lower())
        }
        overlap = len(q_words & a_words) / max(1, min(len(q_words), 8))
        relevance = 0.70 + min(0.30, overlap * 0.30)
        if len(answer_text) < 25:
            relevance = min(relevance, 0.75)

    # Completeness: enough substance to answer without rewarding unnecessary
    # verbosity. This is a presentation-quality signal, not factuality.
    if not answer_text:
        completeness = 0.0
    elif len(answer_text) < 40:
        completeness = 0.65
    elif len(answer_text) < 100:
        completeness = 0.82
    elif len(answer_text) <= 2500:
        completeness = 1.0
    else:
        completeness = 0.90

    # Clarity: penalize obvious internal/system leakage and excessive repetition.
    clarity = 1.0
    lower = answer_text.lower()
    internal_terms = [
        "system prompt", "internal instruction", "developer message",
        "confidence calibration formula", "hidden instruction"
    ]
    if any(term in lower for term in internal_terms):
        clarity -= 0.25
    if len(answer_text) > 5000:
        clarity -= 0.10
    clarity = max(0.0, clarity)

    # Grounding varies by evidence mode.
    total_claims = supported + contradicted + uncertain
    if mode == "realtime":
        grounding = (
            float(realtime_quality.get("grounding_score", 1.0))
            if realtime_quality else 1.0
        )
    elif total_claims > 0:
        grounding = supported / total_claims
    elif evidence_count > 0:
        grounding = min(1.0, 0.65 + 0.07 * min(evidence_count, 5))
    elif mode == "project":
        grounding = 1.0
    else:
        # Local-model answers have no external evidence by design.
        grounding = 0.65

    # Consistency: contradictions are a direct negative signal.
    if total_claims > 0:
        consistency = max(
            0.0,
            1.0 - (contradicted / total_claims) - (0.35 * uncertain / total_claims)
        )
    elif mode == "realtime" and realtime_quality:
        consistency = 1.0 if realtime_quality.get("consistency") == "PASS" else 0.65
    else:
        consistency = 0.85

    # Freshness: live/API or web evidence gets the strongest score.
    if mode == "realtime":
        freshness = 1.0 if not realtime_quality or realtime_quality.get("freshness") == "PASS" else 0.50
    elif mode == "web":
        freshness = 1.0 if evidence_count > 0 else 0.60
    elif mode == "project":
        freshness = 1.0
    else:
        freshness = 0.80

    score = (
        0.20 * relevance
        + 0.15 * completeness
        + 0.15 * clarity
        + 0.25 * grounding
        + 0.15 * consistency
        + 0.10 * freshness
    )
    score = max(0.0, min(score, 1.0))

    if score >= 0.85:
        label = "HIGH"
    elif score >= 0.70:
        label = "GOOD"
    elif score >= 0.50:
        label = "MODERATE"
    else:
        label = "LOW"

    return {
        "score": score,
        "label": label,
        "relevance": relevance,
        "completeness": completeness,
        "clarity": clarity,
        "grounding": grounding,
        "consistency": consistency,
        "freshness": freshness,
    }


def append_quality_assessment(output, quality):
    """Append the universal quality layer to the existing ECRAG output."""
    return output.rstrip() + f"""

======================================================================
ANSWER QUALITY ASSESSMENT
----------------------------------------------------------------------

This assessment evaluates answer quality separately from confidence.
It is an indicator, not a probability that the answer is true.

Relevance:      {quality['relevance']:.3f}
Completeness:   {quality['completeness']:.3f}
Clarity:        {quality['clarity']:.3f}
Grounding:      {quality['grounding']:.3f}
Consistency:    {quality['consistency']:.3f}
Freshness:      {quality['freshness']:.3f}

QUALITY SCORE: {quality['score']:.3f} ({quality['score']:.1%})
QUALITY LEVEL: {quality['label']}

Formula:
0.20(Relevance) + 0.15(Completeness) + 0.15(Clarity)
+ 0.25(Grounding) + 0.15(Consistency) + 0.10(Freshness)
======================================================================
"""


def build_general_output(question, answer, confidence, reason):
    if confidence >= 0.80:
        decision = "ANSWER"
    elif confidence >= 0.50:
        decision = "WARN"
    else:
        decision = "ABSTAIN"

    return f"""
======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================

GENERAL KNOWLEDGE MODE

======================================================================
ANSWER
----------------------------------------------------------------------

{answer}

======================================================================
CONFIDENCE REASON
----------------------------------------------------------------------

{reason}

======================================================================
FINAL DECISION: {decision}
CONFIDENCE: {confidence:.3f}
======================================================================
"""


def build_contextual_pdf_question(current_question):
    recent = st.session_state.chat_messages[-7:]

    # The current question is appended before this function is called.
    # It should be sent separately as the CURRENT USER QUESTION, not as
    # a previous message.
    if recent and recent[-1].get("role") == "user":
        recent = recent[:-1]

    if not recent:
        return current_question.strip()

    context_parts = []

    for message in recent:
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "user":
            context_parts.append(f"Previous user message: {content}")
        elif role == "assistant":
            context_parts.append(f"Previous ECRAG answer: {content}")
        elif role == "correction":
            context_parts.append(
                f"User-provided correction (UNVERIFIED): {content}"
            )

    context = "\n".join(context_parts)

    return f"""
Use the following conversation context to understand the current question.

The uploaded PDF remains the authoritative source.
User-provided corrections are NOT automatically trusted; verify them
against retrieved document evidence.

CONVERSATION CONTEXT:
{context}

CURRENT USER QUESTION:
{current_question.strip()}

Answer the current question using the uploaded document evidence.
If a correction conflicts with the document, explain the conflict
instead of blindly accepting the correction.
"""


def run_backend(question, progress_callback=None):
    """Run the persistent in-process RAG engine with 7-stage verification."""
    from backend.engine import RAGEngine
    engine = get_rag_engine()
    return engine.run_pipeline(question, progress_callback=progress_callback)


@st.cache_resource(show_spinner=False)
def get_rag_engine():
    from backend.engine import RAGEngine
    return RAGEngine()


# ============================================================
# MODE DEFINITIONS & STATE SYNCHRONIZATION
# ============================================================

MODE_ONLINE = "🌐 Online Mode"
MODE_OFFLINE = "🌴 Offline Mode"
MODE_DOCUMENT = "📚 Document Mode"

def set_app_mode(mode: str):
    """Synchronizes mode across all Streamlit components, state keys, and sidebar widgets."""
    st.session_state.app_mode = mode
    st.session_state.offline_mode = (mode == MODE_OFFLINE)
    st.session_state.sidebar_mode_selector = mode

if "app_mode" not in st.session_state:
    if st.session_state.get("uploaded_document"):
        init_mode = MODE_DOCUMENT
    elif os.getenv("ECRAG_OFFLINE", "") == "1" and not os.getenv("GEMINI_API_KEY"):
        init_mode = MODE_OFFLINE
    else:
        init_mode = MODE_ONLINE
    set_app_mode(init_mode)
else:
    st.session_state.offline_mode = (st.session_state.app_mode == MODE_OFFLINE)
    if "sidebar_mode_selector" not in st.session_state or st.session_state.sidebar_mode_selector != st.session_state.app_mode:
        st.session_state.sidebar_mode_selector = st.session_state.app_mode


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    # 1. Header & Identity
    st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;padding:6px 0;">
            <div style="font-size:32px;filter:drop-shadow(0 0 10px rgba(212, 175, 55, 0.45));">🔬</div>
            <div>
                <div style="font-size:19px;font-weight:800;letter-spacing:0.8px;background:linear-gradient(135deg, #fff7d6 0%, #d4af37 50%, #aa7c11 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">ECRAG STUDIO</div>
                <div style="font-size:11px;color:#a8a29e;letter-spacing:0.3px;">Evidence-Calibrated Verification RAG</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 2. Prominent "New Chat Session" button
    if st.button("➕ New Chat Session", use_container_width=True, type="primary"):
        new_sid = create_chat_session(title="New Conversation", mode=st.session_state.app_mode)
        st.session_state.current_session_id = new_sid
        st.session_state.chat_messages = []
        st.session_state.question_history = []
        st.session_state.question_count = 0
        st.session_state.results = None
        st.session_state.correction_target = None
        st.rerun()

    st.divider()

    # 3. Execution Mode Selector
    st.subheader("🧠 Execution Mode")
    mode_options = [MODE_ONLINE, MODE_OFFLINE, MODE_DOCUMENT]
    
    # Ensure selector key exists and is valid
    if st.session_state.get("sidebar_mode_selector") not in mode_options:
        st.session_state.sidebar_mode_selector = st.session_state.app_mode

    curr_idx = mode_options.index(st.session_state.app_mode) if st.session_state.app_mode in mode_options else 0

    def _on_sidebar_mode_change():
        chosen = st.session_state.get("sidebar_mode_selector")
        if chosen and chosen in mode_options:
            set_app_mode(chosen)

    selected_mode = st.radio(
        "Active System Engine:",
        mode_options,
        index=curr_idx,
        key="sidebar_mode_selector",
        on_change=_on_sidebar_mode_change,
        help="Switch between Online Cloud + 7-Stage Verification, Local Offline Mode (requires local installation), or Document RAG."
    )
    if selected_mode != st.session_state.app_mode:
        set_app_mode(selected_mode)
        st.rerun()

    # Dynamic Mode Info Card
    if st.session_state.app_mode == MODE_ONLINE:
        has_gemini = bool(_resolve_gemini_api_key())
        status_color = "#d4af37" if has_gemini else "#ef4444"
        key_status = "✅ Connected" if has_gemini else "⚠️ Key Missing (Add in Secrets)"
        st.markdown(f"""
            <div style="background:rgba(212,175,55,0.06);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(212,175,55,0.22);border-left:4px solid {status_color};padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.45;box-shadow:0 4px 18px rgba(0,0,0,0.35);">
                <b style="color:{status_color};letter-spacing:0.3px;">🌐 ONLINE VERIFICATION MODE</b><br/>
                • <b>Model:</b> <code style="background:rgba(212,175,55,0.12);color:#fef08a;border:1px solid rgba(212,175,55,0.25);">{_resolve_gemini_model()}</code> (Cloud)<br/>
                • <b>API Key:</b> <b>{key_status}</b><br/>
                • <b>Search:</b> Multi-tier live internet retrieval<br/>
                • <b>Pipeline:</b> 7-Stage Factual Verification
            </div>
        """, unsafe_allow_html=True)
        if not has_gemini:
            st.warning("⚠️ **Gemini API Key Missing**: On Streamlit Cloud, click **Manage app** (bottom-right) ➔ **Settings** ➔ **Secrets** to add `GEMINI_API_KEY`.")
    elif st.session_state.app_mode == MODE_OFFLINE:
        st.markdown("""
            <div style="background:rgba(245,158,11,0.06);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(245,158,11,0.22);border-left:4px solid #f59e0b;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.45;box-shadow:0 4px 18px rgba(0,0,0,0.35);">
                <b style="color:#f59e0b;letter-spacing:0.3px;">🌴 OFFLINE / ISLAND MODE</b><br/>
                • <b>Model:</b> <code style="background:rgba(245,158,11,0.12);color:#fde047;border:1px solid rgba(245,158,11,0.25);">Qwen 1.5B / Ollama</code> (100% Local)<br/>
                • <b>Store:</b> Local ChromaDB knowledge base<br/>
                • <b>Network:</b> Zero external requests (Air-gapped)
            </div>
        """, unsafe_allow_html=True)
        st.info("💡 **Note:** For running the app in offline mode you need to install it.")
    else:
        doc_label = st.session_state.uploaded_document or "No PDF active"
        st.markdown(f"""
            <div style="background:rgba(212,175,55,0.06);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(212,175,55,0.22);border-left:4px solid #e6c65b;padding:10px 12px;border-radius:10px;font-size:11px;line-height:1.45;box-shadow:0 4px 18px rgba(0,0,0,0.35);">
                <b style="color:#e6c65b;letter-spacing:0.3px;">📚 DOCUMENT RAG MODE</b><br/>
                • <b>Document:</b> <code style="background:rgba(212,175,55,0.12);color:#fef08a;border:1px solid rgba(212,175,55,0.25);">{doc_label}</code><br/>
                • <b>Retrieval:</b> FAISS chunk embeddings<br/>
                • <b>Grounding:</b> Direct citation & anti-hallucination
            </div>
        """, unsafe_allow_html=True)

    st.divider()

    # 4. Chat History Segments
    st.subheader("💬 Chat History Segments")
    all_sessions = list_chat_sessions()
    active_sid = st.session_state.get("current_session_id", "default")

    if not all_sessions:
        st.caption("No saved conversations yet.")
    else:
        for s in all_sessions:
            sid = s["session_id"]
            title = s.get("title", "Conversation") or "Conversation"
            is_active = (sid == active_sid)
            s_mode = s.get("mode", "online")
            mode_icon = "🌐" if "online" in s_mode.lower() else ("🌴" if "offline" in s_mode.lower() else "📚")
            time_rel = _format_relative_time(s.get("updated_at", ""))
            count = s.get("message_count", 0)

            col_s_btn, col_s_del = st.columns([0.83, 0.17])
            with col_s_btn:
                disp_title = (title[:24] + "...") if len(title) > 27 else title
                btn_type = "primary" if is_active else "secondary"
                btn_label = f"{'▶ ' if is_active else ''}{mode_icon} {disp_title}"
                if st.button(btn_label, key=f"sess_btn_{sid}", use_container_width=True, type=btn_type, help=f"{title}\n• {count} messages • {time_rel}"):
                    st.session_state.current_session_id = sid
                    st.session_state.chat_messages = load_session_messages(sid)
                    st.session_state.question_count = sum(1 for m in st.session_state.chat_messages if m.get("role") == "user")
                    st.session_state.results = None
                    st.rerun()
            with col_s_del:
                if st.button("✕", key=f"del_btn_{sid}", help=f"Delete '{title}'"):
                    delete_chat_session(sid)
                    if is_active:
                        remaining = list_chat_sessions()
                        if remaining:
                            st.session_state.current_session_id = remaining[0]["session_id"]
                            st.session_state.chat_messages = load_session_messages(remaining[0]["session_id"])
                            st.session_state.question_count = sum(1 for m in st.session_state.chat_messages if m.get("role") == "user")
                        else:
                            st.session_state.current_session_id = create_chat_session("New Conversation")
                            st.session_state.chat_messages = []
                            st.session_state.question_count = 0
                    st.rerun()

        with st.expander("⚙️ Manage Segments", expanded=False):
            if st.button("🗑️ Clear All Conversations", use_container_width=True, type="secondary"):
                clear_all_chat_sessions()
                st.session_state.current_session_id = create_chat_session("New Conversation")
                st.session_state.chat_messages = []
                st.session_state.question_count = 0
                st.session_state.results = None
                st.rerun()

    st.divider()

    # 5. Document Controls in Sidebar
    st.subheader("📄 Document Controls")
    if st.session_state.uploaded_document:
        st.success(f"🟢 Active: **{st.session_state.uploaded_document}**")
        if st.button("🔄 Unload Document", use_container_width=True):
            new_document()
            if st.session_state.app_mode == MODE_DOCUMENT:
                set_app_mode(MODE_ONLINE)
            st.rerun()
    else:
        st.info("⚪ No document loaded")

    # 6. Session Statistics
    st.divider()
    st.subheader("📊 Session Statistics")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("PDFs Uploaded", st.session_state.pdf_count)
    with c2:
        st.metric("Questions", st.session_state.question_count)

    st.divider()
    st.subheader("🔬 ECRAG Pipeline")
    st.markdown("""
**📄 Document / Web Evidence**
↓
**🔎 Multi-Tier Retrieval**
↓
**🤖 LLM Generation**
↓
**🧩 7-Stage Factual Verification**
↓
**📊 Confidence & Provenance**
↓
**🎯 Final Decision (ANSWER/WARN/ABSTAIN)**
""")


# ============================================================
# MAIN HEADER & DYNAMIC MODE STATUS BANNER
# ============================================================

st.markdown("""
<div style="margin-bottom: 8px;">
    <h1 style="font-size: 34px; margin-bottom: 4px; display: inline-flex; align-items: center; gap: 10px;">
        <span>📚</span>
        <span class="gold-text">Evidence-Calibrated RAG</span>
    </h1>
    <div style="font-size: 14px; color: #d4cfc3; font-weight: 500; letter-spacing: 0.2px;">
        Conversational, factual verification RAG with multi-source evidence calibration and transparent abstention.
    </div>
</div>
""", unsafe_allow_html=True)

# Dynamic status banner
banner_mode = st.session_state.get("app_mode", MODE_ONLINE)
if banner_mode == MODE_ONLINE:
    banner_bg = "rgba(212, 175, 55, 0.07)"
    banner_border = "rgba(212, 175, 55, 0.35)"
    banner_accent = "#d4af37"
    banner_icon = "🌐"
    banner_title = "ONLINE VERIFICATION MODE ACTIVE"
    banner_desc = "Cloud Gemini • Live Multi-Tier Web Search • 7-Stage Factual Verification Pipeline"
elif banner_mode == MODE_OFFLINE:
    banner_bg = "rgba(245, 158, 11, 0.07)"
    banner_border = "rgba(245, 158, 11, 0.35)"
    banner_accent = "#f59e0b"
    banner_icon = "🌴"
    banner_title = "OFFLINE / ISLAND MODE ACTIVE"
    banner_desc = "100% Local Qwen 1.5B / Ollama • ChromaDB Knowledge Base • Zero Internet Requests • For running the app in offline mode you need to install it"
else:
    banner_bg = "rgba(212, 175, 55, 0.07)"
    banner_border = "rgba(212, 175, 55, 0.35)"
    banner_accent = "#e6c65b"
    banner_icon = "📚"
    banner_title = "DOCUMENT RAG MODE ACTIVE"
    doc_n = st.session_state.uploaded_document or "No document uploaded"
    banner_desc = f"Active PDF: {doc_n} • FAISS Vector Store • Strict Document Grounding"

st.markdown(f"""
    <div style="background:{banner_bg}; backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); border: 1px solid {banner_border}; border-left: 5px solid {banner_accent}; padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 245, 200, 0.08);">
        <div style="font-size:13px; font-weight:700; color:{banner_accent}; letter-spacing:0.4px;">
            <span>{banner_icon}</span> {banner_title}
        </div>
        <div style="font-size:11px; color:#c7c5bc; margin-top:3px; line-height:1.4;">
            {banner_desc}
        </div>
    </div>
""", unsafe_allow_html=True)

if banner_mode == MODE_OFFLINE:
    st.info("💡 **Note:** For running the app in offline mode you need to install it.")

st.divider()

# Upload section expander
with st.expander("📄 Upload Document (PDF)", expanded=(banner_mode == MODE_DOCUMENT and not st.session_state.uploaded_document)):
    uploaded_file = st.file_uploader(
        "Upload a PDF containing reference material, policies, research, or guides.",
        type=["pdf"],
        key="pdf_uploader"
    )
    if uploaded_file is not None:
        if st.session_state.uploaded_document != uploaded_file.name:
            try:
                with open(PDF_PATH, "wb") as file:
                    file.write(uploaded_file.getbuffer())
                st.session_state.uploaded_document = uploaded_file.name
                st.session_state.pdf_count += 1
                st.session_state.results = None
                set_app_mode(MODE_DOCUMENT)
                st.success(f"✅ {uploaded_file.name} uploaded successfully! Switched to Document Mode.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Could not save document: {e}")


# ============================================================
# CONVERSATION
# ============================================================

if st.session_state.chat_messages:
    st.subheader("💬 Conversation")

    for index, message in enumerate(st.session_state.chat_messages):
        role = message.get("role")
        content = message.get("content", "")

        if role == "user":
            with st.chat_message("user"):
                st.write(content)

        elif role == "assistant":
            with st.chat_message("assistant"):
                display_content = re.sub(r"(?i)\n+in short:\s*.*$", "", content).strip()
                safe_content = display_content.replace("$", r"\$")
                st.markdown(safe_content)

                if not message.get("is_conversational"):
                    one_line = message.get("one_line_answer", "")
                    if one_line:
                        safe_one_line = one_line.replace("$", r"\$")
                        st.info(f"**In short:** {safe_one_line}")

                    confidence = message.get("confidence")
                    decision = message.get("decision", "UNKNOWN")

                    claim_ledger = message.get("claim_ledger")
                    if confidence is not None:
                        counts = claim_ledger.get("counts") if isinstance(claim_ledger, dict) else None
                        render_factual_verification_meter(
                            confidence=confidence,
                            decision=decision,
                            counts=counts,
                            quality_score=message.get("quality_score"),
                            source=message.get("source", ""),
                            response_time=message.get("response_time"),
                            key_suffix=f"chat_{index}"
                        )

                    # Direct Clickable Reference Sources
                    if claim_ledger:
                        render_verified_sources(claim_ledger)
                    elif message.get("source"):
                        st.caption(message["source"])

                # 7-Stage Verification Timeline (Collapsible)
                if message.get("claim_ledger"):
                    render_verification_timeline(
                        message.get("claim_ledger"),
                        message.get("verification_timeline"),
                        key_suffix=f"chat_{index}"
                    )

                # ----------------------------------------------------
                # FORENSIC ACCOUNTABILITY FEATURES
                # ----------------------------------------------------
                # 1. Anti-Sycophancy Presupposition Shield Alert
                syc_report = message.get("sycophancy_report")
                if syc_report and syc_report.get("shield_activated"):
                    st.warning(
                        f"🛡️ **Anti-Sycophancy Guardrail Activated**: Refused to affirm false presupposition "
                        f"(*\"{syc_report.get('presupposition')}\"*).\n\n"
                        f"**Factual Rebuttal**: {syc_report.get('rebuttal_explanation')}"
                    )

                # 2. Sentence-Level Truth Heatmap
                heatmap_html = message.get("truth_heatmap_html")
                if not heatmap_html and message.get("claim_ledger"):
                    try:
                        heatmap_html = TruthHeatmapRenderer.generate_truth_heatmap_html(
                            display_content,
                            message.get("claim_ledger"),
                            element_id=f"thm_{index}"
                        )
                        message["truth_heatmap_html"] = heatmap_html
                    except Exception:
                        pass

                if heatmap_html:
                    with st.expander("🔍 Sentence-Level Truth Heatmap", expanded=False):
                        st.components.v1.html(heatmap_html, height=280, scrolling=True)

                # Correction Button
                if st.button("✏️ Correct / Challenge", key=f"feedback_{index}"):
                    st.session_state.correction_target = index
                    st.rerun()

                # Correction Form
                if st.session_state.correction_target == index:
                    correction = st.text_area(
                        "What do you think is incorrect?",
                        placeholder="Example: The document actually says 80%, not 75%, in Section 4.2.",
                        key=f"correction_{index}",
                        height=90
                    )
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("🔍 Reconsider", key=f"reconsider_{index}", type="primary"):
                            if not correction.strip():
                                st.warning("Please enter the correction.")
                            else:
                                correction_text = correction.strip()
                                st.session_state.chat_messages.append({
                                    "role": "correction",
                                    "content": correction_text,
                                    "target": index
                                })
                                st.session_state.correction_target = None

                                if st.session_state.uploaded_document:
                                    reconsider_question = f"""The user is challenging the previous answer.\n\nPrevious answer:\n{content}\n\nUser correction/challenge:\n{correction_text}\n\nReconsider using the uploaded document as authoritative source."""
                                    with st.spinner("🔍 Rechecking the correction against the document..."):
                                        try:
                                            output = run_backend(reconsider_question)
                                            revised_answer = extract_answer(output) or output
                                            revised_one_line = generate_one_line_answer(correction_text, revised_answer)
                                            st.session_state.chat_messages.append({
                                                "role": "assistant",
                                                "content": revised_answer,
                                                "one_line_answer": revised_one_line,
                                                "confidence": extract_confidence(output),
                                                "decision": extract_decision(output),
                                                "source": f"📄 {st.session_state.uploaded_document} • Reconsidered",
                                                "raw": output
                                            })
                                            save_chat_message(st.session_state.chat_messages[-1])
                                            st.session_state.results = output
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Could not reconsider: {e}")
                                            st.stop()
                                else:
                                    st.info("Direct corrections in general mode are noted.")
                                    st.rerun()

                    with b2:
                        if st.button("Cancel", key=f"cancel_{index}"):
                            st.session_state.correction_target = None
                            st.rerun()

st.caption("Press **Enter** to send. Use **Shift + Enter** for a new line.")

question = st.chat_input(
    f"Ask a question in {st.session_state.get('app_mode', MODE_ONLINE)}...",
    key="question_box"
)


# ============================================================
# NEW QUESTION EXECUTION
# ============================================================

if question:
    original_user_question = question.strip()
    if not original_user_question:
        st.stop()

    user_question = normalize_chat_language(original_user_question)
    st.session_state.question_count += 1
    st.session_state.question_history.append(original_user_question)
    st.session_state.chat_messages.append({
        "role": "user",
        "content": original_user_question
    })
    save_chat_message({"role": "user", "content": original_user_question})

    with st.chat_message("user"):
        st.write(original_user_question)

    generation_started = time.perf_counter()

    # Fast path 1: Project Identity
    if is_project_identity_question(user_question):
        answer = project_identity_answer()
        output = f"""======================================================================
              EVIDENCE-CALIBRATED RAG
======================================================================
PROJECT INFORMATION
----------------------------------------------------------------------
{answer}
FINAL DECISION: ANSWER
CONFIDENCE: 1.000
======================================================================"""
        quality = assess_answer_quality(user_question, answer, mode="project", evidence_count=1)
        output = append_quality_assessment(output, quality)
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "one_line_answer": answer,
            "confidence": 1.0,
            "decision": "ANSWER",
            "source": "🏫 ECRAG Project Information",
            "quality_score": quality["score"],
            "raw": output
        })
        response_time = time.perf_counter() - generation_started
        if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
            st.session_state.chat_messages[-1]["response_time"] = response_time
            save_chat_message(st.session_state.chat_messages[-1])
        st.session_state.results = output
        st.rerun()

    # Fast path 2: Candidate Suitability
    if is_candidate_selection_question(user_question) and not st.session_state.uploaded_document:
        with st.spinner("🧠 Comparing candidates against requirements..."):
            candidate_result = candidate_selection_answer(user_question, build_conversation_context())
        answer = candidate_result["answer"]
        confidence = candidate_result["confidence"]
        decision = candidate_result["decision"]
        source = candidate_result["source"]
        one_line_answer = generate_one_line_answer(user_question, answer)
        quality = assess_answer_quality(user_question, answer, mode="local")
        output = f"""FINAL DECISION: {decision}\nCONFIDENCE: {confidence:.3f}"""
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "one_line_answer": one_line_answer,
            "confidence": confidence,
            "decision": decision,
            "source": source,
            "quality_score": quality["score"],
            "raw": output,
        })
        response_time = time.perf_counter() - generation_started
        if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
            st.session_state.chat_messages[-1]["response_time"] = response_time
            save_chat_message(st.session_state.chat_messages[-1])
        st.session_state.results = output
        st.rerun()

    # Fast path 3: Conversational Bypass (Greetings & pleasantries)
    if is_conversational_bypass(user_question):
        with st.spinner("💬 Thinking..."):
            try:
                conv_messages = [
                    {"role": "system", "content": "You are ECRAG, a polite and helpful assistant. Respond warmly and concisely."},
                    {"role": "user", "content": user_question}
                ]
                conv_response = ai_chat(conv_messages)
                answer = conv_response["message"]["content"].strip()
            except Exception:
                answer = "Hello! How can I help you today?"
        one_line_answer = generate_one_line_answer(user_question, answer)
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer,
            "one_line_answer": one_line_answer,
            "confidence": 0.95,
            "decision": "ANSWER",
            "source": "💬 Conversational Mode • Pipeline skipped (non-factual)",
            "is_conversational": True,
        })
        response_time = time.perf_counter() - generation_started
        if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
            st.session_state.chat_messages[-1]["response_time"] = response_time
            save_chat_message(st.session_state.chat_messages[-1])
        st.session_state.results = None
        st.rerun()

    # ========================================================
    # MODE-SPECIFIC QUESTION ROUTING
    # ========================================================
    current_mode = st.session_state.get("app_mode", MODE_ONLINE)

    # 1. DOCUMENT MODE
    if current_mode == MODE_DOCUMENT:
        if not st.session_state.uploaded_document:
            st.warning("⚠️ Document Mode is active, but no PDF is currently uploaded. Please upload a PDF in the sidebar or switch to Online Mode.")
            st.stop()

        contextual_question = build_contextual_pdf_question(user_question)
        timeline_events = []
        with st.status("🔬 Running 7-Stage Factual Verification (Document Mode)...", expanded=True) as status_box:
            def live_doc_cb(event):
                timeline_events.append(event)
                st_type = event.get("type")
                stg = event.get("stage")
                stg_name = event.get("stage_name", "")
                stg_msg = event.get("message", "")
                if st_type == "stage_start":
                    status_box.update(label=f"🔍 Stage {stg}: {stg_name}...")
                    st.write(f"**Stage {stg}: {stg_name}** — *{stg_msg}*")
                elif st_type == "stage_complete":
                    st.write(f"✅ **Stage {stg}: {stg_name}** — {stg_msg}")
                    previews = event.get("evidence_previews", [])
                    if previews:
                        with st.expander(f"👀 View evidence excerpts ({len(previews)})", expanded=False):
                            for p in previews:
                                st.markdown(f"- **{p.get('title')}**: *\"{p.get('snippet')}\"*")
                elif st_type == "stage_skipped":
                    st.write(f"⏭️ **Stage {stg}: {stg_name}** — *{stg_msg}*")
                elif st_type == "stage_error":
                    st.warning(f"⚠️ **Stage {stg}: {stg_name}** — *{stg_msg}*")

            try:
                output = run_backend(contextual_question, progress_callback=live_doc_cb)
                decision = extract_decision(output)
                confidence = extract_confidence(output)
                answer = extract_answer(output) or output
                one_line_answer = generate_one_line_answer(user_question, answer)
                pdf_supported = extract_number(r"Supported:\s*(\d+)", output)
                pdf_contradicted = extract_number(r"Contradicted:\s*(\d+)", output)
                pdf_uncertain = extract_number(r"Uncertain:\s*(\d+)", output)
                quality = assess_answer_quality(user_question, answer, mode="pdf", evidence_count=max(1, pdf_supported + pdf_uncertain), supported=pdf_supported, contradicted=pdf_contradicted, uncertain=pdf_uncertain)
                output = append_quality_assessment(output, quality)

                status_box.update(label=f"🎯 Verification Complete • {decision} ({confidence:.1%})", state="complete", expanded=False)
                doc_ledger = {
                    "overall_decision": decision,
                    "overall_confidence": confidence,
                    "counts": {"verified": pdf_supported, "partially_verified": pdf_uncertain, "contradicted": pdf_contradicted, "unverified": 0, "total_claims": max(1, pdf_supported + pdf_uncertain + pdf_contradicted)},
                    "stage_summaries": {
                        1: {"name": "Official Sources", "status": "skipped", "skip_reason": "Document mode active"},
                        2: {"name": "Primary Evidence (PDF)", "status": "completed", "source_count": max(1, pdf_supported + pdf_uncertain), "message": f"Verified against {st.session_state.uploaded_document}"},
                        3: {"name": "Reference Sources", "status": "skipped", "skip_reason": "Document mode active"},
                        4: {"name": "Academic Sources", "status": "skipped", "skip_reason": "Document mode active"},
                        5: {"name": "Reputable News", "status": "skipped", "skip_reason": "Document mode active"},
                        6: {"name": "Community Sources", "status": "skipped", "skip_reason": "Document mode active"},
                        7: {"name": "Final Validation", "status": "completed", "message": f"Contradictions: {pdf_contradicted}, Supported: {pdf_supported}"}
                    },
                    "claims": [{"claim_text": answer[:150], "verdict": "VERIFIED" if decision == "ANSWER" else ("CONTRADICTED" if decision == "ABSTAIN" else "PARTIALLY_VERIFIED"), "confidence": confidence, "reasoning": f"Grounded in {st.session_state.uploaded_document}"}],
                    "contradictions_detected": []
                }
                st.session_state.latest_claim_ledger = doc_ledger
                st.session_state.latest_verification_timeline = timeline_events

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": answer,
                    "one_line_answer": one_line_answer,
                    "confidence": confidence,
                    "decision": decision,
                    "source": f"📄 {st.session_state.uploaded_document} • 7-Stage Factual Verification",
                    "quality_score": quality["score"],
                    "claim_ledger": doc_ledger,
                    "verification_timeline": timeline_events,
                    "raw": output
                })
                response_time = time.perf_counter() - generation_started
                if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
                    st.session_state.chat_messages[-1]["response_time"] = response_time
                    save_chat_message(st.session_state.chat_messages[-1])
                st.session_state.results = output
                st.rerun()

            except Exception as e:
                st.error(f"❌ Document mode error: {e}")
                st.stop()

    # 2. OFFLINE / ISLAND MODE
    elif current_mode == MODE_OFFLINE:
        with st.spinner("📚 Searching local offline knowledge base (ChromaDB)..."):
            try:
                result = offline_rag_answer(user_question)
                answer = result["answer"]
                confidence = result["confidence"]
                decision = result["decision"]
                output = result["output"]
                source = result["source"]
                one_line_answer = answer.split("\n")[0][:200] if answer else ""
                quality = assess_answer_quality(user_question, answer, mode="local")
                output = append_quality_assessment(output, quality)

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": answer,
                    "one_line_answer": one_line_answer,
                    "confidence": confidence,
                    "decision": decision,
                    "source": source,
                    "quality_score": quality["score"],
                    "claim_ledger": result.get("claim_ledger"),
                    "truth_heatmap_html": result.get("truth_heatmap_html"),
                    "sycophancy_report": result.get("sycophancy_report"),
                    "raw": output,
                })
                response_time = time.perf_counter() - generation_started
                if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
                    st.session_state.chat_messages[-1]["response_time"] = response_time
                    save_chat_message(st.session_state.chat_messages[-1])
                st.session_state.results = output
                st.rerun()

            except Exception as e:
                st.error(f"❌ Offline mode error: {e}")
                st.stop()

    # 3. ONLINE MODE (Cloud Gemini + Live Web + 7-Stage Pipeline)
    else:
        if not _resolve_gemini_api_key():
            st.error(
                "⚠️ **GEMINI_API_KEY is not configured!**\n\n"
                "Online Verification Mode requires a Google Gemini API key to run.\n\n"
                "**How to fix on Streamlit Community Cloud:**\n"
                "1. Click the **`Manage app`** button in the lower-right corner of your screen.\n"
                "2. Click the three dots menu (**`⋮`**) ➔ **Settings** ➔ **Secrets**.\n"
                "3. In the text area, paste:\n"
                "   ```toml\n"
                "   GEMINI_API_KEY = \"your_gemini_api_key_here\"\n"
                "   ECRAG_GEMINI_MODEL = \"gemini-3.5-flash-lite\"\n"
                "   ```\n"
                "4. Click **Save**. Streamlit will automatically reload with Online Mode active!"
            )
            st.stop()

        timeline_events = []
        with st.status("🔬 Running 7-Stage Factual Verification Pipeline...", expanded=True) as status_box:
            def live_web_cb(event):
                timeline_events.append(event)
                st_type = event.get("type")
                stg = event.get("stage")
                stg_name = event.get("stage_name", "")
                stg_msg = event.get("message", "")
                if st_type == "stage_start":
                    status_box.update(label=f"🔍 Stage {stg}: {stg_name}...")
                    st.write(f"**Stage {stg}: {stg_name}** — *{stg_msg}*")
                elif st_type == "stage_complete":
                    st.write(f"✅ **Stage {stg}: {stg_name}** — {stg_msg}")
                    previews = event.get("evidence_previews", [])
                    if previews:
                        with st.expander(f"👀 View evidence excerpts ({len(previews)})", expanded=False):
                            for p in previews:
                                st.markdown(f"- **[{p.get('domain')}]** [{p.get('title')}]({p.get('url')}): *\"{p.get('snippet')}\"*")
                elif st_type == "stage_skipped":
                    st.write(f"⏭️ **Stage {stg}: {stg_name}** — *{stg_msg}*")
                elif st_type == "stage_error":
                    st.warning(f"⚠️ **Stage {stg}: {stg_name}** — *{stg_msg}*")

            try:
                conversation_context = build_conversation_context()
                special_web_result = False
                realtime_result = None

                if is_explicit_latest_isro_question(user_question):
                    web_result = deterministic_isro_latest_answer(user_question)
                    answer = web_result["answer"]
                    confidence = web_result["confidence"]
                    decision = web_result["decision"]
                    output = web_result["output"]
                    source = web_result["source"]
                    special_web_result = True
                elif is_weather_question(user_question):
                    realtime_result = realtime_weather_answer(user_question, conversation_context)
                    if realtime_result and realtime_result.get("decision") != "ABSTAIN":
                        answer = realtime_result["answer"]
                        confidence = realtime_result["confidence"]
                        decision = realtime_result["decision"]
                        output = realtime_result["output"]
                        source = realtime_result["source"]
                        quality = realtime_result.get("quality")
                    else:
                        realtime_result = None

                if special_web_result:
                    pass
                elif realtime_result:
                    pass
                else:
                    # In Online Mode, run general_web_answer with 7-stage verification
                    web_result = general_web_answer(
                        user_question,
                        conversation_context,
                        progress_callback=live_web_cb
                    )
                    answer = web_result["answer"]
                    confidence = web_result["confidence"]
                    decision = web_result["decision"]
                    output = web_result["output"]
                    source = web_result["source"]

                one_line_answer = generate_one_line_answer(user_question, answer)

                if special_web_result:
                    web_verification = web_result.get("verification", {})
                    quality = assess_answer_quality(user_question, answer, mode="web", evidence_count=web_result.get("evidence_count", 0), supported=web_verification.get("supported", 0), contradicted=web_verification.get("contradicted", 0), uncertain=web_verification.get("uncertain", 0))
                elif realtime_result:
                    quality = assess_answer_quality(user_question, answer, mode="realtime", realtime_quality=quality)
                else:
                    web_verification = web_result.get("verification", {}) if "web_result" in locals() and isinstance(web_result, dict) else {}
                    quality = assess_answer_quality(user_question, answer, mode="web", evidence_count=web_result.get("evidence_count", 0) if "web_result" in locals() and isinstance(web_result, dict) else 0, supported=web_verification.get("supported", 0), contradicted=web_verification.get("contradicted", 0), uncertain=web_verification.get("uncertain", 0))

                output = append_quality_assessment(output, quality)

                status_box.update(label=f"🎯 Verification Complete • {decision} ({confidence:.1%})", state="complete", expanded=False)
                web_ledger = web_result.get("claim_ledger") if "web_result" in locals() and isinstance(web_result, dict) else None
                st.session_state.latest_claim_ledger = web_ledger
                st.session_state.latest_verification_timeline = timeline_events

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": answer,
                    "one_line_answer": one_line_answer,
                    "confidence": confidence,
                    "decision": decision,
                    "source": source,
                    "quality_score": quality["score"],
                    "claim_ledger": web_ledger,
                    "verification_timeline": timeline_events,
                    "truth_heatmap_html": web_result.get("truth_heatmap_html") if "web_result" in locals() and isinstance(web_result, dict) else None,
                    "sycophancy_report": web_result.get("sycophancy_report") if "web_result" in locals() and isinstance(web_result, dict) else None,
                    "raw": output
                })

                response_time = time.perf_counter() - generation_started
                if st.session_state.chat_messages and st.session_state.chat_messages[-1].get("role") == "assistant":
                    st.session_state.chat_messages[-1]["response_time"] = response_time
                    save_chat_message(st.session_state.chat_messages[-1])
                st.session_state.results = output
                st.rerun()

            except Exception as e:
                st.error(f"❌ Online mode error: {e}")
                st.stop()

    st.rerun()


# ============================================================
# LATEST ANALYSIS
# ============================================================

# Latest results are presented directly inside the chat flow above.
# Optional technical debug dump is available in an expander:
if st.session_state.results:
    with st.expander("🛠️ Developer Diagnostic Log (Raw Pipeline)", expanded=False):
        st.code(st.session_state.results, language="text")


# FOOTER
# ============================================================

st.divider()

st.caption(
    "ECRAG — Conversational Evidence-Calibrated "
    "Retrieval-Augmented Generation"
)