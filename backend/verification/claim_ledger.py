"""
Evidence Provenance and Claim Ledger for ECRAG 7-Stage Factual Verification.

Tracks factual claims, evidence provenance across 7 stages, citations,
contradictions, source independence, date consistency, and verdicts:
- VERIFIED
- PARTIALLY_VERIFIED
- CONTRADICTED
- UNVERIFIED
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any


# ============================================================
# VERDICTS AND STAGES
# ============================================================

VERDICT_VERIFIED = "VERIFIED"
VERDICT_PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
VERDICT_CONTRADICTED = "CONTRADICTED"
VERDICT_UNVERIFIED = "UNVERIFIED"

VALID_VERDICTS = {
    VERDICT_VERIFIED,
    VERDICT_PARTIALLY_VERIFIED,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIED
}

STAGE_NAMES = {
    1: "Official Sources (.gov, WHO, Agencies)",
    2: "Primary Evidence (Original Reports, Datasets, PDFs)",
    3: "Reference Sources (Wikipedia, Encyclopedias)",
    4: "Academic Sources (Peer-Reviewed, Universities)",
    5: "Reputable News (Independent Reporting)",
    6: "Community Sources (Reddit, Quora, Forums - Leads Only)",
    7: "Final Validation (Contradiction & Citation Check)"
}

STAGE_SHORT_TITLES = {
    1: "Official Sources",
    2: "Primary Evidence",
    3: "Reference Sources",
    4: "Academic Sources",
    5: "Reputable News",
    6: "Community Sources",
    7: "Final Validation"
}

# Authority score by stage: higher means higher epistemic authority
STAGE_AUTHORITY_WEIGHT = {
    1: 1.0,   # Official (.gov, WHO)
    2: 0.95,  # Primary reports / PDFs
    4: 0.90,  # Academic / peer-reviewed
    3: 0.80,  # Reference / Wikipedia / .edu
    5: 0.75,  # Reputable news
    6: 0.35,  # Community (leads only; never authoritative alone)
}


# ============================================================
# DATA STRUCTURES
# ============================================================

class EvidenceItem:
    """A discrete piece of evidence with complete provenance."""
    def __init__(
        self,
        evidence_id: str,
        stage: int,
        title: str,
        url_or_ref: str,
        snippet: str,
        domain: str = "",
        published_date: Optional[str] = None,
        authority_tier: int = 1,
        is_community_lead: bool = False,
        extra_metadata: Optional[Dict[str, Any]] = None
    ):
        self.evidence_id = evidence_id
        self.stage = stage
        self.stage_name = STAGE_NAMES.get(stage, f"Stage {stage}")
        self.title = title
        self.url_or_ref = url_or_ref
        self.snippet = snippet
        self.domain = domain or self._extract_domain(url_or_ref)
        self.published_date = published_date
        self.authority_tier = authority_tier
        self.is_community_lead = is_community_lead or (stage == 6)
        self.extra_metadata = extra_metadata or {}

    @staticmethod
    def _extract_domain(ref: str) -> str:
        if not ref:
            return "unknown"
        if ref.startswith("doc://") or ref.startswith("pdf://"):
            return "local-document"
        if ref.startswith("chromadb://") or ref.startswith("local://"):
            return "offline-knowledge-base"
        match = re.search(r"https?://([^/]+)", ref)
        if match:
            return match.group(1).lower().replace("www.", "")
        return "external-source"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "stage": self.stage,
            "stage_name": self.stage_name,
            "title": self.title,
            "url_or_ref": self.url_or_ref,
            "domain": self.domain,
            "snippet": self.snippet,
            "published_date": self.published_date,
            "authority_tier": self.authority_tier,
            "is_community_lead": self.is_community_lead,
            "extra_metadata": self.extra_metadata
        }


class ClaimEntry:
    """A discrete factual claim and its verification ledger."""
    def __init__(
        self,
        claim_id: str,
        claim_text: str,
        verdict: str = VERDICT_UNVERIFIED,
        confidence: float = 0.0,
        supporting_citations: Optional[List[Dict[str, Any]]] = None,
        contradictions: Optional[List[Dict[str, Any]]] = None,
        reasoning: str = "",
        source_independence_score: float = 0.0,
        date_consistency_status: str = "UNDATED"
    ):
        self.claim_id = claim_id
        self.claim_text = claim_text
        self.verdict = verdict if verdict in VALID_VERDICTS else VERDICT_UNVERIFIED
        self.confidence = max(0.0, min(float(confidence), 1.0))
        self.supporting_citations = supporting_citations or []
        self.contradictions = contradictions or []
        self.reasoning = reasoning
        self.source_independence_score = source_independence_score
        self.date_consistency_status = date_consistency_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 3),
            "supporting_citations": self.supporting_citations,
            "contradictions": self.contradictions,
            "reasoning": self.reasoning,
            "source_independence_score": round(self.source_independence_score, 3),
            "date_consistency_status": self.date_consistency_status
        }


class ClaimLedger:
    """Complete provenance ledger tracking evidence, claims, and validation results."""
    def __init__(self):
        self.evidence_items: Dict[str, EvidenceItem] = {}
        self.claims: List[ClaimEntry] = []
        self.stage_summaries: Dict[int, Dict[str, Any]] = {
            i: {
                "stage": i,
                "name": STAGE_NAMES[i],
                "short_title": STAGE_SHORT_TITLES[i],
                "status": "pending",  # pending, running, completed, skipped, failed
                "source_count": 0,
                "message": "",
                "evidence_ids": [],
                "skip_reason": None,
                "error": None
            }
            for i in range(1, 8)
        }
        self.overall_confidence: float = 0.0
        self.overall_decision: str = "ABSTAIN"
        self.contradictions_detected: List[str] = []

    def add_evidence(self, item: EvidenceItem):
        self.evidence_items[item.evidence_id] = item
        stage_info = self.stage_summaries.get(item.stage)
        if stage_info:
            if item.evidence_id not in stage_info["evidence_ids"]:
                stage_info["evidence_ids"].append(item.evidence_id)
            stage_info["source_count"] = len(stage_info["evidence_ids"])

    def get_evidence_for_stage(self, stage: int) -> List[EvidenceItem]:
        return [
            ev for ev in self.evidence_items.values()
            if ev.stage == stage
        ]

    def record_stage_status(
        self,
        stage: int,
        status: str,
        message: str = "",
        skip_reason: Optional[str] = None,
        error: Optional[str] = None
    ):
        if stage in self.stage_summaries:
            self.stage_summaries[stage]["status"] = status
            self.stage_summaries[stage]["message"] = message
            if skip_reason:
                self.stage_summaries[stage]["skip_reason"] = skip_reason
            if error:
                self.stage_summaries[stage]["error"] = error

    def get_distinct_domains(self) -> List[str]:
        domains = set()
        for ev in self.evidence_items.values():
            if ev.domain and ev.domain not in {"unknown", "external-source"}:
                domains.add(ev.domain)
        return sorted(list(domains))

    def compute_summary_counts(self) -> Dict[str, int]:
        verified = sum(1 for c in self.claims if c.verdict == VERDICT_VERIFIED)
        partially = sum(1 for c in self.claims if c.verdict == VERDICT_PARTIALLY_VERIFIED)
        contradicted = sum(1 for c in self.claims if c.verdict == VERDICT_CONTRADICTED)
        unverified = sum(1 for c in self.claims if c.verdict == VERDICT_UNVERIFIED)
        return {
            "verified": verified,
            "partially_verified": partially,
            "contradicted": contradicted,
            "unverified": unverified,
            "total_claims": len(self.claims)
        }

    def to_dict(self) -> Dict[str, Any]:
        counts = self.compute_summary_counts()
        return {
            "claims": [c.to_dict() for c in self.claims],
            "evidence": {k: v.to_dict() for k, v in self.evidence_items.items()},
            "stage_summaries": self.stage_summaries,
            "overall_confidence": round(self.overall_confidence, 3),
            "overall_decision": self.overall_decision,
            "counts": counts,
            "contradictions_detected": self.contradictions_detected,
            "distinct_domains": self.get_distinct_domains()
        }


# ============================================================
# CLAIM DECOMPOSITION HELPER
# ============================================================

def split_into_atomic_claims(text: str) -> List[str]:
    """
    Deterministically extracts clear atomic factual assertions from an answer.
    Preserves numbers, names, entities, and statements.
    """
    if not text:
        return []

    clean_text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    clean_text = re.sub(r"^\s*[-*•]\s*", "", clean_text, flags=re.MULTILINE)

    # Split into sentences or numbered items
    raw_lines = clean_text.splitlines()
    candidates = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        # Numbered list matching
        num_match = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if num_match:
            candidate = num_match.group(1).strip()
            if candidate:
                candidates.append(candidate)
            continue

        # If line has a bullet label like "0-60 mph Acceleration: The tri-motor..."
        # Extract the substantive statement after the colon
        colon_match = re.match(r"^([^:]{2,35}):\s+(.{20,})$", line)
        if colon_match:
            candidates.append(colon_match.group(2).strip())
            continue

        # Split line by sentence terminators
        sentences = re.split(r"(?<=[.!?])\s+", line)
        for s in sentences:
            s = s.strip()
            if s and len(s) > 15:
                candidates.append(s)

    # Filter out conversational noise, structural headers, or meta-commentary
    noise_patterns = [
        r"^in short:?",
        r"^as an ai",
        r"^evidence \d+",
        r"^based on the (document|evidence)",
        r"^according to",
        r"^i hope this helps",
        r"^let me know",
        r"^note that",
        r"^here is",
        r"^summary:",
        r"^where the .+ wins:?$",
        r"^here is how",
        r"^key performance areas",
        r".*compare in key performance.*"
    ]

    filtered_claims = []
    for c in candidates:
        c_clean = c.strip(" .;:*#")
        if len(c_clean) < 18:
            continue
        # Skip pure headers ending in colon
        if c.endswith(":") or c.endswith(":*"):
            continue
        c_lower = c_clean.lower()
        if any(re.match(pat, c_lower) for pat in noise_patterns):
            # Clean off the leading phrase if rest is substantial
            cleaned = re.sub(r"^(in short:?|based on the (document|evidence),?|according to [^,]+,?)\s*", "", c_clean, flags=re.I).strip()
            if len(cleaned) < 20 or any(re.match(pat, cleaned.lower()) for pat in noise_patterns):
                continue
            c_clean = cleaned

        # Avoid duplicates
        if c_clean not in filtered_claims:
            filtered_claims.append(c_clean)

    return filtered_claims[:8]  # Max 8 discrete claims for bounded computation

