"""
Simple Week 3 verdict helper checks.

Run from the iris-backend folder:
    python tests/test_verdict_generator.py

This test uses a tiny fake embedding model so it can run without network access.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pipeline.verdict_generator as verdict_generator


class FakeModel:
    def encode(self, text, convert_to_tensor=True):
        return text


class FakeSimilarity:
    def __init__(self, score):
        self.score = score

    def item(self):
        return self.score


def fake_cos_sim(claim_text, article_text):
    if "dengue" in article_text.lower():
        return FakeSimilarity(0.92)

    return FakeSimilarity(0.12)


def run_checks() -> None:
    claim = "The Department of Health reported new dengue cases."
    articles = [
        {
            "source": "GMA News",
            "title": "DOH reports dengue cases",
            "url": "https://example.com/dengue",
            "status": "extracted",
            "word_count": 120,
            "text": (
                "The Department of Health reported new dengue cases in the "
                "Philippines and reminded the public to remove mosquito "
                "breeding sites."
            ),
        },
        {
            "source": "Philippine Star",
            "title": "Sports update",
            "url": "https://example.com/sports",
            "status": "extracted",
            "word_count": 120,
            "text": (
                "A basketball team won the championship after a close final "
                "game in Manila."
            ),
        },
    ]

    original_get_model = verdict_generator.get_model
    original_cos_sim = verdict_generator.util.cos_sim

    try:
        verdict_generator.get_model = lambda: FakeModel()
        verdict_generator.util.cos_sim = fake_cos_sim
        result = verdict_generator.generate_verdict(claim, articles)
    finally:
        verdict_generator.get_model = original_get_model
        verdict_generator.util.cos_sim = original_cos_sim

    assert result["verdict"] == "Verified"
    assert result["primary_evidence"] is not None
    assert "similarity_score" in result["primary_evidence"]
    assert result["corroboration_count"] >= 0

    print("All Week 3 verdict checks passed.")
    print(f"Verdict: {result['verdict']}")
    print(f"Top score: {result['primary_evidence']['similarity_score']}")


if __name__ == "__main__":
    run_checks()
