"""
Regression checks for dense sentence decomposition in claim extraction.

Run from the iris-backend folder:
    python -m unittest tests.test_claim_extraction_decomposition
"""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import claim_extractor


PARDON_SENTENCE = (
    "Padilla was arrested and imprisoned before for illegal possession of "
    "firearms and was granted a conditional pardon by the late Fidel Ramos "
    "and an absolute pardon in 2016 by Former President Rodrigo Roa Duterte."
)

LAW_CLAIM_SENTENCE = (
    "Mariel Rodriguez Padilla, wife of Senator Robinhood Padilla, recently "
    "stated that her husband had passed a law dubbed the \"Robin Padilla "
    "Law\" while he was imprisoned in the 1990's."
)

NEUTRAL_NEIGHBOR_SENTENCES = (
    "The claim was made during a public interview. "
    "It quickly circulated on social media."
)


class ClaimExtractionDecompositionTests(unittest.TestCase):
    def setUp(self):
        self._original_openai = claim_extractor.OpenAI
        claim_extractor.OpenAI = None

    def tearDown(self):
        claim_extractor.OpenAI = self._original_openai

    def _claims(self, text):
        return claim_extractor.extract_claims(text)["claims"]

    def test_pardon_sentence_alone_yields_three_claims(self):
        claims = self._claims(PARDON_SENTENCE)

        self.assertEqual(len(claims), 3)
        self.assertIn("illegal possession of firearms", claims[0]["normalized_claim"])
        self.assertIn("conditional pardon by Fidel Ramos", claims[1]["normalized_claim"])
        self.assertIn("absolute pardon in 2016 by Rodrigo Roa Duterte", claims[2]["normalized_claim"])

    def test_pardon_sentence_with_plain_neighbors_still_yields_three_claims(self):
        text = f"{PARDON_SENTENCE} {NEUTRAL_NEIGHBOR_SENTENCES}"
        claims = self._claims(text)

        self.assertEqual(len(claims), 3)

    def test_two_dense_sentences_together_yield_four_claims(self):
        text = f"{LAW_CLAIM_SENTENCE} {PARDON_SENTENCE}"
        claims = self._claims(text)

        self.assertEqual(len(claims), 4)
        self.assertIn("Robin Padilla Law", claims[0]["normalized_claim"])
        self.assertIn("illegal possession of firearms", claims[1]["normalized_claim"])
        self.assertIn("conditional pardon by Fidel Ramos", claims[2]["normalized_claim"])
        self.assertIn("absolute pardon in 2016 by Rodrigo Roa Duterte", claims[3]["normalized_claim"])

    @unittest.skip("Fill in FULL_POST and EXPECTED_COUNT after manual read-through.")
    def test_full_original_post_matches_manual_claim_count(self):
        full_post = "..."
        expected_count = None
        claims = self._claims(full_post)

        self.assertEqual(len(claims), expected_count)


if __name__ == "__main__":
    unittest.main()
