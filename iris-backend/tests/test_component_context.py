import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_context import (FIELDS, prepare_components, temporal_context_decision, attach_context,
    needs_context_review, merge_context_review)
from pipeline.component_evidence import (review_components, validate_review,
    event_identity_input, apply_event_identity_checks)


def context(subject='', action='', event='', time='', speaker='', origin='claim'):
    values = dict(subject=subject, action=action, event=event, time=time, speaker=speaker)
    return {k: [{'origin': origin, 'quote': values[k]}] if values.get(k) else [] for k in FIELDS}


class ComponentContextTests(unittest.TestCase):
    def test_arrest_fragment_recombines_with_incident(self):
        claim = "Man who shot ex's new partner after online taunts arrested."
        parts = [claim[:-9].rstrip(), 'arrested.']
        units = prepare_components(claim, parts, [context('Man', 'shot'), context('Man', 'arrested')])
        self.assertEqual([u['assertion'] for u in units], [claim])

    def test_causes_is_not_independent_even_with_bad_action_annotation(self):
        claim = 'Tony pointed to her years of championing environmental causes.'
        units = prepare_components(claim, [claim[:-7].rstrip(), 'causes.'],
                                   [context('Tony', 'pointed'), context('Tony', 'causes')])
        self.assertEqual([u['assertion'] for u in units], [claim])

    def test_job_title_cannot_earn_its_own_component(self):
        claim = 'Education Secretary Angara said OJT would increase to 640 hours.'
        units = prepare_components(claim, ['Education Secretary Angara', claim[26:].strip()],
                                   [context('Education Secretary Angara', 'said'), context('Angara', 'said')])
        self.assertEqual([u['assertion'] for u in units], [claim])

    def test_short_complete_assertions_remain_separate(self):
        claim = 'Cases rose. Deaths fell.'
        units = prepare_components(claim, ['Cases rose.', 'Deaths fell.'],
                                   [context('Cases', 'rose'), context('Deaths', 'fell')])
        self.assertEqual(len(units), 2)

    def test_non_ascii_negation_and_whitespace_preserved(self):
        claim = 'Cardi\u00f1o did not confess.\n  Police investigated.'
        c = context('Cardi\u00f1o', 'did not confess')
        c['negation'] = [{'origin': 'claim', 'quote': 'not'}]
        units = prepare_components(claim, ['Cardi\u00f1o did not confess.', 'Police investigated.'],
                                   [c, context('Police', 'investigated')])
        for u in units:
            self.assertEqual(claim[u['start']:u['end']], u['assertion'])
        self.assertEqual(units[0]['anchors']['negation'][0]['quote'], 'not')

    def test_invented_context_is_dropped_not_inferred(self):
        units = prepare_components('Someone spoke.', ['Someone spoke.'], [context('Robin Padilla', 'spoke')])
        self.assertEqual(units[0]['anchors']['subject'], [])
        self.assertEqual([r['quote'] for r in units[0]['ungrounded_dropped']], ['Robin Padilla'])

    def test_missing_context_fails_closed(self):
        with self.assertRaises(ValueError):
            prepare_components('Someone spoke.', ['Someone spoke.'], [])

    def test_context_count_mismatch_recombines_without_rewriting(self):
        claim = 'Tony pointed to her years of championing environmental causes.'
        units = prepare_components(claim, [claim[:-7].rstrip(), 'causes.'],
                                   [context('Tony', 'pointed')])
        self.assertEqual([u['assertion'] for u in units], [claim])
        self.assertIn('partition_repair', units[0])

    def test_mismatch_repair_does_not_accept_invented_context(self):
        units = prepare_components('Someone spoke. Police listened.', ['Someone spoke.', 'Police listened.'],
                                   [context('Robin Padilla', 'spoke')])
        self.assertEqual(units[0]['anchors']['subject'], [])
        self.assertEqual([r['quote'] for r in units[0]['ungrounded_dropped']], ['Robin Padilla'])
        self.assertIn('partition_repair', units[0])

    def test_asserted_date_cannot_be_omitted(self):
        claim = 'The peso closed lower on September 9.'
        units = prepare_components(claim, [claim], [context('peso', 'closed')])
        result = temporal_context_decision(units, ['The peso closed lower on September 8.'])
        self.assertEqual(result['status'], 'conflicting')

    def test_inherited_interview_date_filters_older_interview(self):
        claim = 'Dela Torre discussed her healing journey.'
        source = 'Moira Dela Torre faced the media on Sept. 17 in Quezon City. ' + claim
        c = context('Dela Torre', 'discussed')
        c['event'] = [{'origin': 'source_context', 'quote': 'Moira Dela Torre faced the media on Sept. 17 in Quezon City.'}]
        c['time'] = [{'origin': 'source_context', 'quote': 'Sept. 17'}]
        units = prepare_components(claim, [claim], [c], source)
        self.assertEqual(temporal_context_decision(units, ['She discussed healing after her 2022 breakup.'])['status'], 'unresolved')
        self.assertEqual(temporal_context_decision(units, ['She discussed healing at the September 17 media event.'])['status'], 'matching')

    def test_no_time_anchor_does_not_block_undated_fact(self):
        units = prepare_components('Cases rose.', ['Cases rose.'], [context('Cases', 'rose')])
        self.assertFalse(temporal_context_decision(units, ['Cases rose.'])['enforced'])

    def test_missing_dated_antecedent_requests_separate_review(self):
        claim = 'The singer discussed healing.'
        source = 'The singer met the media on Sept. 17. ' + claim
        units = prepare_components(claim, [claim], [context('singer', 'discussed')], source)
        self.assertTrue(needs_context_review(claim, source, units))
        correction = context(time='Sept. 17', origin='source_context')
        merge_context_review(units, [correction], claim, source)
        self.assertFalse(needs_context_review(claim, source, units))
        self.assertEqual(units[0]['anchors']['subject'][0]['quote'], 'singer')

    def test_unrelated_post_date_need_not_be_assigned(self):
        claim = 'Cases rose.'
        source = 'A concert is on October 4. Cases rose.'
        units = prepare_components(claim, [claim], [context('Cases', 'rose')], source)
        merge_context_review(units, [context()], claim, source)
        self.assertEqual(units[0]['anchors']['time'], [])
        self.assertFalse(temporal_context_decision(units, ['Cases rose.'])['enforced'])

    def test_context_review_drops_invented_year(self):
        claim = 'The singer discussed healing.'
        source = 'The singer met the media on Sept. 17. ' + claim
        units = prepare_components(claim, [claim], [context('singer', 'discussed')], source)
        merged = merge_context_review(units, [context(time='Sept. 17, 2026', origin='source_context')], claim, source)
        self.assertEqual(merged[0]['anchors']['time'], [])
        self.assertEqual([r['quote'] for r in merged[0]['ungrounded_dropped']], ['Sept. 17, 2026'])

    def test_context_review_is_wired_before_assessment(self):
        claim = 'The singer discussed healing.'
        source = 'The singer met the media on Sept. 17. ' + claim
        replies = [
            {'split_after': [], 'contexts': [context('singer', 'discussed')]},
            {'contexts': [context(time='Sept. 17', origin='source_context')]},
            {'assessments': {'0': {'status': 'not_supported', 'passage_ids': []}}},
        ]
        calls = []
        def create(**kwargs):
            calls.append(json.loads(kwargs['messages'][1]['content']))
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=
                SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0))))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch('openai.OpenAI', return_value=client):
            result = review_components(claim, [], source)
        self.assertEqual(result['verdict'], 'Not Found')
        self.assertEqual(calls[2]['component_contexts'][0]['anchors']['time'][0]['quote'], 'Sept. 17')
        self.assertTrue(result['components'][0]['context']['context_reviewed'])

    def test_publication_url_cannot_establish_event_date(self):
        claim = 'Dela Torre spoke on September 17.'
        units = prepare_components(claim, [claim], [context('Dela Torre', 'spoke')])
        article = {'url': 'https://example.org/2026/09/17/news', 'text': 'Dela Torre spoke about healing in an older interview.'}
        review = validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
                                  'citations': [{'url': article['url'], 'quote': article['text']}]}], [article])
        attach_context(review, units, claim)
        payload = event_identity_input(claim, review, [article])
        final = apply_event_identity_checks(claim, review, [{'component_ids': [0], 'referent': claim,
            'sources': {'0': {'status': 'matched', 'passage_ids': [0], 'reason': 'Model approved.'}}}], payload, [article])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['event_identity_checks'][0]['sources'][article['url']]['context_status'], 'unresolved')

    def test_date_matching_still_needs_semantic_identity(self):
        claim = 'Alex was arrested on September 17.'
        units = prepare_components(claim, [claim], [context('Alex', 'was arrested')])
        article = {'url': 'https://example.org/news', 'text': 'Ben was arrested on September 17 for another incident.'}
        review = validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
                                  'citations': [{'url': article['url'], 'quote': article['text']}]}], [article])
        attach_context(review, units, claim)
        payload = event_identity_input(claim, review, [article])
        final = apply_event_identity_checks(claim, review, [{'component_ids': [0], 'referent': claim,
            'sources': {'0': {'status': 'mismatched', 'passage_ids': [0], 'reason': 'Different person.'}}}], payload, [article])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_context_survives_live_pipeline_shape_and_reaches_reviewers(self):
        claim = 'Cases rose in the city.'
        article = {'url': 'https://example.org/news', 'text': claim}
        replies = [
            {'split_after': [], 'contexts': [context('Cases', 'rose')]},
            {'assessments': {'0': {'status': 'supported', 'passage_ids': [0]}}},
            {'groups': [{'component_ids': [0], 'referent': claim, 'sources': {
                '0': {'status': 'matched', 'passage_ids': [0], 'reason': 'Same assertion.'}}}]},
            {'checks': {'0': {'same_subject_and_event': True, 'assertion_supported': True,
                'qualifiers_preserved': True, 'citation_ids': [0], 'reason': 'Explicit support.'}}},
        ]
        calls = []
        def create(**kwargs):
            calls.append(json.loads(kwargs['messages'][1]['content']))
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=
                SimpleNamespace(refusal=None, content=json.dumps(replies.pop(0))))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch('openai.OpenAI', return_value=client):
            result = review_components(claim, [article], 'Original post: ' + claim)
        self.assertEqual(result['verdict'], 'Verified')
        self.assertEqual(result['original_claim'], claim)
        self.assertEqual(result['components'][0]['context']['assertion'], claim)
        self.assertFalse(result['components'][0]['context']['context_is_evidence'])
        self.assertIn('component_contexts', calls[1])
        self.assertIn('context', calls[2]['components'][0])
        self.assertIn('component_contexts', calls[3])


if __name__ == '__main__':
    unittest.main()
