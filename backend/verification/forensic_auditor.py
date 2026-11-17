"""
ECRAG Forensic Auditor Module.

Implements two state-of-the-art accountability features:
1. Anti-Sycophancy Presupposition Shield:
   Detects manipulative, biased, or counter-factual user presuppositions
   (e.g., "Why does drinking bleach cure COVID?", "Why did NASA fake the moon landing?",
   "Tesla Plaid loses to an Alto, right?"), audits the premise against Tier-1 facts,
   and injects a non-sycophantic factual rebuttal directive.

2. Sentence-Level Truth Heatmap:
   Aligns candidate answer sentences to atomic claims in the ClaimLedger,
   generating an interactive, color-coded factual provenance display
   (Green = Tier-1 Verified, Yellow = Partially Verified/Secondary, Red = Contradicted/Unverified).
"""

import re
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from .claim_ledger import (
    ClaimLedger,
    ClaimEntry,
    VERDICT_VERIFIED,
    VERDICT_PARTIALLY_VERIFIED,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIED,
    STAGE_NAMES
)


# ============================================================
# 1. ANTI-SYCOPHANCY PRESUPPOSITION SHIELD
# ============================================================

class AntiSycophancyShield:
    """
    Detects and defends against user-manipulation and sycophancy traps.
    Ensures the AI never rationalizes or agrees with false presuppositions.
    """

    KNOWN_DEBUNKED_PATTERNS = [
        # Health & Science Myths
        (r"\b(?:drinking|ingesting|inject(?:ing|ed)?)\s+(?:bleach|disinfectant)\b", "Drinking or injecting bleach/disinfectants is toxic and medically lethal; it does not cure any viral infection."),
        (r"\b(?:vaccines?|vaccination)\s+(?:causes?|leads? to)\s+autism\b|\bautism\s+(?:caused|triggered)\s+by\s+vaccin", "Extensive global scientific studies involving millions of children have conclusively refuted any link between vaccines and autism."),
        (r"\b5g\s+(?:radiation|towers?|networks?)\s+(?:causes?|spreads?|creates?)\s+(?:covid|illness|disease|cancer|virus)\b|\b(?:covid|disease|illness)\s+(?:caused|spread)\s+by\s+5g\b", "5G radio waves are non-ionizing radiation and physically incapable of creating or transmitting biological viruses or illnesses."),
        (r"\b(?:earth|world)\s+is\s+(?:flat|stationary|dome)\b|\b(?:is\s+the\s+)?(?:earth|world)\s+(?:is\s+)?(?:flat|dome)\b|\bflat\s+earth\b", "The Earth is an oblate spheroid confirmed by thousands of years of astronomy, satellite imagery, and physics."),
        (r"\b(?:nasa|apollo)\s+(?:did\s+fake|faked|staged|hoaxed)\b|\b(?:did\s+)?(?:nasa|apollo)\s+(?:fake|stage|hoax)\b|\bmoon\s+landing\s+(?:was\s+)?(?:faked|staged|a\s+hoax)\b", "The Apollo Moon landings are verified historical facts confirmed by independent radar, laser retroreflectors, and international space agencies."),
        (r"\b(?:plaid|model s plaid)\s+(?:loses to|slower than|beaten by)\s+(?:an?\s+)?(?:alto|swift|wagon r|civic|corolla|prius)\b", "A Tesla Model S Plaid (0-60 in 1.99s, 1020 hp) significantly outperforms commuter vehicles in all acceleration and power benchmarks."),
    ]

    LEADING_QUESTION_PATTERNS = [
        # "Why does X...", "Why is X...", "Why did X..."
        r"^(?:why|how)\s+(?:does|did|is|was|are|were|can|would)\s+(.+?)(?:\?|$)",
        # "Explain how X...", "Prove that X...", "Confirm that X..."
        r"^(?:explain|describe|show|prove|confirm|clarify|demonstrate)\s+(?:why|how|that)\s+(.+?)(?:\?|$)",
        # "Isn't it true that X...", "Is it a fact that X..."
        r"^(?:isn't it true that|is it true that|is it a fact that)\s+(.+?)(?:,\s*(?:confirm|explain|prove|right)\b|\?|$)",
        # "X, right?", "X, isn't it?"
        r"^(.+?),\s*(?:right|isn't it|correct|true)\s*\?*$",
    ]

    @classmethod
    def detect_presupposition(cls, question: str) -> Optional[str]:
        """Extracts the underlying presupposition proposition from a leading question."""
        q = re.sub(r"\s+", " ", str(question or "")).strip()
        q_lower = q.lower()

        # Check for known debunked tropes first
        for pat, rebuttal in cls.KNOWN_DEBUNKED_PATTERNS:
            if re.search(pat, q_lower):
                m = re.search(pat, q_lower)
                return m.group(0)

        # Check leading question syntax
        for pat in cls.LEADING_QUESTION_PATTERNS:
            m = re.match(pat, q, flags=re.I)
            if m:
                premise = m.group(1).strip(" ?.,!")
                # Avoid trivial conversational prefixes
                if len(premise.split()) >= 3 and not any(premise.lower().startswith(w) for w in ["the weather", "you think", "i am", "we can"]):
                    return premise

        return None

    @classmethod
    def audit_query(
        cls,
        question: str,
        retrieved_evidence: Optional[List[Dict[str, Any]]] = None,
        ai_chat_fn=None
    ) -> Dict[str, Any]:
        """
        Audits the user query for sycophancy traps, leading questions, and false presuppositions.
        Returns a structured audit report with directives for the generation stage.
        """
        q = str(question or "").strip()
        q_lower = q.lower()
        premise = cls.detect_presupposition(q)

        report = {
            "is_leading": False,
            "presupposition": "",
            "verdict": "NEUTRAL",
            "is_contradicted": False,
            "rebuttal_explanation": "",
            "directive": "",
            "shield_activated": False
        }

        if not premise:
            return report

        report["is_leading"] = True
        report["presupposition"] = premise

        # 1. Deterministic Known Myths / Contradictions
        for pat, rebuttal in cls.KNOWN_DEBUNKED_PATTERNS:
            if re.search(pat, q_lower):
                report["is_contradicted"] = True
                report["verdict"] = "CONTRADICTED_PREMISE"
                report["rebuttal_explanation"] = rebuttal
                report["shield_activated"] = True
                report["directive"] = (
                    f"ANTI-SYCOPHANCY SHIELD ACTIVATED:\n"
                    f"The user's question presupposes that '{premise}', which is demonstrably false and contradicted by empirical consensus.\n"
                    f"CRITICAL INSTRUCTION: Do NOT validate, indulge, or apologize for rejecting this false premise. "
                    f"Directly and politely refute the premise at the very beginning of your answer using verified facts: {rebuttal}"
                )
                return report

        # 2. Evidence Corpus Contradiction Inspection
        if retrieved_evidence:
            corpus_text = " ".join([
                f"{e.get('title', '')} {e.get('snippet', '')}"
                for e in retrieved_evidence
            ]).lower()

            refutation_terms = ["myth", "debunked", "false", "hoax", "conspiracy", "untrue", "no evidence", "disproven", "refuted"]
            premise_tokens = set(re.findall(r"\b[a-z]{4,}\b", premise.lower()))
            has_token_overlap = any(t in corpus_text for t in premise_tokens)
            has_refutation = any(term in corpus_text for term in refutation_terms)

            if has_token_overlap and has_refutation:
                report["is_contradicted"] = True
                report["verdict"] = "DISPUTED_OR_CONTRADICTED_PREMISE"
                report["rebuttal_explanation"] = f"Independent evidence indicates the premise '{premise}' is disputed or recognized as a debunked claim."
                report["shield_activated"] = True
                report["directive"] = (
                    f"ANTI-SYCOPHANCY SHIELD ACTIVATED:\n"
                    f"The user's question contains a leading presupposition: '{premise}'. "
                    f"Retrieved independent evidence indicates this premise is unverified or contested. "
                    f"Do NOT uncritically adopt the user's framing. Clarify the factual status of the premise upfront before addressing the query."
                )
                return report

        # 3. Leading but not overtly contradicted
        report["verdict"] = "LEADING_PREMISE"
        report["directive"] = (
            f"OBJECTIVITY GUARDRAIL: The user phrased the question with a leading assumption ('{premise}'). "
            f"Remain strictly neutral and grounded in verified evidence; do not sycophantically affirm the premise unless verified by authoritative sources."
        )
        return report


