"""
Integration test verifying real backend retrieval for all 7 stages against live providers.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.verification.sources import (
    search_stage_1_official,
    search_stage_2_primary,
    search_stage_3_reference,
    search_stage_4_academic,
    search_stage_5_news,
    search_stage_6_community
)
from backend.verification.pipeline import SevenStageVerificationPipeline


class TestLiveSourcesIntegration(unittest.TestCase):
    """Verifies that live search modules actually connect and retrieve data."""

    def test_live_stage_3_wikipedia(self):
        """Wikipedia API must return real articles with snippet text."""
        items = search_stage_3_reference("James Webb Space Telescope", max_results=2)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0].stage, 3)
        self.assertIn("wikipedia.org", items[0].domain)
        self.assertTrue(len(items[0].snippet) > 10)

    def test_live_stage_4_arxiv(self):
        """ArXiv Atom feed must return real papers with preprints and abstracts."""
        items = search_stage_4_academic("deep learning neural networks", max_results=2)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0].stage, 4)
        self.assertTrue(len(items[0].snippet) > 10)

    def test_live_stage_5_google_news(self):
        """Google News RSS must return recent news reports with publication dates."""
        items = search_stage_5_news("ISRO space mission", max_results=3)
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0].stage, 5)
        self.assertTrue(len(items[0].title) > 5)

    def test_live_stage_6_community_tagged_as_leads(self):
        """Community sources must be marked with is_community_lead=True."""
        items = search_stage_6_community("Python programming tips", max_results=2)
        if items:
            self.assertEqual(items[0].stage, 6)
            self.assertTrue(items[0].is_community_lead)
            self.assertEqual(items[0].authority_tier, 4)

    def test_full_pipeline_live_streaming(self):
        """Test full 7-stage streaming pipeline on a real query."""
        pipeline = SevenStageVerificationPipeline()
        events = []
        for event in pipeline.run_streaming(
            question="What is the speed of light in vacuum?",
            candidate_answer="The speed of light in a vacuum is exactly 299,792,458 meters per second.",
            mode="web"
        ):
            events.append(event)

        final_event = events[-1]
        self.assertEqual(final_event["type"], "pipeline_complete")
        ledger = final_event.get("claim_ledger")
        self.assertIsNotNone(ledger)
        self.assertIn("claims", ledger)
        self.assertGreater(len(ledger["claims"]), 0)
        # Speed of light is well corroborated by Wikipedia/reference
        verdict = ledger["claims"][0]["verdict"]
        self.assertIn(verdict, ["VERIFIED", "PARTIALLY_VERIFIED"])


if __name__ == "__main__":
    unittest.main()
