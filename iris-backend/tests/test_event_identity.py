import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_context import FIELDS
from pipeline.component_evidence import (
    apply_event_identity_checks, apply_entailment_checks, event_identity_input,
    event_identity_schema, review_components, validate_review,
)


class EventIdentityTests(unittest.TestCase):
    def setUp(self):
        self.saved = json.loads((Path(__file__).parent / 'fixtures/cross_event_shooting.json')
                               .read_text(encoding='utf-8'))
        self.claim = self.saved['claim']
        self.articles = [self.saved['article']]
        self.reviewed = self.saved['saved_review']
        self.payload = event_identity_input(self.claim, self.reviewed, self.articles)

    def groups(self, status='mismatched', components=None, payload=None):
        payload = payload or self.payload
        return [{'component_ids': components if components is not None else [0, 1, 2],
                 'referent': "Shooting of the ex's new partner and the same suspect's arrest",
                 'sources': {str(s['source_id']): {
                     'status': status,
                     'passage_ids': [next(p['passage_id'] for p in payload['passages'] if p['url'] == s['url'])],
                     'reason': 'Participant relationships identify a different incident.'}
                     for s in payload['sources']}}]

    def apply(self, groups):
        return apply_event_identity_checks(self.claim, self.reviewed, groups, self.payload, self.articles)

    def test_saved_wrong_incident_cannot_lend_arrest_support(self):
        self.assertEqual(self.reviewed['verdict'], 'Partially Verified')
        self.assertEqual(self.reviewed['components'][2]['component'], 'arrested')
        final = self.apply(self.groups())
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['supporting_urls'], [])
        self.assertTrue(all(not p['citations'] for p in final['components']))
        self.assertEqual(final['components'][2]['event_rejections'][0]['status'], 'mismatched')

    def test_unestablished_identity_also_cannot_support_generic_fragment(self):
        self.assertEqual(self.apply(self.groups('uncertain'))['verdict'], 'Not Found')

    def test_correct_incident_can_retain_partial_support(self):
        # Synthetic positive control: an independently identified event, unknown motive.
        claim = 'Alex shot Ben after online taunts, and was arrested.'
        parts = ['Alex shot Ben', 'after online taunts,', 'and was arrested.']
        article = {'url': 'https://example.org/incident', 'text':
                   'Alex shot Ben in the station. Alex was arrested for shooting Ben. The motive is unknown.'}
        assessments = [{'component_id': i, 'status': 'not_supported' if i == 1 else 'supported',
                        'citations': [] if i == 1 else [{'url': article['url'], 'quote': article['text']}]} for i in range(3)]
        reviewed = validate_review(claim, parts, assessments, [article])
        payload = event_identity_input(claim, reviewed, [article])
        result = apply_event_identity_checks(claim, reviewed, self.groups('matched', payload=payload), payload, [article])
        self.assertEqual(result['verdict'], 'Partially Verified')
        self.assertEqual(result['components'][1]['status'], 'not_supported')
        self.assertEqual(result['components'][2]['status'], 'supported')

    def test_different_events_in_one_article_are_not_globally_blacklisted(self):
        parts = ['Alex was arrested.', 'Ben was arrested.']
        claim = ' '.join(parts)
        article = {'url': 'https://example.org/roundup', 'text':
                   'Alex was arrested at the station. Ben remained at large after a separate incident.'}
        reviewed = validate_review(claim, parts, [
            {'component_id': i, 'status': 'supported', 'citations': [
                {'url': article['url'], 'quote': article['text']}]} for i in range(2)], [article])
        payload = event_identity_input(claim, reviewed, [article])
        groups = self.groups('matched', [0], payload) + self.groups('mismatched', [1], payload)
        result = apply_event_identity_checks(claim, reviewed, groups, payload, [article])
        self.assertEqual(result['verdict'], 'Partially Verified')
        self.assertEqual(result['components'][0]['status'], 'supported')
        self.assertEqual(result['components'][1]['status'], 'not_supported')

    def test_wrong_article_does_not_blacklist_good_article(self):
        good = {'url': 'https://example.org/matching', 'text':
                "The man who shot his ex's new partner after online taunts was arrested."}
        reviewed = deepcopy(self.reviewed)
        reviewed['components'][2]['citations'].append({'url': good['url'], 'quote': good['text']})
        articles = [*self.articles, good]
        payload = event_identity_input(self.claim, reviewed, articles)
        groups = self.groups(payload=payload)
        good_id = next(str(s['source_id']) for s in payload['sources'] if s['url'] == good['url'])
        groups[0]['sources'][good_id]['status'] = 'matched'
        result = apply_event_identity_checks(self.claim, reviewed, groups, payload, articles)
        self.assertEqual(result['supporting_urls'], [good['url']])
        self.assertEqual(result['verdict'], 'Partially Verified')

    def test_incomplete_duplicate_and_invalid_groups_fail_closed(self):
        bad_groups = [None, [], self.groups(components=[0, 1]), self.groups(components=[0, 1, 1, 2]),
                      self.groups(components=[True, 0, 1, 2]), self.groups(components=[0, 1, 3])]
        for groups in bad_groups:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                self.apply(groups)

    def test_missing_identity_evidence_or_invalid_ids_are_technical_errors(self):
        for field, value in [('status', 'verified'), ('reason', ''), ('passage_ids', []),
                             ('passage_ids', [999]), ('passage_ids', [True]), ('passage_ids', [0, 0])]:
            groups = self.groups('matched')
            groups[0]['sources']['0'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.apply(groups)

    def test_identity_evidence_must_belong_to_reviewed_source(self):
        payload = deepcopy(self.payload)
        payload['passages'][0]['url'] = 'https://invented.invalid/article'
        with self.assertRaises(ValueError):
            apply_event_identity_checks(self.claim, self.reviewed, self.groups('matched'), payload, self.articles)

    def test_short_identity_fragment_can_accompany_substantial_passage(self):
        payload = deepcopy(self.payload)
        # A sentence splitter may separate an abbreviated location from its sentence.
        short_id = len(payload['passages'])
        payload['passages'].append({'passage_id': short_id, 'url': self.articles[0]['url'], 'text': 'Angono.'})
        groups = self.groups('matched')
        groups[0]['sources']['0']['passage_ids'] = [0, short_id]
        result = apply_event_identity_checks(self.claim, self.reviewed, groups, payload, self.articles)
        self.assertEqual(result['status'], 'ok')
        groups[0]['sources']['0']['passage_ids'] = [short_id]
        with self.assertRaises(ValueError):
            apply_event_identity_checks(self.claim, self.reviewed, groups, payload, self.articles)

    def test_matched_identity_does_not_override_relationship_or_speaker_check(self):
        reviewed = self.apply(self.groups('matched'))
        final = apply_entailment_checks(self.claim, reviewed, [{
            'component_id': 2, 'same_subject_and_event': True, 'assertion_supported': False,
            'qualifiers_preserved': True, 'citation_ids': [], 'reason': 'Missing specific support.'}], self.articles)
        self.assertEqual(final['verdict'], 'Not Found')

    def run_mock_pipeline(self, identity_reply):
        identity_reply = deepcopy(identity_reply)
        if isinstance(identity_reply, dict):
            for group in identity_reply.get('groups', []):
                group['component_ids'] = [0]
        replies = [{'split_after': [4, 10], 'contexts': [{k: [] for k in FIELDS} for _ in range(3)]},
                   {'assessments': {'0': {'status': 'supported', 'passage_ids': [0]}}}, identity_reply]
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            response = replies.pop(0)
            if isinstance(response, Exception):
                raise response
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
                message=SimpleNamespace(refusal=None, content=json.dumps(response)))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kw: client)}):
            result = review_components(self.claim, self.articles, source_context=self.saved['source_context'])
        return result, calls

    def test_pipeline_cannot_bypass_identity_rejection(self):
        result, calls = self.run_mock_pipeline({'groups': self.groups()})
        self.assertEqual(result['verdict'], 'Not Found')
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1]['response_format']['json_schema']['name'], 'event_identity_checks')
        payload = json.loads(calls[-1]['messages'][1]['content'])
        self.assertEqual(len(payload['components']), 1)  # Incomplete fragments are recombined.
        self.assertEqual(payload['claim'], self.claim)

    def test_gate_timeout_or_malformed_output_does_not_reuse_positive_result(self):
        for response in [TimeoutError('timeout'), {'groups': []}]:
            result, _ = self.run_mock_pipeline(response)
            self.assertEqual(result['status'], 'error')
            self.assertIsNone(result['verdict'])
            self.assertEqual(result['supporting_urls'], [])
            self.assertEqual(result['failed_stage'], 'event_identity_check')

    def test_strict_schema_requires_a_decision_for_every_source(self):
        group = event_identity_schema(3, 2, 10)['properties']['groups']['items']
        self.assertEqual(group['properties']['sources']['required'], ['0', '1'])
        self.assertEqual(group['properties']['component_ids']['items']['maximum'], 2)


if __name__ == '__main__':
    unittest.main()
