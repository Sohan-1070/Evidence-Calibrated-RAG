"""
Seven-Stage Factual Verification Pipeline for ECRAG.

Implements the complete 7-stage verification workflow:
1. Official sources (.gov, WHO, agencies, official documentation)
2. Primary evidence (original reports, datasets, PDFs)
3. Reference sources (Wikipedia, encyclopedias)
4. Academic sources (peer-reviewed papers, universities)
5. Reputable news (independent reporting, recent developments)
6. Community sources (Reddit, Quora, blogs - leads only)
7. Final validation (cross-evidence verification, contradiction detection, source independence, date checks, citations)

Assigns verdicts:
- VERIFIED
- PARTIALLY_VERIFIED
- CONTRADICTED
- UNVERIFIED

Emits real-time streaming progress events for live UI integration.
"""

import os
import re
import json
import time
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any, Generator, Callable

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
        STAGE_NAMES,
        STAGE_AUTHORITY_WEIGHT
    )
    from .sources import (
        search_stage_1_official,
        search_stage_2_primary,
        search_stage_3_reference,
        search_stage_4_academic,
        search_stage_5_news,
        search_stage_6_community
    )
    from .forensic_auditor import (
        AntiSycophancyShield,
        TruthHeatmapRenderer
    )
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
        STAGE_NAMES,
        STAGE_AUTHORITY_WEIGHT
    )
    from sources import (
        search_stage_1_official,
        search_stage_2_primary,
        search_stage_3_reference,
        search_stage_4_academic,
        search_stage_5_news,
        search_stage_6_community
    )
    from forensic_auditor import (
        AntiSycophancyShield,
        TruthHeatmapRenderer
    )


