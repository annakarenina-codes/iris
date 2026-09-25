import sys
import unittest
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.attribution_integrity import ground_attribution, attribution_phrase_match


class IntegrityTests(unittest.TestCase):
    def test_invented_context_removed(self):
        text = "Padilla asked Win Gatchalian about the chamber's position on Monday."
        claim = dict(claim_type="attributed_statement", claim_text=text,
                     normalized_claim="Padilla said in an interview on social media",
                     attribution=dict(speaker="Padilla", source="social media", program="not specified", date="Monday"))
        result = ground_attribution(claim, text)
        self.assertEqual(result["normalized_claim"], text)
        self.assertIsNone(result["attribution"]["source"])
        self.assertIsNone(result["attribution"]["program"])
        self.assertEqual(result["attribution"]["date"], "Monday")

    def test_real_context_and_negation_preserved(self):
        text = "According to 24 Oras, Padilla did not ask Gatchalian to preside."
        result = ground_attribution(dict(claim_type="attributed_statement", claim_text=text,
            attribution=dict(speaker="Padilla", source="24 Oras")), text)
        self.assertEqual(result["attribution"]["source"], "24 Oras")
        self.assertIn("did not", result["normalized_claim"])

    def test_credit_only_source_removed_but_speaker_kept(self):
        text = "According to Melvin Matibag, the investigation has begun./via Zyann Ambrosi\r\n"
        result = ground_attribution(dict(claim_type="attributed_statement", claim_text=text.split('/')[0],
            attribution=dict(speaker="Melvin Matibag", source="Zyann Ambrosi")), text)
        self.assertIsNone(result['attribution']['source'])
        self.assertEqual(result['attribution']['speaker'], 'Melvin Matibag')
        self.assertEqual(result['attribution_integrity']['field_checks']['source'], 'credit_only')
        self.assertEqual(result['attribution_integrity']['incidental_credits'], ['Zyann Ambrosi'])

    def test_reporter_can_be_actual_speaker(self):
        text = 'Zyann Ambrosi said the road was closed.\nBy Zyann Ambrosi'
        result = ground_attribution(dict(claim_type='attributed_statement', claim_text=text.splitlines()[0],
            attribution=dict(speaker='Zyann Ambrosi')), text)
        self.assertEqual(result['attribution']['speaker'], 'Zyann Ambrosi')

    def test_credit_only_speaker_cannot_be_guessed(self):
        result = ground_attribution(dict(claim_type='attributed_statement', claim_text='The road closed.',
            attribution=dict(speaker='Zyann Ambrosi')), 'The road closed. | via Zyann Ambrosi')
        self.assertIsNone(result['attribution']['speaker'])

    def test_name_prefix_is_not_the_full_reporter_name(self):
        result = ground_attribution(dict(claim_type='attributed_statement', claim_text='Zyann Ambrosio spoke.',
            attribution=dict(speaker='Zyann Ambrosi')), 'Zyann Ambrosio spoke.')
        self.assertIsNone(result['attribution']['speaker'])

    def test_unicode_grounding_retains_input_spelling_and_negation(self):
        text = 'Malaca\u00f1ang said the president will not interfere.'
        result = ground_attribution(dict(claim_type='attributed_statement', claim_text=text,
            attribution=dict(speaker='Malacanang')), text)
        self.assertEqual(result['attribution']['speaker'], 'Malacanang')
        self.assertEqual(result['normalized_claim'], text)

    def test_explicit_interview_context_is_not_removed(self):
        text = 'Art Samaniego Jr. spoke on DZRH News, Special on Saturday, on July 4.\n/via Reporter Name'
        attribution = dict(speaker='Art Samaniego Jr.', source='DZRH News',
                           program='Special on Saturday', date='July 4')
        result = ground_attribution(dict(claim_type='attributed_statement', claim_text=text.splitlines()[0],
            attribution=attribution), text)
        for key, value in attribution.items():
            self.assertEqual(result['attribution'][key], value)

    def test_phrase_matching_is_bounded_and_preserves_small_words(self):
        for phrase, text, expected in [
            ('Malaca\u00f1ang', 'Malacanang said...', True),
            ('Cardi\u00f1o', 'Cardino said...', True),
            ('G.M.A.', 'GMA News', True),
            ('Robin Padilla', 'ROBIN-PADILLA spoke', True),
            ('Robin Padilla', 'Daniel Padilla met Robin yesterday.', False),
            ('Art Samaniego Jr.', 'Art Samaniego Sr. spoke.', False),
            ('Sara Duterte', 'Rodrigo Duterte spoke.', False),
            ('Solar boy', 'President Marcos spoke.', False),
            ('Special on Saturday', 'A special report arrived Saturday.', False),
            ('July 4', 'July 14', False),
            ('!!!', 'text', False),
            ('', 'text', False),
        ]:
            with self.subTest(phrase=phrase, text=text):
                self.assertEqual(attribution_phrase_match(phrase, text), expected)


class AttributionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app
        cls.iris = app
        cls.cases = json.loads((Path(__file__).parent / 'fixtures' / 'attribution_cases.json').read_text())

    def gate(self, speaker, body, **fields):
        return self.iris.attribution_evidence_gate(
            {'text': body}, {'claim_type': 'attributed_statement',
                             'attribution': {'speaker': speaker, **fields}}, anchors_only=True)

    def test_same_surname_or_suffix_does_not_identify_speaker(self):
        for speaker, body in [('Robin Padilla', 'Daniel Padilla spoke.'),
                              ('Art Samaniego Jr.', 'A different politician Jr. spoke.'),
                              ('Sara Duterte', 'Rodrigo Duterte spoke.')]:
            self.assertIn('speaker', self.gate(speaker, body)['missing'])

    def test_url_or_title_cannot_supply_missing_speaker(self):
        result = self.iris.attribution_evidence_gate(
            {'title': 'Robin Padilla', 'url': 'https://www.abs-cbn.com/robin-padilla', 'text': 'Someone spoke.'},
            {'claim_type': 'attributed_statement', 'attribution': {'speaker': 'Robin Padilla'}}, anchors_only=True)
        self.assertFalse(result['matches'])

    def test_unresolved_speaker_is_not_required_at_the_gate(self):
        # A speaker IRIS never resolved ("the judges") cannot be checked here. Requiring a name it
        # does not have rejected every article (saved cases B04, C06); the component review decides.
        gate = self.gate(None, 'A politician spoke.')
        self.assertTrue(gate['matches'])
        self.assertEqual(gate['anchor_checks']['speaker'], 'unresolved_not_required')

    def test_speaker_match_is_not_statement_confirmation(self):
        claim = {'claim_type': 'attributed_statement', 'attribution': {
            'speaker': 'Malaca\u00f1ang', 'statement': 'The president will not interfere.'}}
        article = {'text': 'Malacanang announced a holiday.'}
        self.assertTrue(self.iris.attribution_evidence_gate(article, claim, anchors_only=True)['matches'])
        result = self.iris.attribution_evidence_gate(article, claim)
        self.assertEqual(result['missing'], ['statement'])

    def test_a_required_program_cannot_be_ignored(self):
        result = self.gate('Art Samaniego Jr.', 'Art Samaniego Jr. spoke on DZRH News July 14.',
                           source='DZRH News', program='Special on Saturday', date='July 4')
        self.assertEqual(result['missing'], ['program'])

    def test_a_date_the_article_does_not_state_is_unconfirmed_rather_than_missing(self):
        # A news story rarely reprints the date, so excluding the article threw away the
        # coverage too (saved case C06). The verdict is capped instead; see cap_unconfirmed_date.
        result = self.gate('Art Samaniego Jr.', 'Art Samaniego Jr. spoke on DZRH News July 14.',
                           source='DZRH News', date='July 4')
        self.assertNotIn('date', result['missing'])
        self.assertEqual(result['anchor_checks']['date'], 'unconfirmed')
        self.assertFalse(result['date_confirmed'])

    def test_saved_malacanang_article_passes_accent_gate(self):
        case = next(c for c in self.cases if c['name'] == 'diacritic')
        claim = ground_attribution(case['claim'], case['input_text'])
        article = next(a for a in case['articles'] if 'palace-marcos-jr-won-t-interfere' in a['url'])
        self.assertEqual(article['word_count'], 284)
        result = self.iris.attribution_evidence_gate(article, claim, anchors_only=True)
        self.assertTrue(result['matches'], result)
        self.assertEqual(result['anchor_checks']['speaker'], 'normalized_phrase_match')

    def test_saved_reporter_credit_is_removed_without_inventing_support(self):
        case = next(c for c in self.cases if c['name'] == 'reporter_credit')
        claim = ground_attribution(case['claim'], case['input_text'])
        self.assertIsNone(claim['attribution']['source'])
        self.assertEqual(claim['attribution']['speaker'], 'Melvin Matibag')
        self.assertNotIn('Zyann', claim['normalized_claim'])
        article = next(a for a in case['articles'] if 'ginang-nasawi' in a['url'])
        self.assertIn('speaker', self.iris.attribution_evidence_gate(article, claim, anchors_only=True)['missing'])


if __name__ == "__main__":
    unittest.main()
