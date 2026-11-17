import json
import re
from typing import List, Dict, Any, Optional

try:
    import ollama
except ImportError:
    ollama = None

try:
    from .claim_ledger import (
        ClaimLedger,
        ClaimEntry,
        EvidenceItem,
        split_into_atomic_claims,
        VERDICT_VERIFIED,
        VERDICT_PARTIALLY_VERIFIED,
        VERDICT_CONTRADICTED,
        VERDICT_UNVERIFIED,
        STAGE_NAMES
    )
    from .pipeline import SevenStageVerificationPipeline
except ImportError:
    from claim_ledger import (
        ClaimLedger,
        ClaimEntry,
        EvidenceItem,
        split_into_atomic_claims,
        VERDICT_VERIFIED,
        VERDICT_PARTIALLY_VERIFIED,
        VERDICT_CONTRADICTED,
        VERDICT_UNVERIFIED,
        STAGE_NAMES
    )
    from pipeline import SevenStageVerificationPipeline

LLM_MODEL = "llama3.2:3b"


# ============================================================
# CLAIM DECOMPOSITION
# ============================================================

def decompose_claims(answer: str) -> List[str]:
    """
    Decomposes an answer into discrete atomic claims.
    Uses local Ollama if available, with robust deterministic fallback.
    """
    prompt = f"""
You are a claim decomposition system.

Break the following answer into its smallest meaningful
factual claims.

IMPORTANT:
- Only extract factual claims from the ANSWER.
- Do not create claims about the evidence itself.
- Do not create claims such as: "The evidence is located on page 5."
- Do not create explanations about verification.
- Do not invent information.
- Return ONLY a numbered list.

ANSWER:
{answer}
"""
    if ollama is not None:
        try:
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response["message"]["content"].strip()
            claims = []
            for line in text.splitlines():
                line = line.strip()
                match = re.match(r"^\d+[\.\)]\s*(.+)$", line)
                if match:
                    claim = match.group(1).strip()
                    if claim:
                        claims.append(claim)
            if claims:
                return claims
        except Exception:
            pass

    # Deterministic fallback using proven sentence/clause extraction
    return split_into_atomic_claims(answer)


# ============================================================
# VERIFY CLAIM (Legacy ECRAG Interface)
# ============================================================

def verify_claim(claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Evaluates whether an individual claim is supported, contradicted, or uncertain.
    Maintains backward compatibility with earlier ECRAG stages.
    """
    evidence_text = ""
    for number, item in enumerate(evidence, start=1):
        page_val = item.get("page", 1)
        score_val = item.get("score", 0.0)
        evidence_text += (
            f"\nEvidence {number}\n"
            f"Page: {page_val}\n"
            f"Similarity: {score_val:.3f}\n"
            f"Text:\n{item.get('text', '')}\n"
        )

    prompt = f"""
You are a strict evidence verification system.
Determine whether the CLAIM is supported by the provided EVIDENCE.

CLAIM:
{claim}

EVIDENCE:
{evidence_text}

Choose exactly ONE verdict:
SUPPORTED
CONTRADICTED
UNCERTAIN

Return ONLY valid JSON:
{{
    "verdict": "SUPPORTED",
    "reason": "Short explanation based only on the evidence."
}}
"""
    if ollama is not None:
        try:
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_response = response["message"]["content"].strip()
            try:
                result = json.loads(raw_response)
                verdict = result.get("verdict", "UNCERTAIN").upper()
                reason = result.get("reason", "No reason provided.")
                if verdict in ["SUPPORTED", "CONTRADICTED", "UNCERTAIN"]:
                    return {"verdict": verdict, "reason": reason}
            except Exception:
                pass

            json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    verdict = result.get("verdict", "UNCERTAIN").upper()
                    reason = result.get("reason", "No reason provided.")
                    if verdict in ["SUPPORTED", "CONTRADICTED", "UNCERTAIN"]:
                        return {"verdict": verdict, "reason": reason}
                except Exception:
                    pass

            upper_response = raw_response.upper()
            if "CONTRADICTED" in upper_response:
                return {"verdict": "CONTRADICTED", "reason": "Evidence contradicts claim."}
            if "SUPPORTED" in upper_response:
                return {"verdict": "SUPPORTED", "reason": "Evidence supports claim."}
        except Exception:
            pass

    # Deterministic fallback when Ollama is unavailable
    claim_words = set(re.findall(r"\w{4,}", claim.lower()))
    best_overlap = 0
    matched_ev = None
    for ev in evidence:
        text_lower = ev.get("text", "").lower()
        overlap = sum(1 for w in claim_words if w in text_lower)
        if overlap > best_overlap:
            best_overlap = overlap
            matched_ev = ev

    ratio = best_overlap / max(1, len(claim_words))
    if ratio >= 0.5:
        return {
            "verdict": "SUPPORTED",
            "reason": f"Corroborated by text in evidence (Page {matched_ev.get('page', 1)})."
        }
    elif ratio >= 0.25:
        return {
            "verdict": "UNCERTAIN",
            "reason": "Evidence contains partial matches but lacks decisive proof."
        }
    return {
        "verdict": "UNCERTAIN",
        "reason": "Evidence does not contain sufficient information to substantiate this claim."
    }


# ============================================================
# SEVEN-STAGE PIPELINE FACTORY
# ============================================================

def create_verification_pipeline(
    ai_chat_fn: Optional[Any] = None,
    pdf_path: Optional[str] = None,
    offline_chunks: Optional[List[Dict[str, Any]]] = None,
    offline_mode: bool = False
) -> SevenStageVerificationPipeline:
    """Helper factory for initializing the 7-stage verification pipeline."""
    return SevenStageVerificationPipeline(
        ai_chat_fn=ai_chat_fn,
        pdf_path=pdf_path,
        offline_chunks=offline_chunks,
        offline_mode=offline_mode
    )


if __name__ == "__main__":
    test_claim = "The council uses standard forms for employee administrative functions."
    test_evidence = [
        {"page": 3, "score": 0.85, "text": "The council uses standard forms for employee administrative functions."}
    ]
    res = verify_claim(test_claim, test_evidence)
    print("Verification result:", res)
