"""Partial support inside a component: a missing detail or an unconfirmed date, never a different event."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_context import FIELDS, prepare_components, attach_context
from pipeline.component_evidence import (apply_entailment_checks, apply_event_identity_checks,
                                         event_identity_input, validate_review)


def context(subject='', action=''):
    values = dict(subject=subject, action=action)
    return {k: [{'origin': 'claim', 'quote': values[k]}] if values.get(k) else [] for k in FIELDS}


def check(component_id=0, same_event=True, supported=True, contradicted=False, ids=(0,),
          reason='Checked.', same_occurrence=None, missing_kind=None):
    return {'component_id': component_id, 'same_subject_and_event': same_event,
            'assertion_supported': supported, 'qualifiers_preserved': supported,
            'contradicted': contradicted, 'citation_ids': list(ids), 'reason': reason,
            'same_occurrence': same_event if same_occurrence is None else same_occurrence,
            'missing_kind': ('none' if supported else 'detail') if missing_kind is None else missing_kind}


def reviewed_with(claim, article, quote=None):
    return validate_review(claim, [claim], [{'component_id': 0, 'status': 'supported',
        'citations': [{'url': article['url'], 'quote': quote or article['text']}]}], [article])


class MissingDetailTests(unittest.TestCase):
    # A06: every source confirms the potholes, none mentions "peeling".
    CLAIM = 'Several parts of the road already have potholes and peeling despite recent work.'
    ARTICLE = {'url': 'https://example.org/edsa',
               'text': 'Several parts of the road already have potholes despite recent work on them.'}

    def test_same_event_with_one_missing_detail_is_partially_verified(self):
        final = apply_entailment_checks(self.CLAIM, reviewed_with(self.CLAIM, self.ARTICLE), [
            check(supported=False, reason='Potholes are confirmed; peeling is not mentioned.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Partially Verified')
        self.assertEqual(final['components'][0]['status'], 'partially_supported')
        self.assertEqual(final['components'][0]['evidence_relation'], 'partially_supported')
        self.assertTrue(final['components'][0]['citations'])
        self.assertIn('partially supported', final['reason'])

    def test_a_different_event_is_still_not_found(self):
        # B05: an arrest from another shooting must not support this incident.
        final = apply_entailment_checks(self.CLAIM, reviewed_with(self.CLAIM, self.ARTICLE), [
            check(same_event=False, supported=False, reason='Different road and incident.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['citations'], [])

    def test_a_contradicted_component_is_still_not_found(self):
        final = apply_entailment_checks(self.CLAIM, reviewed_with(self.CLAIM, self.ARTICLE), [
            check(contradicted=True, reason='The passage says the road is intact.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['evidence_relation'], 'contradicted')

    def test_no_cited_passage_is_still_not_found(self):
        final = apply_entailment_checks(self.CLAIM, reviewed_with(self.CLAIM, self.ARTICLE), [
            check(supported=False, ids=[], reason='Nothing relevant.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')


class OtherOccurrenceTests(unittest.TestCase):
    # B05, A09 and C07: the passages describe another occasion, however similar.
    CLAIM = "Man who shot his ex's new partner after online taunts arrested."
    ARTICLE = {'url': 'https://example.org/taytay',
               'text': 'The suspect is the former partner of the store owner where the victim works.'}

    def reviewed(self):
        return reviewed_with(self.CLAIM, self.ARTICLE)

    def test_a_different_occurrence_is_not_partial_support(self):
        final = apply_entailment_checks(self.CLAIM, self.reviewed(), [check(
            supported=False, same_occurrence=False, missing_kind='subject_or_event',
            reason='The victim is an employee, not the new partner.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['citations'], [])

    def test_same_occurrence_with_a_missing_detail_is_partial(self):
        final = apply_entailment_checks(self.CLAIM, self.reviewed(), [check(
            supported=False, same_occurrence=True, missing_kind='detail',
            reason='The taunts are not mentioned.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Partially Verified')

    def test_unknown_gap_is_not_partial_support(self):
        final = apply_entailment_checks(self.CLAIM, self.reviewed(), [check(
            supported=False, same_occurrence=True, missing_kind='other',
            reason='Unclear what the passages establish.')], [self.ARTICLE])
        self.assertEqual(final['verdict'], 'Not Found')


class UnconfirmedDateTests(unittest.TestCase):
    # C06: articles cover the same announcement but never print the claimed date.
    CLAIM = 'Padilla announced on Sept. 18 that he has no plans of running.'
    UNDATED = {'url': 'https://example.org/undated',
               'text': 'Padilla announced that he has no plans of running, his office said.'}
    OTHER_DATE = {'url': 'https://example.org/dated',
                  'text': 'Padilla announced on Aug. 4 that he has no plans of running.'}

    def identity(self, article, status='matched'):
        claim, units = self.CLAIM, prepare_components(self.CLAIM, [self.CLAIM], [context('Padilla', 'announced')])
        review = reviewed_with(claim, article)
        attach_context(review, units, claim)
        payload = event_identity_input(claim, review, [article])
        return apply_event_identity_checks(claim, review, [{'component_ids': [0], 'referent': claim,
            'sources': {'0': {'status': status, 'passage_ids': [0], 'reason': 'Same announcement.'}}}],
            payload, [article])

    def test_undated_source_supports_partially(self):
        final = self.identity(self.UNDATED)
        self.assertEqual(final['verdict'], 'Partially Verified')
        self.assertTrue(final['components'][0]['time_unconfirmed'])
        self.assertEqual(final['event_identity_checks'][0]['sources'][self.UNDATED['url']]['context_status'],
                         'unresolved')

    def test_a_different_date_is_rejected(self):
        final = self.identity(self.OTHER_DATE)
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['event_identity_checks'][0]['sources'][self.OTHER_DATE['url']]['status'],
                         'mismatched')

    def test_an_unconfirmed_date_cannot_become_verified_later(self):
        final = self.identity(self.UNDATED)
        after = apply_entailment_checks(self.CLAIM, final, [check(reason='Announcement matches.')], [self.UNDATED])
        self.assertEqual(after['verdict'], 'Partially Verified')
        self.assertTrue(after['entailment_checks'][0]['time_unconfirmed'])


if __name__ == '__main__':
    unittest.main()
