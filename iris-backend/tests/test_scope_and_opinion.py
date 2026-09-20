"""Two limits on what IRIS checks: no opinion columns as proof, no posts outside its coverage."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.coverage_scope import PHILIPPINE_MARKERS, out_of_scope_message, philippine_scope
from pipeline.evidence_urls import is_opinion_url

FACTUAL = {'claim_type': 'factual_claim', 'attribution': {}}
ATTRIBUTED = {'claim_type': 'attributed_statement',
              'attribution': {'speaker': 'Cielito Habito', 'statement': 'The vote is expensive.'}}
COLUMN = {'url': 'https://opinion.inquirer.net/183377/the-vote-is-expensive', 'text': 'A column.'}
REPORT = {'url': 'https://newsinfo.inquirer.net/2307988/padilla-decision', 'text': 'A report.'}
VERA_COMMENTARY = {'url': 'https://verafiles.org/articles/the-resounding-fall-of-loren-legarda',
                   'text': 'A commentary.', 'is_opinion': True, 'sections': ['Commentary']}


class OpinionEvidenceTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app

    def test_opinion_sections_are_recognised(self):
        for url in ['https://opinion.inquirer.net/183377/the-vote',
                    'https://www.rappler.com/voices/thought-leaders/rear-view/',
                    'https://www.philstar.com/opinion/2026/09/19/2557313/piece',
                    'https://www.gmanetwork.com/news/opinion/content/1/x/story/',
                    'https://mb.com.ph/opinion/2026/9/19/on-the-budget',
                    'https://www.onenews.ph/columns/2026/9/19/the-week-in-review']:
            with self.subTest(url=url):
                self.assertTrue(is_opinion_url(url))

    def test_reporting_is_not_mistaken_for_opinion(self):
        for url in ['https://newsinfo.inquirer.net/2307988/padilla-decision',
                    'https://www.abs-cbn.com/news/nation/2026/9/16/palace-1610',
                    'https://verafiles.org/articles/fact-check-poquiz-statement',
                    'https://www.rappler.com/philippines/elections/parties-most/',
                    'https://mb.com.ph/2026/9/19/editorial-board-names-new-chair']:
            with self.subTest(url=url):
                self.assertFalse(is_opinion_url(url))

    def test_a_column_cannot_prove_a_factual_claim(self):
        # B07 claim 5 rested on an Inquirer opinion piece and a VERA Files commentary.
        self.assertTrue(self.app.opinion_evidence_blocked(COLUMN, FACTUAL))
        self.assertTrue(self.app.opinion_evidence_blocked(VERA_COMMENTARY, FACTUAL))

    def test_a_column_still_proves_what_its_author_wrote(self):
        self.assertFalse(self.app.opinion_evidence_blocked(COLUMN, ATTRIBUTED))
        self.assertFalse(self.app.opinion_evidence_blocked(VERA_COMMENTARY, ATTRIBUTED))

    def test_reporting_is_never_blocked(self):
        self.assertFalse(self.app.opinion_evidence_blocked(REPORT, FACTUAL))
        self.assertFalse(self.app.opinion_evidence_blocked(REPORT, ATTRIBUTED))

    def test_a_publisher_section_label_is_enough_without_a_telling_url(self):
        # VERA Files files commentary under a category; its address looks like any article.
        self.assertFalse(is_opinion_url(VERA_COMMENTARY['url']))
        self.assertTrue(self.app.is_opinion_article(VERA_COMMENTARY))


class CoverageScopeTests(unittest.TestCase):
    NASA = ('NASA\u2019s Hubble Space Telescope showcased a breathtaking image of spiral galaxy '
            'NGC 4258. The galaxy is located approximately 24 million light-years from Earth.')

    def answer(self, in_scope, subject='a NASA image of a distant galaxy'):
        return {'philippine_connection': in_scope, 'subject': subject, 'reason': 'checked'}

    def scope(self, text, in_scope=False, **kwargs):
        import json
        from types import SimpleNamespace
        message = SimpleNamespace(content=json.dumps(self.answer(in_scope, **kwargs)), refusal=None)
        reply = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason='stop')])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **_: reply)), close=lambda: None)
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}), \
             patch('openai.OpenAI', return_value=client):
            return philippine_scope(text)

    def test_a_post_with_no_philippine_connection_is_out_of_scope(self):
        result = self.scope(self.NASA, in_scope=False)
        self.assertFalse(result['in_scope'])
        self.assertIn('NASA image', out_of_scope_message(result['subject']))
        self.assertIn('not a judgment about whether the post is true', out_of_scope_message(''))

    def test_philippine_wording_keeps_a_post_in_scope_whatever_the_model_says(self):
        # A wrong "out of scope" silences a check that should have run, so the post text wins.
        for text in ['Marcos signed the budget on Monday.',
                     'Nagsara ang piso sa 62.513 kontra dolyar.',
                     'The DSWD will release cash aid in Cebu next week.',
                     'A Filipino student won a prize in Tokyo.']:
            with self.subTest(text=text):
                self.assertTrue(PHILIPPINE_MARKERS.search(text))
                self.assertTrue(self.scope(text, in_scope=False)['in_scope'])

    def test_a_foreign_event_involving_the_philippines_stays_in_scope(self):
        # B04: Duterte before the ICC in The Hague. B15: a Korean actor's Manila fan meeting.
        result = self.scope('Former president Rodrigo Duterte will remain in detention in The Hague.')
        self.assertTrue(result['in_scope'])
        self.assertEqual(result['decided_by'], 'post_text')

    def test_the_model_can_keep_an_unmarked_post_in_scope(self):
        result = self.scope('A Southeast Asian summit opened today.', in_scope=True)
        self.assertTrue(result['in_scope'])
        self.assertEqual(result['decided_by'], 'review')

    def test_a_failed_check_never_blocks_a_post(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}), \
             patch('openai.OpenAI', side_effect=RuntimeError('provider down')):
            result = philippine_scope('A galaxy far away.')
        self.assertTrue(result['in_scope'])
        self.assertEqual(result['reason'], 'scope_check_failed')


if __name__ == '__main__':
    unittest.main()
