"""The Refuted verdict: only a VERA Files denial about this very occurrence can trigger it."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_evidence import (ENTAILMENT_SCHEMA, REFUTED_VERDICT, ComponentReviewError,
                                         apply_entailment_checks, require_completed_review,
                                         validate_review)

CLAIM = 'Retired Maj. Gen. Romeo Poquiz made a statement against President Ferdinand Marcos Jr.'
DENIAL = ('VERA Files found that there are no records of Poquiz making this statement against '
          'the Marcoses, and his family confirmed he did not write it.')
VERA = {'url': 'https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement',
        'source': 'VERA Files', 'text': DENIAL}
GMA = {'url': 'https://www.gmanetwork.com/news/topstories/nation/1001/poquiz/story/',
       'source': 'GMA News', 'text': DENIAL}


def check(component_id=0, contradiction_kind='denial', same_occurrence=True, ids=(0,),
          same_event=True, supported=False, reason='The passage denies the statement.'):
    return {'component_id': component_id, 'same_subject_and_event': same_event,
            'assertion_supported': supported, 'qualifiers_preserved': True,
            'contradicted': contradiction_kind != 'none', 'same_occurrence': same_occurrence,
            'missing_kind': 'none' if supported else 'subject_or_event',
            'contradiction_kind': contradiction_kind, 'citation_ids': list(ids), 'reason': reason}


def reviewed(article, claim=CLAIM, components=None):
    components = components or [claim]
    assessments = [{'component_id': i, 'status': 'supported',
                    'citations': [{'url': article['url'], 'quote': article['text']}]}
                   for i in range(len(components))]
    return validate_review(claim, components, assessments, [article])


class RefutedVerdictTests(unittest.TestCase):
    def test_the_reviewer_is_asked_which_kind_of_contradiction_it_found(self):
        item = ENTAILMENT_SCHEMA['properties']['checks']['items']
        self.assertIn('contradiction_kind', item['required'])
        self.assertEqual(item['properties']['contradiction_kind']['enum'],
                         ['none', 'denial', 'different_detail'])

    def test_a_vera_files_denial_refutes_the_claim(self):
        # C08 claim 2: the fact-check settles it, so "Not Found" would have misled the reader.
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check()], [VERA])
        self.assertEqual(final['verdict'], REFUTED_VERDICT)
        self.assertEqual(final['components'][0]['evidence_relation'], 'contradicted')
        self.assertEqual(final['supporting_urls'], [VERA['url']])
        self.assertTrue(final['reason'].startswith('VERA Files reports that this did not happen.'))

    def test_the_same_denial_from_a_news_outlet_does_not_refute(self):
        final = apply_entailment_checks(CLAIM, reviewed(GMA), [check()], [GMA])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['supporting_urls'], [])

    def test_a_differing_detail_is_not_a_refutation(self):
        # A wrong number or date leaves the claim unverified, not false.
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check(contradiction_kind='different_detail')],
                                        [VERA])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['evidence_relation'], 'contradicted')

    def test_a_denial_about_another_occurrence_is_not_a_refutation(self):
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check(same_occurrence=False)], [VERA])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_a_denial_about_another_subject_is_not_a_refutation(self):
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check(same_event=False)], [VERA])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_a_denial_with_no_cited_passage_is_not_a_refutation(self):
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check(ids=[])], [VERA])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_silence_is_not_a_denial(self):
        final = apply_entailment_checks(CLAIM, reviewed(VERA), [check(contradiction_kind='none')], [VERA])
        self.assertEqual(final['verdict'], 'Not Found')
        self.assertEqual(final['components'][0]['evidence_relation'], 'not_established')

    def test_a_refuted_part_decides_a_claim_whose_other_part_is_supported(self):
        claim = ('Romeo Poquiz is a retired Air Force major general. '
                 'He made a statement against President Ferdinand Marcos Jr.')
        parts = ['Romeo Poquiz is a retired Air Force major general.',
                 'He made a statement against President Ferdinand Marcos Jr.']
        profile = {'url': GMA['url'], 'source': 'GMA News',
                   'text': 'Romeo Poquiz is a retired Air Force major general who led the PAF health service.'}
        articles = [profile, VERA]
        review = validate_review(claim, parts, [
            {'component_id': 0, 'status': 'supported',
             'citations': [{'url': profile['url'], 'quote': profile['text']}]},
            {'component_id': 1, 'status': 'supported',
             'citations': [{'url': VERA['url'], 'quote': VERA['text']}]}], articles)
        final = apply_entailment_checks(claim, review, [
            check(component_id=0, contradiction_kind='none', supported=True, reason='Confirmed.'),
            check(component_id=1)], articles)
        self.assertEqual(final['verdict'], REFUTED_VERDICT)
        self.assertEqual(final['components'][0]['status'], 'supported')
        self.assertEqual(final['components'][1]['evidence_relation'], 'contradicted')
        # The fact-check leads, so the reader sees what the verdict rests on first.
        self.assertEqual(final['supporting_urls'], [VERA['url'], profile['url']])


class PublisherLookupTests(unittest.TestCase):
    """The passages handed to the reviewer carry no publisher name, only a URL and text."""

    PASSAGE = {'url': VERA['url'], 'text': VERA['text']}

    def test_the_publisher_map_decides_when_passages_carry_no_source(self):
        final = apply_entailment_checks(CLAIM, reviewed(self.PASSAGE), [check()], [self.PASSAGE],
                                        published_by={VERA['url']: 'VERA Files'})
        self.assertEqual(final['verdict'], REFUTED_VERDICT)

    def test_an_unnamed_publisher_cannot_refute(self):
        final = apply_entailment_checks(CLAIM, reviewed(self.PASSAGE), [check()], [self.PASSAGE])
        self.assertEqual(final['verdict'], 'Not Found')

    def test_the_review_hands_the_publisher_map_to_every_entailment_check(self):
        # Without this the VERA rule can never match, which is how it first shipped broken.
        import inspect
        from pipeline import component_evidence
        body = inspect.getsource(component_evidence.review_components)
        self.assertIn("publishers = {article['url']: article.get('source') for article in articles}", body)
        self.assertEqual(body.count('published_by=publishers'), body.count('apply_entailment_checks('))


class ClientContractTests(unittest.TestCase):
    def test_a_refuted_verdict_must_carry_a_source(self):
        import app
        self.assertIn(REFUTED_VERDICT, app.VERDICTS_NEEDING_EVIDENCE)

    def test_a_refuted_review_is_a_completed_review(self):
        # It reached the client as a 503 until the verdict was added here.
        review = {'status': 'ok', 'verdict': REFUTED_VERDICT, 'supporting_urls': [VERA['url']],
                  'components': [{'component': CLAIM, 'status': 'not_supported', 'citations': []}],
                  'reason': 'VERA Files reports that this did not happen.'}
        self.assertEqual(require_completed_review(dict(review))['verdict'], REFUTED_VERDICT)

    def test_a_refuted_review_without_a_source_is_rejected(self):
        review = {'status': 'ok', 'verdict': REFUTED_VERDICT, 'supporting_urls': [],
                  'components': [{'component': CLAIM, 'status': 'not_supported', 'citations': []}],
                  'reason': 'VERA Files reports that this did not happen.'}
        with self.assertRaises(ComponentReviewError):
            require_completed_review(review)


if __name__ == '__main__':
    unittest.main()