# ============================================================
# 2. SENTENCE-LEVEL TRUTH HEATMAP GENERATOR
# ============================================================

class TruthHeatmapRenderer:
    """
    Maps generated response text to ClaimLedger claims sentence by sentence,
    producing an interactive, color-coded factual provenance heatmap.
    """

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Splits an answer into discrete presentation sentences/statements."""
        if not text:
            return []
        
        # Split by paragraph first to preserve block structure
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        sentences = []
        for p in paragraphs:
            # If line is a markdown header or bullet point, treat line as a unit
            if re.match(r"^(?:#+|-|\*|\d+\.)\s+", p):
                sentences.append(p)
            else:
                # Split regular sentences on period/exclamation/question mark followed by space and capital
                sub = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", p)
                for s in sub:
                    s_clean = s.strip()
                    if s_clean:
                        sentences.append(s_clean)
        return sentences

    @classmethod
    def align_sentences_to_claims(
        cls,
        answer_text: str,
        claim_ledger: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Aligns each sentence of the candidate answer to the closest verified claim in the ledger.
        """
        sentences = cls.split_sentences(answer_text)
        if not sentences:
            return []

        claims = []
        if claim_ledger and isinstance(claim_ledger, dict):
            claims = claim_ledger.get("claims", [])

        aligned = []
        for idx, sentence in enumerate(sentences):
            # Check for structural / conversational sentences
            clean_s = re.sub(r"^(?:#+|-|\*|\d+\.)\s+", "", sentence).strip()
            s_tokens = set(re.findall(r"\b[a-z]{3,}\b", clean_s.lower()))

            best_claim = None
            best_score = 0.0

            for c in claims:
                c_text = c.get("claim_text", "")
                c_tokens = set(re.findall(r"\b[a-z]{3,}\b", c_text.lower()))
                if not c_tokens or not s_tokens:
                    continue
                intersection = s_tokens & c_tokens
                # Jaccard / Overlap score
                score = len(intersection) / max(1, min(len(s_tokens), len(c_tokens)))
                if score > best_score:
                    best_score = score
                    best_claim = c

            # If match exceeds threshold, link to claim
            if best_claim and best_score >= 0.28:
                aligned.append({
                    "sentence_index": idx,
                    "text": sentence,
                    "verdict": best_claim.get("verdict", VERDICT_UNVERIFIED),
                    "confidence": best_claim.get("confidence", 0.0),
                    "matched_claim": best_claim.get("claim_text", ""),
                    "reasoning": best_claim.get("reasoning", ""),
                    "citations": best_claim.get("supporting_citations", [])
                })
            else:
                # Neutral / connective sentence without individual factual claim
                aligned.append({
                    "sentence_index": idx,
                    "text": sentence,
                    "verdict": "NEUTRAL",
                    "confidence": None,
                    "matched_claim": "",
                    "reasoning": "Conversational framing or general transition.",
                    "citations": []
                })

        return aligned

    @classmethod
    def generate_truth_heatmap_html(
        cls,
        answer_text: str,
        claim_ledger: Optional[Dict[str, Any]],
        element_id: str = "truth_heatmap"
    ) -> str:
        """
        Generates production-grade HTML + CSS for the interactive Truth Heatmap.
        """
        aligned_sentences = cls.align_sentences_to_claims(answer_text, claim_ledger)
        if not aligned_sentences:
            return f"<p>{answer_text}</p>"

        # Compute summary stats
        verified_count = sum(1 for s in aligned_sentences if s["verdict"] == VERDICT_VERIFIED)
        partial_count = sum(1 for s in aligned_sentences if s["verdict"] == VERDICT_PARTIALLY_VERIFIED)
        unverified_count = sum(1 for s in aligned_sentences if s["verdict"] in (VERDICT_UNVERIFIED, VERDICT_CONTRADICTED))
        total_factual = verified_count + partial_count + unverified_count

        rendered_spans = []
        for item in aligned_sentences:
            v = item["verdict"]
            text = item["text"]
            reason = item["reasoning"] or ""
            cites = item["citations"]

            cite_info = ""
            if cites:
                primary_domain = cites[0].get("domain") or "verified source"
                cite_info = f" • Source: {primary_domain}"

            if v == VERDICT_VERIFIED:
                bg = "rgba(16, 185, 129, 0.10)"
                border = "#10b981"
                badge = f'<span style="background: rgba(16, 185, 129, 0.25); color: #10b981; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-left: 6px;">✅ VERIFIED{cite_info}</span>'
            elif v == VERDICT_PARTIALLY_VERIFIED:
                bg = "rgba(245, 158, 11, 0.10)"
                border = "#f59e0b"
                badge = f'<span style="background: rgba(245, 158, 11, 0.25); color: #f59e0b; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-left: 6px;">⚠️ PARTIALLY VERIFIED</span>'
            elif v == VERDICT_CONTRADICTED:
                bg = "rgba(239, 68, 68, 0.15)"
                border = "#ef4444"
                badge = f'<span style="background: rgba(239, 68, 68, 0.25); color: #ef4444; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-left: 6px;">❌ CONTRADICTED</span>'
            elif v == VERDICT_UNVERIFIED:
                bg = "rgba(239, 68, 68, 0.08)"
                border = "#f87171"
                badge = f'<span style="background: rgba(239, 68, 68, 0.20); color: #f87171; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-left: 6px;">❓ UNVERIFIED</span>'
            else:
                bg = "transparent"
                border = "transparent"
                badge = ""

            tooltip_title = f"{v}: {reason}" if reason else v

            # If text is markdown header or bullet, format accordingly
            is_bullet = text.startswith(("- ", "* ", "1. ", "2. ", "3. "))
            margin = "margin: 4px 0;" if is_bullet else "margin: 2px 0; display: inline;"

            span_html = (
                f'<span title="{tooltip_title}" style="'
                f'background: {bg}; '
                f'border-bottom: 2px solid {border}; '
                f'padding: 2px 4px; '
                f'border-radius: 4px; '
                f'{margin} '
                f'line-height: 1.7; '
                f'display: inline-block;">'
                f'{text}{badge}'
                f'</span> '
            )
            rendered_spans.append(span_html)

        full_content = "".join(rendered_spans)

        html = f"""
<div id="{element_id}" style="
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
    padding: 16px;
    margin: 12px 0;
    color: #f1f5f9;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13.5px;
">
    <!-- Header & Legend Bar -->
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px; margin-bottom: 12px;">
        <div style="font-weight: 700; font-size: 12.5px; letter-spacing: 0.3px; display: flex; align-items: center; gap: 6px;">
            <span>🔬</span> SENTENCE-LEVEL TRUTH HEATMAP
        </div>
        <div style="display: flex; gap: 8px; font-size: 10.5px; font-weight: 600;">
            <span style="color: #10b981; background: rgba(16,185,129,0.15); padding: 2px 6px; border-radius: 4px;">🟢 {verified_count} Verified</span>
            <span style="color: #f59e0b; background: rgba(245,158,11,0.15); padding: 2px 6px; border-radius: 4px;">🟡 {partial_count} Partial</span>
            <span style="color: #ef4444; background: rgba(239,68,68,0.15); padding: 2px 6px; border-radius: 4px;">🔴 {unverified_count} Unverified</span>
        </div>
    </div>

    <!-- Interactive Highlighted Text -->
    <div style="line-height: 1.8; color: #e2e8f0;">
        {full_content}
    </div>

    <!-- Inspector Footer Note -->
    <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); font-size: 10.5px; color: #64748b;">
        ℹ️ Each statement is cross-referenced with the 7-Stage Evidence Ledger. Hover over highlighted sentences to view provenance citations.
    </div>
</div>
"""
        return html
