"""The claimed date: matched in any wording, never a reason to discard the coverage."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.attribution_integrity import date_phrase_match

CLAIM = {'claim_type': 'attributed_statement', 'normalized_claim': 'Padilla said he will not run.',
         'attribution': {'speaker': 'Sen. Robin Padilla', 'source': 'Facebook post',
                         'date': 'Sept. 18', 'statement': 'Padilla said he will not run.'}}
DATED = {'url': 'https://mb.com.ph/2026/09/18/padilla/', 'status': 'extracted',
         'text': 'Sen. Robin Padilla said on September 18 that he will not run again in 2028.'}
UNDATED = {'url': 'https://www.philstar.com/2026/09/19/padilla/', 'status': 'extracted',
           'text': 'Sen. Robin Padilla said on Friday that he will not run again in 2028.'}
OTHER_DAY = {'url': 'https://www.gmanetwork.com/news/x/story/', 'status': 'extracted',
             'text': 'Sen. Robin Padilla said on September 19 that he will not run again.'}


class DateWordingTests(unittest.TestCase):
    def test_the_same_date_counts_however_it_is_written(self):
        for text in ['Padilla spoke on Sept. 18 in Manila.',
                     'Padilla spoke on September 18 in Manila.',
                     'the announcement Thursday night, September 18, 2026',
                     'Sa Setyembre 18, nagsalita si Padilla.',
                     'Padilla spoke on 18 September in Manila.']:
            with self.subTest(text=text):
                self.assertTrue(date_phrase_match('Sept. 18', text))

    def test_another_day_or_no_day_does_not_count(self):
        for text in ['Padilla spoke on September 19.', 'Padilla spoke on Friday.',
                     'Padilla spoke this week.', 'Bill September 188 was filed.']:
            with self.subTest(text=text):
                self.assertFalse(date_phrase_match('Sept. 18', text))

    def test_a_phrase_that_is_not_a_date_still_matches_as_a_phrase(self):
        self.assertTrue(date_phrase_match('last Holy Week', 'He spoke last Holy Week in Manila.'))
        self.assertFalse(date_phrase_match('last Holy Week', 'He spoke during the rainy season.'))


class DateAnchorGateTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app

    def test_coverage_without_the_date_is_still_admitted(self):
        # C06: requiring the calendar date rejected all 33 articles and the claims lost their evidence.
        gate = self.app.attribution_evidence_gate(UNDATED, CLAIM, anchors_only=True)
        self.assertTrue(gate['matches'])
        self.assertEqual(gate['anchor_checks']['date'], 'unconfirmed')
        self.assertFalse(gate['date_confirmed'])

    def test_an_article_stating_the_date_is_marked_confirmed(self):
        gate = self.app.attribution_evidence_gate(DATED, CLAIM, anchors_only=True)
        self.assertTrue(gate['matches'])
        self.assertEqual(gate['anchor_checks']['date'], 'normalized_phrase_match')
        self.assertTrue(gate['date_confirmed'])

    def test_a_wrong_speaker_is_still_rejected(self):
        other = dict(UNDATED, text='Sen. Imee Marcos said on Friday that she will not run again.')
        self.assertFalse(self.app.attribution_evidence_gate(other, CLAIM, anchors_only=True)['matches'])

    def test_an_unconfirmed_date_keeps_the_claim_off_verified(self):
        verdict, message = self.app.cap_unconfirmed_date('Verified', 'Supported.', CLAIM, [UNDATED])
        self.assertEqual(verdict, 'Partially Verified')
        self.assertIn('Sept. 18', message)

    def test_a_confirmed_date_leaves_the_verdict_alone(self):
        self.assertEqual(self.app.cap_unconfirmed_date('Verified', 'Supported.', CLAIM, [DATED]),
                         ('Verified', 'Supported.'))

    def test_another_day_does_not_confirm_the_date(self):
        verdict, _ = self.app.cap_unconfirmed_date('Verified', 'Supported.', CLAIM, [OTHER_DAY])
        self.assertEqual(verdict, 'Partially Verified')

    def test_a_claim_without_a_date_is_untouched(self):
        undated_claim = {**CLAIM, 'attribution': {**CLAIM['attribution'], 'date': None}}
        self.assertEqual(self.app.cap_unconfirmed_date('Verified', 'Supported.', undated_claim, [UNDATED]),
                         ('Verified', 'Supported.'))


if __name__ == '__main__':
    unittest.main()
