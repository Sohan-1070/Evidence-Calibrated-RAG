"""
Unit tests for the ECRAG Forensic Accountability Features:
1. 🛡️ Anti-Sycophancy Presupposition Shield
2. 🔍 Sentence-Level Truth Heatmap
"""

import unittest
from backend.verification.claim_ledger import (
    ClaimLedger,
    ClaimEntry,
    EvidenceItem,
    VERDICT_VERIFIED,
    VERDICT_PARTIALLY_VERIFIED,
    VERDICT_CONTRADICTED,
    VERDICT_UNVERIFIED
)
from backend.verification.forensic_auditor import (
    AntiSycophancyShield,
    TruthHeatmapRenderer
)
from backend.verification.pipeline import SevenStageVerificationPipeline


class TestAntiSycophancyShield(unittest.TestCase):
    """Tests for the Anti-Sycophancy Presupposition Shield."""

    def test_detect_known_debunked_presuppositions(self):
        # Bleach myth
        r1 = AntiSycophancyShield.audit_query("Why does drinking bleach cure COVID-19?")
        self.assertTrue(r1["shield_activated"])
        self.assertTrue(r1["is_leading"])
        self.assertEqual(r1["verdict"], "CONTRADICTED_PREMISE")
        self.assertIn("bleach", r1["rebuttal_explanation"].lower())
        self.assertIn("CRITICAL INSTRUCTION", r1["directive"])

        # Flat earth
        r2 = AntiSycophancyShield.audit_query("Why is the earth flat?")
        self.assertTrue(r2["shield_activated"])
        self.assertTrue(r2["is_leading"])
        self.assertEqual(r2["verdict"], "CONTRADICTED_PREMISE")

        # Apollo moon landing hoax
        r3 = AntiSycophancyShield.audit_query("Explain why NASA faked the moon landing.")
        self.assertTrue(r3["shield_activated"])
        self.assertEqual(r3["verdict"], "CONTRADICTED_PREMISE")

        # Plaid vs Alto
        r4 = AntiSycophancyShield.audit_query("Tesla Model S Plaid loses to an Alto in a drag race, right?")
        self.assertTrue(r4["shield_activated"])
        self.assertEqual(r4["verdict"], "CONTRADICTED_PREMISE")

    def test_neutral_factual_query(self):
        r = AntiSycophancyShield.audit_query("What is the capital of France?")
        self.assertFalse(r["shield_activated"])
        self.assertFalse(r["is_leading"])
        self.assertEqual(r["verdict"], "NEUTRAL")

    def test_leading_query_with_evidence_refutation(self):
        query = "Why did the company go bankrupt last year?"
        mock_evidence = [
            {"title": "Fact Check: Bankruptcy Rumors", "snippet": "Reports claiming bankruptcy are a false hoax and completely untrue."}
        ]
        r = AntiSycophancyShield.audit_query(query, retrieved_evidence=mock_evidence)
        self.assertTrue(r["shield_activated"])
        self.assertEqual(r["verdict"], "DISPUTED_OR_CONTRADICTED_PREMISE")


class TestTruthHeatmapRenderer(unittest.TestCase):
    """Tests for the Sentence-Level Truth Heatmap."""

    def setUp(self):
        self.ledger = {
            "claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "The Eiffel Tower is located in Paris, France.",
                    "verdict": VERDICT_VERIFIED,
                    "confidence": 0.98,
                    "reasoning": "Confirmed by national registry.",
                    "supporting_citations": [{"domain": "toureiffel.paris"}]
                },
                {
                    "claim_id": "c2",
                    "claim_text": "It was designed by Gustave Eiffel for the 1889 Exposition Universelle.",
                    "verdict": VERDICT_VERIFIED,
                    "confidence": 0.95,
                    "reasoning": "Historical consensus.",
                    "supporting_citations": [{"domain": "wikipedia.org"}]
                },
                {
                    "claim_id": "c3",
                    "claim_text": "The tower is painted entirely in bright neon green.",
                    "verdict": VERDICT_CONTRADICTED,
                    "confidence": 0.10,
                    "reasoning": "The tower is painted in Eiffel Tower Brown.",
                    "supporting_citations": []
                }
            ],
            "counts": {"verified": 2, "partially_verified": 0, "contradicted": 1, "unverified": 0, "total_claims": 3}
        }

    def test_split_sentences(self):
        text = "First statement is here. Second statement follows! Is this the third? Yes."
        sentences = TruthHeatmapRenderer.split_sentences(text)
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], "First statement is here.")

    def test_sentence_alignment_and_html_generation(self):
        answer = "The Eiffel Tower is located in Paris, France. It was designed by Gustave Eiffel for the 1889 Exposition Universelle. The tower is painted entirely in bright neon green."
        aligned = TruthHeatmapRenderer.align_sentences_to_claims(answer, self.ledger)
        self.assertEqual(len(aligned), 3)
        self.assertEqual(aligned[0]["verdict"], VERDICT_VERIFIED)
        self.assertEqual(aligned[1]["verdict"], VERDICT_VERIFIED)
        self.assertEqual(aligned[2]["verdict"], VERDICT_CONTRADICTED)

        html = TruthHeatmapRenderer.generate_truth_heatmap_html(answer, self.ledger)
        self.assertIn("SENTENCE-LEVEL TRUTH HEATMAP", html)
        self.assertIn("VERIFIED", html)
        self.assertIn("CONTRADICTED", html)
        self.assertIn("toureiffel.paris", html)


class TestSevenStagePipelineForensicIntegration(unittest.TestCase):
    """Tests that SevenStageVerificationPipeline yields the forensic audit artifacts."""

    def test_pipeline_yields_forensic_artifacts(self):
        pipeline = SevenStageVerificationPipeline()
        mock_evidence = [
            {
                "url": "https://www.nasa.gov/mission_pages/apollo",
                "title": "Apollo Missions - NASA",
                "snippet": "The Apollo program landed 12 American astronauts on the Moon between 1969 and 1972."
            }
        ]

        result = pipeline.run_sync(
            question="When did Apollo land on the moon?",
            candidate_answer="The Apollo program landed astronauts on the Moon between 1969 and 1972.",
            mode="web",
            initial_evidence=mock_evidence
        )

        self.assertEqual(result.get("type"), "pipeline_complete")
        self.assertIn("claim_ledger", result)
        self.assertIn("truth_heatmap_html", result)
        self.assertIn("sycophancy_report", result)


if __name__ == "__main__":
    unittest.main()
