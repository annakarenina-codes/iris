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

    @patch('pipeline.component_evidence.prepare_component_review')
    @patch('pipeline.component_evidence.review_components')
    def test_every_quote_claim_searches_and_sees_what_the_others_found(self, component_review, prepare):
        # Quote claims used to read one search built for the whole post and never search on
        # their own. Each claim now searches; an article one claim finds is offered to the others.
        component_review.return_value = {
            'status': 'ok', 'verdict': 'Partially Verified',
            'reason': 'Stubbed component review for retrieval isolation.',
            'components': [{'component': 'fixture', 'status': 'supported', 'citations': []}],
            'supporting_urls': [ABS_CBN_URL],
        }
        prepare.side_effect = lambda claim, source_context='': {
            'status': 'ok', 'claim': claim, 'source_context': source_context, 'contexts': []}
        weather = {
            "source": "GMA News", "title": "Rain over Luzon",
            "url": "https://www.gmanetwork.com/news/weather/content/1/rain-over-luzon/story/",
            "description": "", "status": "extracted", "word_count": 40, "error": None,
            "extraction_method": "paragraphs", "extraction_quality": "thin",
            "text": "Rain is expected over Luzon this weekend, the weather bureau said.",
        }
        originals = {name: getattr(iris_app, name) for name in (
            "detect_language", "translate_to_english", "profile_content", "is_opinion",
            "extract_claims", "search_and_extract", "get_cached_verdict", "save_cached_verdict")}
        search_calls = []

        def fake_search(primary_query, backup_query=None, **_):
            search_calls.append(primary_query)
            if "evaluation" in primary_query:
                # This claim's own search misses the hearing report its siblings find.
                result = _abs_cbn_event_search_result(primary_query)
                result["articles"] = [weather]
                return result
            return _abs_cbn_event_search_result(primary_query)

        claims = [
            ("\"But you are the ones in charge of the investigation regarding the confidential "
             "funds, is that correct?\" Padilla asked Wamil."),
            "\"It is not an investigation. It is an evaluation,\" the witness answered.",
            ("Padilla then asked Wamil to define \"confidential,\" to which the auditor "
             "replied, \"classified.\""),
        ]
        try:
            iris_app.detect_language = lambda text: "english"
            iris_app.translate_to_english = lambda text, language: text
            iris_app.profile_content = lambda text, translated: _fake_content_profile()
            iris_app.is_opinion = lambda text: {"is_opinion": False, "matched_phrases": [], "matched_words": []}
            iris_app.extract_claims = lambda text, translated: {
                "status": "ok", "method": "test_stub", "error": None, "post_type": "fact_only",
                "contains_opinion": False, "contains_recommendation": False, "ignored_segments": [],
                "claims": [{"claim_id": i, "claim_text": text, "normalized_claim": text,
                            "claim_type": "factual_claim", "risk_tags": []}
                           for i, text in enumerate(claims, 1)],
            }
            iris_app.search_and_extract = fake_search
            iris_app.get_cached_verdict = lambda claim_hash: None
            iris_app.save_cached_verdict = lambda claim_hash, claim_text, result: None
            response = iris_app.app.test_client().post("/verify", json={"text": PADILLA_WAMIL_POST, "debug": True})
            payload = response.get_json()
        finally:
            for name, value in originals.items():
                setattr(iris_app, name, value)

        self.assertEqual(response.status_code, 200)
        # One search per claim, each in the claim's own words; no search built for the whole post.
        self.assertEqual(len(search_calls), 3)
        self.assertNotIn("shared_evidence_pool", payload["debug"])
        self.assertEqual(payload["debug"]["post_evidence_pool"]["found_by_several_claims"], 1)
        claims_out = payload["claims"]
        self.assertTrue(all(claim["is_quote_derived"] for claim in claims_out))
        self.assertEqual(claims_out[0]["retrieval_strategy"], "claim_search_only")
        # The second claim's own search missed the hearing report; its siblings' copy reached it.
        self.assertEqual(claims_out[1]["retrieval_strategy"], "claim_search_plus_post_pool")
        self.assertEqual(claims_out[1]["shared_evidence"]["urls"], [ABS_CBN_URL])
        self.assertEqual(claims_out[1]["sources"][0]["url"], ABS_CBN_URL)
        # Reviews run a few at a time, so the second claim's call is found by its text.
        reviewed = next(call for call in component_review.call_args_list if call.args[0] == claims[1])
        self.assertIn(ABS_CBN_URL, [article["url"] for article in reviewed.args[1]])
        self.assertEqual(prepare.call_count, 3)


if __name__ == "__main__":
    unittest.main()
