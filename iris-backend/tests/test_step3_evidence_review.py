"""Step 3 evidence review: identity passages, silence vs contradiction, consistency recheck."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_context import FIELDS
from pipeline import component_evidence
from pipeline.component_evidence import (apply_entailment_checks, apply_event_identity_checks,
                                         event_identity_input, review_components,
                                         select_assessment_passages, validate_review,
                                         verbatim_recheck_targets)


def context(subject='', action=''):
    values = dict(subject=subject, action=action)
    return {k: [{'origin': 'claim', 'quote': values[k]}] if values.get(k) else [] for k in FIELDS}


def run_review(claim, articles, replies):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
            refusal=None, content=json.dumps(replies.pop(0))))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with patch('openai.OpenAI', return_value=client):
        result = review_components(claim, articles, claim)
    return result, calls


def check(supported=True, ids=(0,), contradicted=False, reason='Checked.'):
    return {'same_subject_and_event': True, 'assertion_supported': supported,
            'qualifiers_preserved': supported, 'contradicted': contradicted,
            'citation_ids': list(ids), 'reason': reason}


class IdentityPassageTests(unittest.TestCase):
    CLAIM = 'Woo-seok will hold his fan meeting at the Mall of Asia Arena on October 10, 2026.'
    ARTICLE = {'url': 'https://example.org/fan-meet',
               'text': 'Woo-seok will hold his fan meeting at the Mall of Asia Arena. '
                       'The fan meeting is set for October 10, 2026.'}

    def test_matched_identity_passages_join_the_component_citations(self):
        review = validate_review(self.CLAIM, [self.CLAIM], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': self.ARTICLE['url'],
                           'quote': 'Woo-seok will hold his fan meeting at the Mall of Asia Arena.'}]}], [self.ARTICLE])
        payload = event_identity_input(self.CLAIM, review, [self.ARTICLE])
        final = apply_event_identity_checks(self.CLAIM, review, [{'component_ids': [0], 'referent': self.CLAIM,
            'sources': {'0': {'status': 'matched', 'passage_ids': [0, 1], 'reason': 'Same fan meeting.'}}}],
            payload, [self.ARTICLE])
        quotes = [c['quote'] for c in final['components'][0]['citations']]
        self.assertEqual(len(quotes), 2)
        self.assertIn('The fan meeting is set for October 10, 2026.', quotes)

    def test_unmatched_identity_passages_are_not_added(self):
        review = validate_review(self.CLAIM, [self.CLAIM], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': self.ARTICLE['url'],
                           'quote': 'Woo-seok will hold his fan meeting at the Mall of Asia Arena.'}]}], [self.ARTICLE])
        payload = event_identity_input(self.CLAIM, review, [self.ARTICLE])
        final = apply_event_identity_checks(self.CLAIM, review, [{'component_ids': [0], 'referent': self.CLAIM,
            'sources': {'0': {'status': 'uncertain', 'passage_ids': [1], 'reason': 'Unclear.'}}}],
            payload, [self.ARTICLE])
        self.assertEqual(final['components'][0]['citations'], [])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_explicit_year_found_by_identity_check_reaches_final_review(self):
        replies = [
            {'split_after': [], 'contexts': [context('Woo-seok', 'will hold')]},
            {'assessments': {'0': {'status': 'supported', 'passage_ids': [0]}}},
            {'groups': [{'component_ids': [0], 'referent': self.CLAIM, 'sources': {
                '0': {'status': 'matched', 'passage_ids': [0, 1], 'reason': 'Same fan meeting.'}}}]},
            {'checks': {'0': check(ids=[0, 1], reason='Venue and dated passage together.')}},
        ]
        result, calls = run_review(self.CLAIM, [self.ARTICLE], replies)
        self.assertEqual(result['verdict'], 'Verified')
        entailment = json.loads(calls[-1]['messages'][1]['content'])
        self.assertEqual(len(entailment['candidates'][0]['passages']), 2)


class ContradictionTests(unittest.TestCase):
    CLAIM = 'The peso closed at 62.513 per dollar on Wednesday.'
    ARTICLE = {'url': 'https://example.org/peso', 'text': 'The peso closed at 62.625 per dollar on Wednesday.'}

    def reviewed(self):
        return validate_review(self.CLAIM, [self.CLAIM], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': self.ARTICLE['url'], 'quote': self.ARTICLE['text']}]}], [self.ARTICLE])

    def test_contradiction_overrides_support_and_is_reported(self):
        final = apply_entailment_checks(self.CLAIM, self.reviewed(), [
            {**check(ids=[0], contradicted=True, reason='Passage 0 gives 62.625.'), 'component_id': 0}],
            [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['evidence_relation'], 'contradicted')
        self.assertIn('contradicted by retrieved passages', final['reason'])

    def test_unsupported_without_contradiction_is_not_established(self):
        final = apply_entailment_checks(self.CLAIM, self.reviewed(), [
            {**check(supported=False, ids=[]), 'component_id': 0}], [self.ARTICLE])
        self.assertEqual(final['components'][0]['evidence_relation'], 'not_established')
        self.assertNotIn('contradicted', final['reason'])

    def test_supported_component_is_labeled_supported(self):
        claim = self.ARTICLE['text']
        reviewed = validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
            'citations': [{'url': self.ARTICLE['url'], 'quote': claim}]}], [self.ARTICLE])
        final = apply_entailment_checks(claim, reviewed, [{**check(ids=[0]), 'component_id': 0}], [self.ARTICLE])
        self.assertEqual(final['components'][0]['evidence_relation'], 'supported')


class ConsistencyRecheckTests(unittest.TestCase):
    CLAIM = 'Anna Wintour said the young star is interested in fashion and she thinks it is great.'
    FULL = {'url': 'https://example.org/full', 'text': CLAIM}
    PARTIAL = {'url': 'https://example.org/partial',
               'text': 'Anna Wintour said the young star is interested in fashion.'}

    def replies(self, *entailments):
        return [
            {'split_after': [], 'contexts': [context('Anna Wintour', 'said')]},
            {'assessments': {'0': {'status': 'supported', 'passage_ids': [0, 1]}}},
            {'groups': [{'component_ids': [0], 'referent': self.CLAIM, 'sources': {
                '0': {'status': 'matched', 'passage_ids': [0], 'reason': 'Same interview.'},
                '1': {'status': 'matched', 'passage_ids': [1], 'reason': 'Same interview.'}}}]},
            *entailments,
        ]

    def test_one_passage_omitting_a_quote_does_not_cancel_another(self):
        first = {'checks': {'0': check(supported=False, ids=[0, 1],
                                       reason='Only one of two passages contains the full quote.')}}
        second = {'checks': {'0': check(ids=[0], reason='Passage 0 contains the full quote.')}}
        result, calls = run_review(self.CLAIM, [self.FULL, self.PARTIAL], self.replies(first, second))
        self.assertEqual(result['verdict'], 'Verified')
        self.assertEqual(len(calls), 5)
        self.assertIn('CONSISTENCY RECHECK', calls[-1]['messages'][0]['content'])
        self.assertNotIn('CONSISTENCY RECHECK', calls[-2]['messages'][0]['content'])

    def test_recheck_happens_once_and_can_still_reject(self):
        refusal = {'checks': {'0': check(supported=False, ids=[0], reason='Different interview.')}}
        result, calls = run_review(self.CLAIM, [self.FULL, self.PARTIAL], self.replies(refusal, refusal))
        self.assertEqual(result['verdict'], 'Not Found')
        self.assertEqual(len(calls), 5)

    def test_contradicted_or_supported_components_are_not_rechecked(self):
        candidates = [{'component_id': 0, 'assertion_fragment': self.CLAIM,
                       'passages': [{'citation_id': 0, 'url': self.FULL['url'], 'quote': self.CLAIM}]}]
        self.assertEqual(verbatim_recheck_targets(candidates, [check(supported=False, contradicted=True)]), {})
        self.assertEqual(verbatim_recheck_targets(candidates, [check()]), {})
        self.assertEqual(verbatim_recheck_targets(candidates, [check(supported=False)]), {0: [0]})

    def test_short_fragments_and_paraphrases_are_not_rechecked(self):
        short = [{'component_id': 0, 'assertion_fragment': 'on Facebook.',
                  'passages': [{'citation_id': 0, 'url': 'u', 'quote': 'Concerns on Facebook grew.'}]}]
        self.assertEqual(verbatim_recheck_targets(short, [check(supported=False)]), {})
        paraphrase = [{'component_id': 0, 'assertion_fragment': self.CLAIM,
                       'passages': [{'citation_id': 0, 'url': 'u', 'quote': self.PARTIAL['text']}]}]
        self.assertEqual(verbatim_recheck_targets(paraphrase, [check(supported=False)]), {})

    def test_punctuation_and_curly_quotes_do_not_block_the_match(self):
        candidates = [{'component_id': 0, 'assertion_fragment': '“I think it’s great,” she said.',
                       'passages': [{'citation_id': 0, 'url': 'u',
                                     'quote': 'She added: "I think it\'s great" she said at the Open.'}]}]
        self.assertEqual(verbatim_recheck_targets(candidates, [check(supported=False)]), {0: [0]})


class PassageSelectionTests(unittest.TestCase):
    def passages(self, count):
        return [{'passage_id': i, 'url': f'https://example.org/{i // 10}', 'text': f'Passage number {i}.'}
                for i in range(count)]

    def test_small_pools_are_untouched(self):
        passages = self.passages(5)
        with patch.object(component_evidence, '_passage_scores', side_effect=AssertionError('ranked')):
            self.assertEqual(select_assessment_passages('claim', passages, limit=5), passages)

    def test_large_pool_keeps_most_similar_in_article_order_and_renumbers(self):
        passages = self.passages(10)
        scores = [0.1, 0.9, 0.2, 0.3, 0.8, 0.0, 0.7, 0.1, 0.2, 0.1]
        with patch.object(component_evidence, '_passage_scores', return_value=scores):
            kept = select_assessment_passages('claim', passages, limit=3)
        self.assertEqual([p['text'] for p in kept], ['Passage number 1.', 'Passage number 4.', 'Passage number 6.'])
        self.assertEqual([p['passage_id'] for p in kept], [0, 1, 2])

    def test_without_similarity_model_keeps_earliest_passages(self):
        with patch.object(component_evidence, '_passage_scores', return_value=None):
            kept = select_assessment_passages('claim', self.passages(10), limit=4)
        self.assertEqual([p['text'] for p in kept], [f'Passage number {i}.' for i in range(4)])


if __name__ == '__main__':
    unittest.main()
