"""
Comprehensive unit and integration test suite for ECRAG 7-Stage Factual Verification Pipeline.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.verification.claim_ledger import (
    EvidenceItem,
    ClaimEntry,
    ClaimLedger,
    split_into_atomic_claims,
    VERDICT_VERIFIED,
    VERDICT_PARTIALLY_VERIFIED,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIED,
    STAGE_NAMES
)
from backend.verification.sources import (
    search_stage_1_official,
    search_stage_2_primary,
    search_stage_3_reference,
    search_stage_4_academic,
    search_stage_5_news,
    search_stage_6_community
)
from backend.verification.pipeline import SevenStageVerificationPipeline


class TestClaimLedger(unittest.TestCase):
    """Tests the Claim Ledger and Evidence Provenance Data Structures."""

    def test_evidence_item_domain_and_provenance(self):
        ev1 = EvidenceItem(
            evidence_id="ev_1",
            stage=1,
            title="WHO Global Health Guidelines",
            url_or_ref="https://who.int/emergencies/disease-outbreak-news",
            snippet="Official WHO guidance on epidemic containment.",
            published_date="2026-05-12"
        )
        self.assertEqual(ev1.stage, 1)
        self.assertEqual(ev1.domain, "who.int")
        self.assertFalse(ev1.is_community_lead)
        self.assertEqual(ev1.authority_tier, 1)

        # Stage 6 community lead test
        ev6 = EvidenceItem(
            evidence_id="ev_6",
            stage=6,
            title="Reddit Discussion",
            url_or_ref="https://reddit.com/r/science/comments/abc",
            snippet="User comment discussing potential symptoms."
        )
        self.assertTrue(ev6.is_community_lead)
        self.assertEqual(ev6.domain, "reddit.com")

    def test_claim_entry_verdicts(self):
        c1 = ClaimEntry("c1", "Water boils at 100C at sea level", verdict=VERDICT_VERIFIED, confidence=0.95)
        self.assertEqual(c1.verdict, VERDICT_VERIFIED)
        self.assertEqual(c1.confidence, 0.95)

        # Invalid verdict should fallback to UNVERIFIED
        c2 = ClaimEntry("c2", "Random unconfirmed statement", verdict="RANDOM_INVALID")
        self.assertEqual(c2.verdict, VERDICT_UNVERIFIED)

    def test_claim_ledger_aggregation(self):
        ledger = ClaimLedger()
        ev = EvidenceItem("ev1", 1, "Official Gov", "https://isro.gov.in/news", "ISRO announced mission.")
        ledger.add_evidence(ev)

        self.assertIn("isro.gov.in", ledger.get_distinct_domains())
        self.assertEqual(len(ledger.get_evidence_for_stage(1)), 1)
        self.assertEqual(len(ledger.get_evidence_for_stage(2)), 0)

        ledger.claims.append(ClaimEntry("c1", "Claim 1", VERDICT_VERIFIED))
        ledger.claims.append(ClaimEntry("c2", "Claim 2", VERDICT_PARTIALLY_VERIFIED))
        ledger.claims.append(ClaimEntry("c3", "Claim 3", VERDICT_CONTRADICTED))
        ledger.claims.append(ClaimEntry("c4", "Claim 4", VERDICT_UNVERIFIED))

        counts = ledger.compute_summary_counts()
        self.assertEqual(counts["verified"], 1)
        self.assertEqual(counts["partially_verified"], 1)
        self.assertEqual(counts["contradicted"], 1)
        self.assertEqual(counts["unverified"], 1)
        self.assertEqual(counts["total_claims"], 4)

    def test_atomic_claim_decomposition(self):
        text = (
            "1. ISRO successfully launched the EOS-08 satellite on August 16, 2024.\n"
            "2. The SSLV-D3 rocket placed the satellite into a 475 km circular orbit.\n"
            "3. The primary payload carries state-of-the-art infrared sensors."
        )
        claims = split_into_atomic_claims(text)
        self.assertGreaterEqual(len(claims), 2)
        self.assertTrue(any("EOS-08" in c for c in claims))
        self.assertTrue(any("SSLV-D3" in c for c in claims))


class TestSevenStageVerification(unittest.TestCase):
    """Tests the Seven-Stage Factual Verification Pipeline."""

    def test_community_leads_cannot_mark_verified_alone(self):
        """Rule: Community sources (Reddit/Quora) can never serve as authoritative proof alone."""
        pipeline = SevenStageVerificationPipeline()
        ledger = ClaimLedger()

        # Add only Stage 6 community evidence
        ev_comm = EvidenceItem(
            evidence_id="stg6_1",
            stage=6,
            title="Reddit thread about new battery tech",
            url_or_ref="https://reddit.com/r/technology/post1",
            snippet="A user claims solid state batteries are now being sold in stores.",
            is_community_lead=True
        )
        ledger.add_evidence(ev_comm)

        # Run deterministic verification against this claim
        pipeline._run_deterministic_claim_verification(
            ["Solid state batteries are currently sold in stores."],
            [ev_comm],
            ledger
        )

        claim = ledger.claims[0]
        # Must NEVER be VERIFIED! Must be PARTIALLY_VERIFIED or UNVERIFIED with caveat.
        self.assertNotEqual(claim.verdict, VERDICT_VERIFIED)
        self.assertIn("community", claim.reasoning.lower())

    def test_contradiction_detection_penalizes_decision(self):
        """Rule: Credible contradiction forces decision to ABSTAIN."""
        pipeline = SevenStageVerificationPipeline()
        ledger = ClaimLedger()

        ev_opposing = EvidenceItem(
            evidence_id="stg1_1",
            stage=1,
            title="Ministry of Finance Press Release",
            url_or_ref="https://finmin.gov.in/release",
            snippet="The ministry explicitly denied the rumor and refuted claims that tax rates were increased. No tax increase was implemented.",
            authority_tier=1
        )
        ledger.add_evidence(ev_opposing)

        pipeline._run_deterministic_claim_verification(
            ["The ministry implemented a 10 percent tax rate increase."],
            [ev_opposing],
            ledger
        )

        claim = ledger.claims[0]
        self.assertEqual(claim.verdict, VERDICT_CONTRADICTED)

        pipeline._calculate_pipeline_decision(ledger, distinct_domains=["finmin.gov.in"])
        self.assertEqual(ledger.overall_decision, "ABSTAIN")
        self.assertLess(ledger.overall_confidence, 0.50)

    def test_verified_with_authoritative_sources(self):
        """Rule: Verified claims with authoritative corroboration yield ANSWER."""
        pipeline = SevenStageVerificationPipeline()
        ledger = ClaimLedger()

        ev_official = EvidenceItem(
            evidence_id="stg1_1",
            stage=1,
            title="ISRO Official Launch Report",
            url_or_ref="https://isro.gov.in/launch",
            snippet="ISRO confirmed the successful launch of SSLV-D3 placing EOS-08 into orbit.",
            authority_tier=1,
            domain="isro.gov.in"
        )
        ev_primary = EvidenceItem(
            evidence_id="stg2_1",
            stage=2,
            title="Technical Bulletin EOS-08",
            url_or_ref="doc://bulletin.pdf#page=1",
            snippet="SSLV-D3 rocket placed EOS-08 satellite into a circular orbit successfully.",
            authority_tier=1,
            domain="primary-document"
        )
        ledger.add_evidence(ev_official)
        ledger.add_evidence(ev_primary)

        pipeline._run_deterministic_claim_verification(
            ["SSLV-D3 placed EOS-08 satellite into orbit."],
            [ev_official, ev_primary],
            ledger
        )

        claim = ledger.claims[0]
        self.assertEqual(claim.verdict, VERDICT_VERIFIED)
        self.assertGreaterEqual(len(claim.supporting_citations), 1)

        pipeline._calculate_pipeline_decision(ledger, distinct_domains=["isro.gov.in", "primary-document"])
        self.assertEqual(ledger.overall_decision, "ANSWER")
        self.assertGreaterEqual(ledger.overall_confidence, 0.80)

    def test_stage_skipping_logic(self):
        """Rule: Unnecessary stages are skipped transparently with clear reasons."""
        pipeline = SevenStageVerificationPipeline()
        ledger = ClaimLedger()

        # In PDF mode, external searches should be transparently skipped
        skip_r = pipeline._should_skip_stage(1, "What is Oxford handbook policy?", ledger, mode="pdf")
        self.assertIsNotNone(skip_r)
        self.assertIn("document mode active", skip_r.lower())

        # For commodity price query, academic papers search should be skipped
        skip_acad = pipeline._should_skip_stage(4, "What is the gold price rate today in Mumbai?", ledger, mode="web")
        self.assertIsNotNone(skip_acad)
        self.assertIn("non-academic", skip_acad.lower())

    def test_streaming_event_generation(self):
        """Rule: Every progress message corresponds to a real backend operation."""
        chunks = [{"text": "The council standard form is required for administrative requests on Page 3.", "page": 3}]
        pipeline = SevenStageVerificationPipeline(
            pdf_path="test_handbook.pdf",
            offline_chunks=chunks
        )

        events = []
        for event in pipeline.run_streaming(
            "What form is used for administrative requests?",
            candidate_answer="The council uses standard forms for administrative requests.",
            mode="pdf"
        ):
            events.append(event)

        # Check that events were emitted
        event_types = [e.get("type") for e in events]
        self.assertIn("pipeline_start", event_types)
        self.assertIn("stage_start", event_types)
        self.assertIn("stage_complete", event_types)
        self.assertIn("pipeline_complete", event_types)

        # In PDF mode, stage 2 should be completed with source count >= 1
        stg2_completes = [e for e in events if e.get("type") == "stage_complete" and e.get("stage") == 2]
        self.assertTrue(len(stg2_completes) >= 1)
        self.assertGreater(stg2_completes[0].get("source_count", 0), 0)


if __name__ == "__main__":
    unittest.main()