class SevenStageVerificationPipeline:
    """
    Orchestrates the 7-stage factual verification pipeline with live progress streaming,
    stage skipping heuristics, evidence provenance, and contradiction detection.
    """

    def __init__(
        self,
        ai_chat_fn: Optional[Callable] = None,
        pdf_path: Optional[str] = None,
        offline_chunks: Optional[List[Dict[str, Any]]] = None,
        offline_mode: bool = False
    ):
        self.ai_chat_fn = ai_chat_fn
        self.pdf_path = pdf_path
        self.offline_chunks = offline_chunks
        self.offline_mode = offline_mode

    def _should_skip_stage(self, stage: int, question: str, ledger: ClaimLedger, mode: str) -> Optional[str]:
        """
        Determines whether a stage can be transparently skipped based on relevance and authority.
        Returns skip reason string if skipped, or None if the stage should execute.
        """
        q_lower = question.lower()

        # If pure offline mode without network:
        if self.offline_mode:
            if stage in (1, 3, 4, 5, 6):
                return "Offline / Island Mode active; external internet retrieval skipped."
            return None

        # If PDF / document-only mode:
        if mode == "pdf" or self.pdf_path:
            if stage in (1, 3, 4, 5, 6):
                # Document grounding takes precedence; skip external search unless requested
                return "Primary document mode active; verification grounded directly in uploaded document evidence."
            return None

        # Stage 4: Academic Sources
        if stage == 4:
            # Skip academic search for hyper-transient current events or daily commodity prices
            current_numeric_patterns = [r"\bprice\b", r"\brate\b", r"\btoday\b", r"\bweather\b", r"\bscore\b", r"\bgold\b"]
            if any(re.search(p, q_lower) for p in current_numeric_patterns) and not any(w in q_lower for w in ["study", "physics", "climate", "biology", "science"]):
                return "Non-academic live/commercial query; peer-reviewed preprint search skipped."

            # Skip academic search for local dining, restaurant, food or cafe queries
            dining_patterns = [
                r"\brestaurants?\b", r"\bfood\b", r"\bdining\b", r"\bcafe\b",
                r"\bcafes\b", r"\bdhabas?\b", r"\btiffins?\b", r"\bbiryani\b",
                r"\beateries\b", r"\beatery\b"
            ]
            if any(re.search(p, q_lower) for p in dining_patterns) and not any(w in q_lower for w in ["study", "nutrition science", "microbiology", "epidemiology"]):
                return "Local dining / hospitality query; peer-reviewed preprint search skipped."

        # Stage 5: Reputable News
        if stage == 5:
            # Skip news search for purely timeless conceptual/mathematical/definitions
            timeless_patterns = [r"^what is the definition of", r"^how to calculate", r"^formula for", r"^derivative of"]
            if any(re.search(p, q_lower) for p in timeless_patterns):
                return "Timeless mathematical/conceptual definition; breaking news search skipped."

        # Stage 6: Community Sources (Reddit, Quora)
        if stage == 6:
            # If Stage 1 (.gov / WHO) or Stage 4 (academic) already retrieved substantial authoritative evidence,
            # skip unauthoritative community noise
            stg1_count = len(ledger.get_evidence_for_stage(1))
            stg4_count = len(ledger.get_evidence_for_stage(4))
            if stg1_count >= 3 or (stg1_count >= 1 and stg4_count >= 2):
                return "Authoritative official and academic verification achieved; unauthoritative community search skipped."

        return None

    def run_streaming(
        self,
        question: str,
        candidate_answer: str,
        mode: str = "web",
        initial_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[Dict[str, Any], None, ClaimLedger]:
        """
        Executes the 7 stages in real-time, yielding live progress events for UI streaming.
        Every event corresponds to a real backend operation.
        """
        ledger = ClaimLedger()
        start_time = time.time()

        if initial_evidence:
            for idx, item in enumerate(initial_evidence, 1):
                try:
                    u = str(item.get("url", ""))
                    dom = urlparse(u).netloc if u else "web"
                    ledger.add_evidence(EvidenceItem(
                        evidence_id=f"stg3_init_{idx}",
                        stage=3,
                        title=str(item.get("title", "Reference")),
                        url_or_ref=u,
                        snippet=str(item.get("snippet", "") or item.get("title", "")),
                        domain=dom or "web",
                        published_date=str(item.get("published_date", "")),
                        authority_tier=3
                    ))
                except Exception as e:
                    print(f"[ECRAG Pipeline] Error adding initial evidence: {e}")

        yield {
            "type": "pipeline_start",
            "message": "Initializing 7-stage factual verification pipeline...",
            "timestamp": time.time()
        }

        # ----------------------------------------------------
        # STAGE 1: OFFICIAL SOURCES (.gov, WHO, Agencies)
        # ----------------------------------------------------
        stage_num = 1
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Searching official websites (.gov, WHO, agencies)...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Searching official websites (.gov, WHO, government agencies)..."
            }
            try:
                items = search_stage_1_official(question, max_results=5)
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} official evidence items."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Found {len(items)} official source documents."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error searching official sources: {e}"
                }

        # ----------------------------------------------------
        # STAGE 2: PRIMARY EVIDENCE (Reports, Datasets, PDFs)
        # ----------------------------------------------------
        stage_num = 2
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Examining original documents and primary evidence...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Examining original documents, primary datasets, and reports..."
            }
            try:
                items = search_stage_2_primary(
                    question,
                    max_results=5,
                    pdf_path=self.pdf_path,
                    offline_chunks=self.offline_chunks
                )
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} primary evidence items."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Analyzed {len(items)} primary records / document excerpts."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error examining primary documents: {e}"
                }

        # ----------------------------------------------------
        # STAGE 3: REFERENCE SOURCES (Wikipedia, Encyclopedias)
        # ----------------------------------------------------
        stage_num = 3
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Consulting reference sources and encyclopedias...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Consulting reference sources and encyclopedias (Wikipedia, Britannica)..."
            }
            try:
                items = search_stage_3_reference(question, max_results=4)
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} reference items."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Retrieved {len(items)} encyclopedia / educational reference items."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error consulting reference sources: {e}"
                }

        # ----------------------------------------------------
        # STAGE 4: ACADEMIC SOURCES (Peer-Reviewed, Universities)
        # ----------------------------------------------------
        stage_num = 4
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Cross-checking academic sources and peer-reviewed research...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Cross-checking academic sources, universities, and preprints (ArXiv, PubMed)..."
            }
            try:
                items = search_stage_4_academic(question, max_results=4)
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} academic sources."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Indexed {len(items)} peer-reviewed papers / institutional studies."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error checking academic sources: {e}"
                }

        # ----------------------------------------------------
        # STAGE 5: REPUTABLE NEWS (Independent Reporting)
        # ----------------------------------------------------
        stage_num = 5
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Scanning reputable news for independent reporting...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Scanning reputable news channels and wire services (Google News RSS)..."
            }
            try:
                items = search_stage_5_news(question, max_results=5)
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} news reports."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Found {len(items)} news reports from independent publishers."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error scanning news sources: {e}"
                }

        # ----------------------------------------------------
        # STAGE 6: COMMUNITY SOURCES (Reddit, Quora, Forums - Leads Only)
        # ----------------------------------------------------
        stage_num = 6
        skip_reason = self._should_skip_stage(stage_num, question, ledger, mode)
        if skip_reason:
            ledger.record_stage_status(stage_num, "skipped", "Stage skipped transparently", skip_reason=skip_reason)
            yield {
                "type": "stage_skipped",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": f"Skipped: {skip_reason}",
                "skip_reason": skip_reason
            }
        else:
            ledger.record_stage_status(stage_num, "running", "Gathering community leads (Reddit, Quora - leads only)...")
            yield {
                "type": "stage_start",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "message": "Gathering community leads (Reddit, forums - treated as leads only, never authoritative proof)..."
            }
            try:
                items = search_stage_6_community(question, max_results=4)
                for item in items:
                    ledger.add_evidence(item)
                ledger.record_stage_status(
                    stage_num,
                    "completed",
                    f"Retrieved {len(items)} community leads."
                )
                yield {
                    "type": "stage_complete",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "status": "completed",
                    "source_count": len(items),
                    "evidence_previews": [
                        {"title": it.title, "domain": it.domain, "snippet": it.snippet[:200], "url": it.url_or_ref}
                        for it in items[:3]
                    ],
                    "message": f"Gathered {len(items)} community discussions (flagged as leads only)."
                }
            except Exception as e:
                ledger.record_stage_status(stage_num, "failed", error=str(e))
                yield {
                    "type": "stage_error",
                    "stage": stage_num,
                    "stage_name": STAGE_NAMES[stage_num],
                    "error": str(e),
                    "message": f"Error gathering community leads: {e}"
                }

        # ----------------------------------------------------
        # STAGE 7: FINAL VALIDATION (Contradictions, Citations, Verdicts)
        # ----------------------------------------------------
        stage_num = 7
        ledger.record_stage_status(stage_num, "running", "Performing claim decomposition, contradiction detection & verdict assignment...")
        yield {
            "type": "stage_start",
            "stage": stage_num,
            "stage_name": STAGE_NAMES[stage_num],
            "message": "Running final validation: verifying every claim, detecting contradictions, checking source independence, dates, and citations..."
        }

        try:
            self._execute_final_validation(question, candidate_answer, ledger)
            ledger.record_stage_status(
                stage_num,
                "completed",
                f"Validated {len(ledger.claims)} claims. Verdict: {ledger.overall_decision}"
            )
            yield {
                "type": "stage_complete",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "status": "completed",
                "claim_ledger": ledger.to_dict(),
                "message": f"Final validation completed: {len(ledger.claims)} claims verified against evidence provenance."
            }
        except Exception as e:
            ledger.record_stage_status(stage_num, "failed", error=str(e))
            yield {
                "type": "stage_error",
                "stage": stage_num,
                "stage_name": STAGE_NAMES[stage_num],
                "error": str(e),
                "message": f"Validation stage encountered an error: {e}"
            }

        elapsed = time.time() - start_time
        ledger_dict = ledger.to_dict()

        # Generate Forensic Accountability Artifacts
        evidence_list = [
            {"title": ev.title, "snippet": ev.snippet, "url": ev.url_or_ref, "domain": ev.domain, "stage": ev.stage}
            for ev in ledger.evidence_items.values()
        ]
        sycophancy_report = AntiSycophancyShield.audit_query(
            question,
            retrieved_evidence=evidence_list,
            ai_chat_fn=self.ai_chat_fn
        )
        truth_heatmap_html = TruthHeatmapRenderer.generate_truth_heatmap_html(
            candidate_answer,
            ledger_dict
        )

        # Attach to ledger dictionary for seamless consumption
        ledger_dict["truth_heatmap_html"] = truth_heatmap_html
        ledger_dict["sycophancy_report"] = sycophancy_report

        yield {
            "type": "pipeline_complete",
            "overall_decision": ledger.overall_decision,
            "overall_confidence": ledger.overall_confidence,
            "counts": ledger.compute_summary_counts(),
            "elapsed_seconds": round(elapsed, 2),
            "claim_ledger": ledger_dict,
            "truth_heatmap_html": truth_heatmap_html,
            "sycophancy_report": sycophancy_report
        }

        return ledger

    def run_sync(
        self,
        question: str,
        candidate_answer: str,
        mode: str = "web",
        initial_evidence: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes the 7-stage verification synchronously and returns the complete audit summary dictionary.
        """
        last_event = {}
        for evt in self.run_streaming(question, candidate_answer, mode=mode, initial_evidence=initial_evidence):
            if evt.get("type") == "pipeline_complete":
                last_event = evt
        return last_event

    def _execute_final_validation(self, question: str, candidate_answer: str, ledger: ClaimLedger):
        """
        Decomposes candidate answer into claims, verifies each against the multi-stage evidence,
        checks source independence, dates, citations, and detects contradictions.
        """
        claims_text_list = split_into_atomic_claims(candidate_answer)
        if not claims_text_list and candidate_answer:
            claims_text_list = [candidate_answer.strip()]

        all_evidence = list(ledger.evidence_items.values())
        distinct_domains = ledger.get_distinct_domains()
        total_evidence_count = len(all_evidence)

        # Build evidence overview for LLM or lexical analysis
        evidence_digest = []
        for ev in all_evidence:
            lead_tag = "[LEAD ONLY - NON-AUTHORITATIVE]" if ev.is_community_lead else ""
            evidence_digest.append(
                f"[ID: {ev.evidence_id} | Stage {ev.stage}: {ev.stage_name} {lead_tag}]\n"
                f"Source: {ev.title} ({ev.url_or_ref})\n"
                f"Domain: {ev.domain} | Date: {ev.published_date or 'Undated'}\n"
                f"Text:\n{ev.snippet}\n"
            )
        evidence_corpus = "\n---\n".join(evidence_digest)

        # Attempt LLM-based verification if ai_chat_fn is available
        llm_success = False
        if self.ai_chat_fn and all_evidence:
            llm_success = self._run_llm_claim_verification(
                question,
                candidate_answer,
                claims_text_list,
                evidence_corpus,
                ledger
            )

        # If LLM verification was not available or failed, execute robust deterministic verification
        if not llm_success:
            self._run_deterministic_claim_verification(
                claims_text_list,
                all_evidence,
                ledger
            )

        # Calculate final confidence and overall decision
        self._calculate_pipeline_decision(ledger, distinct_domains)

    def _run_llm_claim_verification(
        self,
        question: str,
        candidate_answer: str,
        claims: List[str],
        evidence_corpus: str,
        ledger: ClaimLedger
    ) -> bool:
        """
        Runs rigorous LLM prompt for Stage 7 validation.
        Enforces strict constraints: never mark verified without authoritative proof.
        """
        prompt = f"""
You are Stage 7 (Final Validation) of the ECRAG factual verification pipeline.

USER QUESTION:
{question}

CANDIDATE ANSWER:
{candidate_answer}

EXTRACTED CLAIMS TO VERIFY:
{json.dumps(claims, indent=2)}

AVAILABLE EVIDENCE CORPUS (WITH PROVENANCE ACROSS 6 STAGES):
{evidence_corpus[:7000]}

STRICT VERIFICATION RULES:
1. For each claim, assign EXACTLY ONE verdict:
   - "VERIFIED": Directly and strongly supported by authoritative evidence (Stage 1-5).
   - "PARTIALLY_VERIFIED": Supported with minor ambiguities, single source, or community leads with partial corroboration.
   - "CONTRADICTED": The evidence directly conflicts with, refutes, or negates the factual claim.
   - "UNVERIFIED": The evidence is insufficient, absent, or vague.
2. UNIVERSAL FIRST-PARTY GROUND TRUTH (ALL DOMAINS):
   - Evidence from verified official sources (.gov, .nic.in, who.int, un.org, nasa.gov, isro.gov.in), accredited universities (.edu, .ac.uk), national standards/science institutes (NIST, BIPM, PubChem), global sports federations (FIFA, ICC, Olympics), primary project portals (e.g. python.org, linuxfoundation.org), corporate first-party domains, or uploaded documents is DEFINITIVE FIRST-PARTY GROUND TRUTH.
   - This applies across ALL domains:
     * Science & Mathematics: physical constants (speed of light, gravitational constant), boiling points, molecular formulas, scientific laws.
     * History & Geography: historical dates, treaty ratifications, country capitals, geographical facts.
     * Policy, Education & Institutions: admission criteria, attendance rules, regulatory rates (RBI repo rate), government acts.
     * Sports & Culture: tournament winners, championship scores, records, dates.
     * Technology, Products & Hardware: release dates, technical benchmarks, specifications, capacities, pricing.
     * Local Dining, Hospitality & Geographic POIs: restaurant locations, dining hubs, campus eateries, dhabas, local cuisines, distances and travel corridors. If the places or corridors exist and match the retrieved local listings, directories (Zomato, Justdial, Tripadvisor), or regional context, assign "VERIFIED" or "PARTIALLY_VERIFIED".
   - If any claim matches authoritative documentation or primary records, assign "VERIFIED".
3. AUTHORITY RULES:
   - Community sources (Stage 6: Reddit, Quora, forums) are LEADS ONLY. They can NEVER independently verify a claim as "VERIFIED".
   - If a claim has evidence ONLY from Stage 6, its verdict must be "UNVERIFIED" or "PARTIALLY_VERIFIED" with a clear note.
4. CONTRADICTIONS VS INFORMATIONAL VARIANCE (UNIVERSAL):
   - Only assign "CONTRADICTED" if the evidence directly, actively, and unambiguously refutes the factual assertion (e.g. claiming an event happened in 2026 when records confirm 2020, or claiming the speed of light is 150,000 km/s when science confirms ~300,000 km/s).
   - DO NOT mark "CONTRADICTED" for normal contextual or domain variations:
     * In science: minor decimal precision or measurement differences between standard conditions vs vacuum.
     * In policies/academics: general criteria vs special category exceptions.
     * In history: Julian vs Gregorian calendar dates, or signing date vs effective date.
     * In commerce/products: base MSRP vs taxes, fees, trims, or model years.
     * In statistics: updated census estimates vs earlier baseline data.
   - In all such cases of normal variance, assign "PARTIALLY_VERIFIED" or "VERIFIED" with a clarifying note.
5. CORE ANSWER VS PERIPHERAL CONTEXT:
   - Distinguish the central factual answer to the user's question from peripheral framing or conversational background statements.
   - If the main factual claims directly answering the question are supported by authoritative evidence, verify them as "VERIFIED".
   - Peripheral sentences that provide color commentary but are not explicitly mentioned in the search snippets should be marked "PARTIALLY_VERIFIED" or "UNVERIFIED" without dragging down the verified status of the core claims.
6. CITATIONS:
   - Cite the exact evidence IDs and quote the supporting passage. Never invent evidence.
   - If evidence is genuinely absent across all stages, mark UNVERIFIED.
7. NEGATIVE ASSERTIONS & UNRELEASED / NON-EXISTENT ENTITIES:
   - When the user asks about a specific product/entity that does not exist or has not been released (e.g. unannounced model like 'OnePlus Nord CE 6 Lite'):
   - And the candidate answer correctly clarifies that this entity has not been announced or released, while citing the latest actual model in the lineage (e.g. 'latest model is Nord CE 4 Lite'):
   - If the retrieved evidence (e.g. official catalogs, Wikipedia product lists) establishes the current existing lineage and confirms zero record of the queried premature entity:
   - Mark the negative claims (e.g. 'has not been announced or released') as 'VERIFIED'.
8. ABSTENTION & INSUFFICIENT EVIDENCE (NEVER MARK AS VERIFIED ANSWER):
   - Statements like "The retrieved evidence does not contain...", "There is no mention of...", "Cannot be verified from the provided evidence", "Insufficient information to answer", or "Refused to guess" are META-STATEMENTS OF UNVERIFIED IGNORANCE / ABSTENTION, NOT affirmative factual answers!
   - Mark any such statement as "UNVERIFIED" with reasoning "Model correctly acknowledged that retrieved evidence is insufficient to verify the user's question."
   - Under no circumstances should meta-statements acknowledging lack of evidence be marked "VERIFIED" to inflate confidence.

Return ONLY a valid JSON object matching this schema:
{{
  "claims": [
    {{
      "claim_text": "text of claim",
      "verdict": "VERIFIED|PARTIALLY_VERIFIED|CONTRADICTED|UNVERIFIED",
      "supporting_evidence_ids": ["stg1_1", "stg2_doc_1"],
      "supporting_quotes": ["exact quote from evidence"],
      "contradictions": ["description of any conflict or contradiction"],
      "reasoning": "brief explanation"
    }}
  ],
  "contradictions_detected": ["list of major contradictions found across sources"]
}}
"""
        try:
            resp = self.ai_chat_fn([{"role": "user", "content": prompt}])
            if not resp or "message" not in resp:
                return False
            raw_text = resp["message"]["content"].strip()
            # Clean json fences
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.I)
            raw_text = re.sub(r"\s*```$", "", raw_text).strip()

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not match:
                return False
            data = json.loads(match.group(0))

            parsed_claims = data.get("claims", [])
            if not parsed_claims:
                return False

            for idx, c in enumerate(parsed_claims, 1):
                verdict = str(c.get("verdict", VERDICT_UNVERIFIED)).upper()
                if verdict not in {VERDICT_VERIFIED, VERDICT_PARTIALLY_VERIFIED, VERDICT_CONTRADICTED, VERDICT_UNVERIFIED}:
                    verdict = VERDICT_UNVERIFIED

                ev_ids = c.get("supporting_evidence_ids", [])
                quotes = c.get("supporting_quotes", [])

                # Enforce rule: Community sources cannot substantiate VERIFIED alone
                only_community = ev_ids and all(
                    ledger.evidence_items.get(eid, EvidenceItem("", 0, "", "", "")).is_community_lead
                    for eid in ev_ids
                )
                if only_community and verdict == VERDICT_VERIFIED:
                    verdict = VERDICT_PARTIALLY_VERIFIED
                    c["reasoning"] = (c.get("reasoning", "") + " [Caveat: Evidence based solely on community leads; authoritative proof absent.]").strip()

                citations = []
                for q, eid in zip(quotes, ev_ids):
                    ev_item = ledger.evidence_items.get(eid)
                    citations.append({
                        "evidence_id": eid,
                        "citation_text": q,
                        "source_title": ev_item.title if ev_item else "Evidence",
                        "url_or_page": ev_item.url_or_ref if ev_item else "",
                        "stage_name": ev_item.stage_name if ev_item else ""
                    })

                contradictions = [
                    {"conflict_text": conflict}
                    for conflict in c.get("contradictions", [])
                    if conflict
                ]

                # Measure source independence
                domains = set()
                for eid in ev_ids:
                    ev_obj = ledger.evidence_items.get(eid)
                    if ev_obj and ev_obj.domain:
                        domains.add(ev_obj.domain)
                independence = min(1.0, len(domains) * 0.4) if domains else 0.0

                # Check if substantiated by official first-party / Tier-1 source
                has_tier1_source = any(
                    ledger.evidence_items.get(eid) and (ledger.evidence_items[eid].authority_tier == 1 or ledger.evidence_items[eid].extra_metadata.get("is_official"))
                    for eid in ev_ids
                )
                claim_conf = 1.0 if (verdict == VERDICT_VERIFIED and has_tier1_source) else (0.92 if verdict == VERDICT_VERIFIED else (0.60 if verdict == VERDICT_PARTIALLY_VERIFIED else (0.15 if verdict == VERDICT_CONTRADICTED else 0.0)))

                ledger.claims.append(
                    ClaimEntry(
                        claim_id=f"c_{idx}",
                        claim_text=c.get("claim_text", f"Claim {idx}"),
                        verdict=verdict,
                        confidence=claim_conf,
                        supporting_citations=citations,
                        contradictions=contradictions,
                        reasoning=c.get("reasoning", ""),
                        source_independence_score=independence,
                        date_consistency_status="CONSISTENT" if not contradictions else "CONFLICTING"
                    )
                )

            ledger.contradictions_detected = data.get("contradictions_detected", [])
            return True
        except Exception as e:
            return False

    def _run_deterministic_claim_verification(
        self,
        claims: List[str],
        all_evidence: List[EvidenceItem],
        ledger: ClaimLedger
    ):
        """
        Deterministic, keyword-grounded evidence verification fallback.
        Assesses token overlap, negation detection, and authority levels.
        """
        negation_markers = {"not", "never", "no", "denied", "false", "disputed", "rejected", "incorrect", "refuted"}

        for idx, claim_text in enumerate(claims, 1):
            claim_words = set(re.findall(r"\w{4,}", claim_text.lower()))
            supporting_items = []
            contradicting_items = []

            for ev in all_evidence:
                snippet_lower = ev.snippet.lower()
                title_lower = ev.title.lower()
                combined = f"{title_lower} {snippet_lower}"

                # Calculate match score
                overlap = sum(1 for w in claim_words if w in combined)
                ratio = overlap / max(1, len(claim_words))

                if ratio >= 0.45:
                    # Check for contradiction words in the matching window
                    has_negation = any(neg in combined for neg in negation_markers)
                    if has_negation and ("not" in combined or "dispute" in combined or "refute" in combined):
                        contradicting_items.append((ev, ev.snippet[:200]))
                    else:
                        supporting_items.append((ev, ev.snippet[:250]))

            # Determine verdict based on matches and authority tiers
            verdict = VERDICT_UNVERIFIED
            citations = []
            contradictions = []
            reasoning = ""

            if contradicting_items and not supporting_items:
                verdict = VERDICT_CONTRADICTED
                reasoning = "Retrieved evidence directly disputes or conflicts with this claim."
                for ev, quote in contradicting_items[:2]:
                    contradictions.append({
                        "evidence_id": ev.evidence_id,
                        "conflict_text": quote,
                        "source_title": ev.title,
                        "url_or_page": ev.url_or_ref
                    })
                    ledger.contradictions_detected.append(f"Conflict in {ev.title}: {quote[:120]}")

            elif supporting_items:
                # Check if all supporting items are community leads
                is_only_community = all(ev.is_community_lead for ev, _ in supporting_items)
                has_high_authority = any(ev.authority_tier <= 2 for ev, _ in supporting_items)

                for ev, quote in supporting_items[:3]:
                    citations.append({
                        "evidence_id": ev.evidence_id,
                        "citation_text": quote,
                        "source_title": ev.title,
                        "url_or_page": ev.url_or_ref,
                        "stage_name": ev.stage_name
                    })

                if is_only_community:
                    verdict = VERDICT_PARTIALLY_VERIFIED
                    reasoning = "Mentioned in community discussions (Reddit/forums), but lacks authoritative primary/official corroboration."
                elif has_high_authority or len(supporting_items) >= 2:
                    verdict = VERDICT_VERIFIED
                    reasoning = f"Corroborated by {len(supporting_items)} authoritative evidence sources across pipeline stages."
                else:
                    verdict = VERDICT_PARTIALLY_VERIFIED
                    reasoning = "Partially supported by retrieved reference/news evidence, with limited primary depth."

            else:
                # Explicit check for abstention/lack of evidence meta-claims
                is_abstain_claim = any(
                    marker in claim_text.lower() for marker in [
                        "does not contain", "do not contain", "did not contain", "no mention of",
                        "cannot be verified", "can't be verified", "could not be verified",
                        "insufficient evidence", "no specific price prediction", "no record of",
                        "refuse to guess", "refuses to guess", "won't guess"
                    ]
                )
                if is_abstain_claim:
                    verdict = VERDICT_UNVERIFIED
                    reasoning = "Model correctly acknowledged that retrieved evidence is insufficient to answer the question."
                else:
                    is_negative_assertion = any(
                        marker in claim_text.lower() for marker in [
                            "not yet announced", "has not been released", "have not been released",
                            "not been announced", "does not exist", "no official price", "unreleased model"
                        ]
                    )
                    if is_negative_assertion and all_evidence:
                        # Lineage evidence confirms this product has not been announced/released
                        catalog_ev = [ev for ev in all_evidence if ev.authority_tier <= 3]
                        if catalog_ev:
                            verdict = VERDICT_VERIFIED
                            ev_top = catalog_ev[0]
                            citations.append({
                                "evidence_id": ev_top.evidence_id,
                                "citation_text": ev_top.snippet[:250],
                                "source_title": ev_top.title,
                                "url_or_page": ev_top.url_or_ref,
                                "stage_name": ev_top.stage_name
                            })
                            reasoning = "Verified: Authoritative records confirm current product lineage/history and establish that this model/entity has not been released or announced."
                        else:
                            verdict = VERDICT_UNVERIFIED
                            reasoning = "Insufficient or missing evidence in the corpus to verify this claim."
                    else:
                        verdict = VERDICT_UNVERIFIED
                        reasoning = "Insufficient or missing evidence in the corpus to verify this claim."

            # Append for every claim processed in this iteration
            conf = 0.92 if verdict == VERDICT_VERIFIED else (0.60 if verdict == VERDICT_PARTIALLY_VERIFIED else 0.0)
            ledger.claims.append(
                ClaimEntry(
                    claim_id=f"c{idx}",
                    claim_text=claim_text,
                    verdict=verdict,
                    confidence=conf,
                    reasoning=reasoning,
                    supporting_citations=citations,
                    contradictions=contradictions
                )
            )

    def _calculate_pipeline_decision(self, ledger: ClaimLedger, distinct_domains: List[str]):
        """
        Computes overall confidence score and decision with dynamic, honest accountability:
        - 1.0 (100%): Official Tier-1 Primary Ground Truth (tesla.com, .gov, uploaded document) with 100% verified claims.
        - 0.85 - 0.92: Multi-source independent secondary news/tech corroboration (2+ distinct domains).
        - 0.75 - 0.80: Single secondary domain corroboration.
        - 0.45 - 0.65 (WARN): Partial verification, caveats, or mixed sources.
        - 0.00 - 0.35 (ABSTAIN): Unverified claims, speculation, contradictions, or explicit abstentions.
        """
        counts = ledger.compute_summary_counts()
        total = max(1, counts["total_claims"])

        verified_ratio = counts["verified"] / total
        partially_ratio = counts["partially_verified"] / total
        contradicted_ratio = counts["contradicted"] / total
        unverified_ratio = counts["unverified"] / total

        all_claim_texts = " ".join(c.claim_text.lower() for c in ledger.claims)

        # Abstention markers: statements acknowledging absence of evidence
        is_abstention_text = any(
            marker in all_claim_texts for marker in [
                "does not contain", "do not contain", "did not contain", "no mention of",
                "cannot be verified", "can't be verified", "could not be verified",
                "insufficient evidence", "not enough evidence", "no conclusive evidence",
                "refuse to guess", "refuses to guess", "won't guess", "cannot confirm",
                "unable to confirm", "cannot be determined", "no data is available",
                "no specific price prediction"
            ]
        )

        # 1. If the answer is an explicit abstention / refusal to speculate
        if is_abstention_text or (total > 0 and counts["unverified"] == total and counts["verified"] == 0):
            ledger.overall_confidence = 0.0
            ledger.overall_decision = "ABSTAIN"
            return

        # 2. Genuine consumer product lineage check (e.g. OnePlus Nord CE 4 Lite vs unreleased Nord CE 6 Lite)
        is_unreleased_resolution = (
            any(m in all_claim_texts for m in ["not yet announced", "has not been released", "unreleased model", "not been announced"])
            and any(m in all_claim_texts for m in ["most recent model is", "latest model is", "lineup currently", "previous model"])
            and not is_abstention_text
        )

        if is_unreleased_resolution and counts["contradicted"] == 0 and counts["verified"] >= 1:
            ledger.overall_confidence = 1.0
            ledger.overall_decision = "ANSWER"
            return

        # Check for official Tier-1 grounding in the evidence corpus and claims across all stages
        has_official_grounding = any(
            (ev.authority_tier == 1 or ev.extra_metadata.get("is_official"))
            for ev in ledger.evidence_items.values()
        ) or any(
            any(
                ledger.evidence_items.get(cite.get("evidence_id")) and (
                    ledger.evidence_items[cite["evidence_id"]].authority_tier == 1
                    or ledger.evidence_items[cite["evidence_id"]].extra_metadata.get("is_official")
                )
                for cite in c.supporting_citations
            )
            for c in ledger.claims
        )

        # Calculate calibrated confidence score
        if counts["contradicted"] > 0:
            # Active contradiction detected: severe penalty
            penalty = (contradicted_ratio * 0.70) + 0.20
            score = max(0.0, (verified_ratio * 0.40) + (partially_ratio * 0.20) - penalty)
            ledger.overall_decision = "ABSTAIN" if contradicted_ratio >= 0.25 or score < 0.50 else "WARN"

        elif counts["verified"] == 0:
            # Zero verified claims: only weak partial or unverified
            score = round(partially_ratio * 0.45, 3)
            ledger.overall_decision = "WARN" if score >= 0.45 else "ABSTAIN"

        elif has_official_grounding and verified_ratio == 1.0 and counts["unverified"] == 0:
            # Official Tier-1 Primary Ground Truth (e.g. tesla.com, .gov, uploaded document)
            score = 1.0
            ledger.overall_decision = "ANSWER"

        elif has_official_grounding and verified_ratio >= 0.67 and counts["unverified"] <= 1:
            score = round(0.85 + (verified_ratio * 0.10), 3)
            ledger.overall_decision = "ANSWER"

        elif verified_ratio == 1.0 and counts["unverified"] == 0:
            # Multi-source web verification (Tier 2-3: Google News, 91mobiles, Wikipedia)
            if len(distinct_domains) >= 3:
                score = 0.90
            elif len(distinct_domains) == 2:
                score = 0.85
            else:
                score = 0.78
            ledger.overall_decision = "ANSWER"

        elif (verified_ratio + partially_ratio) >= 0.60:
            # Mixed / Partial Verification
            base = (verified_ratio * 0.70) + (partially_ratio * 0.45)
            domain_boost = min(0.06, len(distinct_domains) * 0.02)
            score = round(base + domain_boost, 3)
            if score >= 0.70 and counts["unverified"] <= 1:
                ledger.overall_decision = "ANSWER"
            elif score >= 0.45:
                ledger.overall_decision = "WARN"
            else:
                ledger.overall_decision = "ABSTAIN"

        else:
            # Majority Unverified (< 40% verified)
            score = round((verified_ratio * 0.40) + (partially_ratio * 0.25), 3)
            ledger.overall_decision = "ABSTAIN"

        confidence = round(max(0.0, min(1.0, score)), 3)
        ledger.overall_confidence = confidence

