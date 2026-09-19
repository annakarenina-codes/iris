"""
Regression checks for quote-heavy evidence retrieval.

Run from the iris-backend folder:
    python -m unittest tests.test_quote_evidence_retrieval
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app as iris_app
import pipeline.article_extractor as article_module
from pipeline.event_retrieval import build_event_search_query


ABS_CBN_URL = (
    "https://www.abs-cbn.com/news/nation/2026/8/5/"
    "padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501"
)

PADILLA_WAMIL_POST = (
    "'HAVE YOU ALREADY VISITED BARMM?' Senator-judge Robinhood Padilla asked "
    "former state auditor Roderick Wamil if he had ever visited the Bangsamoro "
    "Autonomous Region in Muslim Mindanao (BARMM) and whether he was aware of "
    "the country's ongoing terrorism threats. During his interjection, Padilla "
    "raised preliminary questions about the Audit Observation Memorandum, trying "
    "to establish ties to the confidential funds used by Vice President Sara "
    "Duterte for surveillance on potential New People's Army (NPA) recruitment. "
    "\"But you are the ones in charge of the investigation regarding the "
    "confidential funds, is that correct?\" Padilla asked Wamil. "
    "\"It is not an investigation. It is an evaluation,\" the witness answered. "
    "\"Do you believe that confidential agents should be identified? State their "
    "real names,\" the senator furthered. \"There are no provisions for that in "
    "the joint circular,\" Wamil said. Padilla then asked Wamil to define "
    "\"confidential,\" to which the auditor replied, \"classified.\""
)


def _fake_content_profile():
    return {
        "status": "ok",
        "method": "test_stub",
        "error": None,
        "post_type": "fact_only",
        "confidence": 0.9,
        "ambiguity_score": 0.1,
        "ambiguity_reasons": ["quote_context_needed"],
        "contains_factual_claims": True,
        "contains_opinion": False,
        "contains_recommendation": False,
        "contains_forecast_or_projection": False,
        "contains_satire_or_humor": False,
        "contains_quote": True,
        "eligible_for_verification": True,
        "recommended_route": "proceed_to_verification",
        "verification_text": PADILLA_WAMIL_POST,
        "normalized_verification_text": PADILLA_WAMIL_POST,
        "segments": [
            {
                "segment_id": "s1",
                "text": PADILLA_WAMIL_POST,
                "scores": {"quote": 0.88},
                "reason_codes": ["quote_context_needed"],
                "eligible_for_verification": True,
            }
        ],
        "ignored_segments": [],
        "user_notification": None,
        "openai_profile": {
            "used": False,
            "status": "not_run",
            "error": None,
            "result": None,
        },
    }


def _abs_cbn_event_search_result(query):
    article = {
        "source": "ABS-CBN News",
        "title": "Padilla tests auditor on knowledge of terrorism, security threats",
        "url": ABS_CBN_URL,
        "description": "Padilla asked Roderick Wamil about BARMM and security threats.",
        "status": "extracted",
        "word_count": 182,
        "error": None,
        "extraction_method": "trafilatura",
        "extraction_quality": "full",
        "text": (
            "Senator-judge Robinhood Padilla asked former state auditor Roderick "
            "Wamil whether he had visited BARMM and whether he was aware of "
            "terrorism and security threats. Padilla asked whether auditors were "
            "in charge of evaluating confidential funds. Wamil answered that it "
            "was an evaluation, not an investigation. Padilla asked about "
            "confidential agents, the joint circular, and whether agents should "
            "be named. Wamil said the joint circular had no provisions for that. "
            "Padilla asked Wamil to define confidential, and Wamil replied that "
            "confidential meant classified. "
        )
        * 2,
    }
    return {
        "total_search_results": 1,
        "searched_articles": 1,
        "extracted_articles": 1,
        "articles": [article],
        "source_summary": [
            {
                "source": "ABS-CBN News",
                "results_found": 1,
                "articles_checked": 1,
                "articles_extracted": 1,
            }
        ],
        "search": {
            "primary_query": query,
            "backup_query_used": False,
            "total_results": 1,
            "results": [
                {
                    "source": "ABS-CBN News",
                    "title": article["title"],
                    "url": article["url"],
                    "description": article["description"],
                }
            ],
            "searches": [
                {
                    "source_reports": [
                        {
                            "source": "ABS-CBN News",
                            "status": "ok",
                            "results": [],
                        }
                    ]
                }
            ],
        },
    }


def _partial_verdict(scoring_claim, articles):
    evidence = {
        "source": "ABS-CBN News",
        "title": "Padilla tests auditor on knowledge of terrorism, security threats",
        "url": ABS_CBN_URL,
        "similarity_score": 0.63,
        "status": "extracted",
        "word_count": 182,
    }
    return {
        "verdict": "Partially Verified",
        "reason": f"Fake partial support for: {scoring_claim}",
        "corroboration_count": 1,
        "primary_evidence": evidence,
        "supporting_sources": [evidence],
        "similarity_thresholds": {
            "verified": 0.85,
            "partial": 0.5,
        },
    }


class QuoteEvidenceRetrievalTests(unittest.TestCase):
    def test_event_query_preserves_padilla_wamil_context(self):
        query = build_event_search_query(PADILLA_WAMIL_POST)

        self.assertIn("Robinhood Padilla", query)
        self.assertIn("Roderick Wamil", query)
        self.assertIn("BARMM", query)
        self.assertIn("terrorism threats", query)
        self.assertIn("confidential funds", query)

    def test_trafilatura_fallback_clears_thin_extraction_floor(self):
        original_requests = article_module.requests
        original_trafilatura = article_module.trafilatura

        class FakeResponse:
            text = """
                <html>
                    <head><title>Padilla tests auditor</title></head>
                    <body><main><p>Short article shell.</p></main></body>
                </html>
            """

            def raise_for_status(self):
                return None

        class FakeRequests:
            RequestException = Exception

            @staticmethod
            def get(url, headers=None, timeout=None):
                return FakeResponse()

        class FakeTrafilatura:
            @staticmethod
            def extract(html, url=None, include_comments=False, include_tables=False):
                return "Recovered ABS-CBN article body text " * 40

        try:
            article_module.requests = FakeRequests
            article_module.trafilatura = FakeTrafilatura
            article = article_module.extract_article_text(ABS_CBN_URL)
        finally:
            article_module.requests = original_requests
            article_module.trafilatura = original_trafilatura

        self.assertEqual(article["status"], "extracted")
        self.assertEqual(article["extraction_method"], "trafilatura")
        self.assertEqual(article["extraction_quality"], "full")
        self.assertGreaterEqual(article["word_count"], article_module.THIN_ARTICLE_WORDS)

    @patch('pipeline.component_evidence.review_components')
    def test_quote_claims_reuse_abs_cbn_event_pool_and_score_paraphrases(self, component_review):
        # This is a retrieval-routing test; evidence reasoning has its own fixtures.
        component_review.return_value = {
            'status': 'ok', 'verdict': 'Partially Verified',
            'reason': 'Stubbed component review for retrieval isolation.',
            'components': [{'component': 'fixture', 'status': 'supported', 'citations': []}],
            'supporting_urls': [ABS_CBN_URL],
        }
        originals = {
            "detect_language": iris_app.detect_language,
            "translate_to_english": iris_app.translate_to_english,
            "profile_content": iris_app.profile_content,
            "is_opinion": iris_app.is_opinion,
            "extract_claims": iris_app.extract_claims,
            "search_and_extract": iris_app.search_and_extract,
            "generate_verdict": iris_app.generate_verdict,
            "refine_with_openai_rag": iris_app.refine_with_openai_rag,
            "get_cached_verdict": iris_app.get_cached_verdict,
            "save_cached_verdict": iris_app.save_cached_verdict,
            "paraphrase_quote_claim": iris_app.paraphrase_quote_claim,
        }
        search_calls = []

        def fake_search(primary_query, backup_query=None):
            search_calls.append(primary_query)
            return _abs_cbn_event_search_result(primary_query)

        def fake_paraphrase(claim):
            claim_text = claim["normalized_claim"]
            if "not an investigation" in claim_text:
                paraphrase = "Wamil answered that the process was an evaluation, not an investigation."
            elif "define" in claim_text:
                paraphrase = "Padilla asked Wamil to define confidential, and Wamil replied that it meant classified."
            else:
                paraphrase = "Padilla asked Wamil whether auditors were in charge of evaluating confidential funds."

            return {
                "used_for_scoring": True,
                "status": "ok",
                "method": "test_stub",
                "error": None,
                "paraphrase": paraphrase,
            }

        try:
            iris_app.detect_language = lambda text: "english"
            iris_app.translate_to_english = lambda text, language: text
            iris_app.profile_content = lambda text, translated: _fake_content_profile()
            iris_app.is_opinion = lambda text: {
                "is_opinion": False,
                "matched_phrases": [],
                "matched_words": [],
            }
            iris_app.extract_claims = lambda text, translated: {
                "status": "ok",
                "method": "test_stub",
                "error": None,
                "post_type": "fact_only",
                "contains_opinion": False,
                "contains_recommendation": False,
                "ignored_segments": [],
                "claims": [
                    {
                        "claim_id": 1,
                        "claim_text": (
                            "\"But you are the ones in charge of the investigation "
                            "regarding the confidential funds, is that correct?\" "
                            "Padilla asked Wamil."
                        ),
                        "normalized_claim": (
                            "\"But you are the ones in charge of the investigation "
                            "regarding the confidential funds, is that correct?\" "
                            "Padilla asked Wamil."
                        ),
                        "claim_type": "factual_claim",
                        "risk_tags": [],
                    },
                    {
                        "claim_id": 2,
                        "claim_text": "\"It is not an investigation. It is an evaluation,\" the witness answered.",
                        "normalized_claim": "\"It is not an investigation. It is an evaluation,\" the witness answered.",
                        "claim_type": "factual_claim",
                        "risk_tags": [],
                    },
                    {
                        "claim_id": 3,
                        "claim_text": (
                            "Padilla then asked Wamil to define \"confidential,\" "
                            "to which the auditor replied, \"classified.\""
                        ),
                        "normalized_claim": (
                            "Padilla then asked Wamil to define \"confidential,\" "
                            "to which the auditor replied, \"classified.\""
                        ),
                        "claim_type": "factual_claim",
                        "risk_tags": [],
                    },
                ],
            }
            iris_app.search_and_extract = fake_search
            iris_app.generate_verdict = _partial_verdict
            iris_app.refine_with_openai_rag = lambda claim, articles, verdict_result: {
                "used": False,
                "status": "not_needed",
                "error": None,
                "result": None,
            }
            iris_app.get_cached_verdict = lambda claim_hash: None
            iris_app.save_cached_verdict = lambda claim_hash, claim_text, result: None
            iris_app.paraphrase_quote_claim = fake_paraphrase

            client = iris_app.app.test_client()
            response = client.post(
                "/verify",
                json={"text": PADILLA_WAMIL_POST, "debug": True},
            )
            payload = response.get_json()
        finally:
            for name, value in originals.items():
                setattr(iris_app, name, value)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(component_review.call_count, 3)
        self.assertEqual(len(search_calls), 1)
        self.assertIn("Robinhood Padilla", search_calls[0])
        self.assertTrue(payload["debug"]["shared_evidence_pool"]["used"])
        self.assertEqual(
            payload["debug"]["shared_evidence_pool"]["source_summary"][0]["source"],
            "ABS-CBN News",
        )
        self.assertEqual(
            payload["debug"]["shared_evidence_pool"]["articles"][0]["extraction_quality"],
            "full",
        )

        claims = payload["claims"]
        self.assertEqual(claims[0]["verdict"], "Partially Verified")
        self.assertEqual(claims[2]["verdict"], "Partially Verified")
        self.assertTrue(claims[1]["is_quote_derived"])
        self.assertTrue(claims[1]["quote_paraphrase"]["used_for_scoring"])
        self.assertIn("evaluation", claims[1]["scoring_claim"])
        self.assertTrue(all(claim["retrieval_strategy"] == "event_pool_only" for claim in claims))
        self.assertTrue(all(claim["sources"][0]["source"] == "ABS-CBN News" for claim in claims))


if __name__ == "__main__":
    unittest.main()
