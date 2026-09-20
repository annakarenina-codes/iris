"""Borrowed dates stay with their own subject; reported speech stays whole."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.component_context import (FIELDS, clause_span, limit_inherited_times,
                                        needs_context_review, prepare_components)

C01 = ('Davao City Mayor Sebastian “Baste” Duterte has been subpoenaed to testify in the impeachment '
       'trial of his sister, Vice President Sara Duterte, on Sept. 23, as the Senate impeachment court '
       'examines allegations of unexplained wealth against her.')
C07 = ('HEALING ERA LOOK: Moira Dela Torre faced the media earlier today, Sept. 17, in Quezon City, to talk '
       'about her upcoming concert “Where It All Started,” set for Oct. 4. Dela Torre opened up about '
       'her healing journey after a series of heartbreaks and controversies.')


def ref(text, quote, origin='source_context'):
    start = text.index(quote)
    return {'origin': origin, 'quote': quote, 'start': start, 'end': start + len(quote)}


def context(subject='', action='', time=None):
    values = {k: [] for k in FIELDS}
    if subject:
        values['subject'] = [{'origin': 'claim', 'quote': subject}]
    if action:
        values['action'] = [{'origin': 'claim', 'quote': action}]
    if time:
        values['time'] = [time]
    return values


class BorrowedDateTests(unittest.TestCase):
    def test_date_of_another_subjects_clause_is_dropped(self):
        anchors = {'subject': [{'origin': 'claim', 'quote': 'The Senate impeachment court'}],
                   'time': [ref(C01, 'on Sept. 23')]}
        dropped = limit_inherited_times(anchors, C01)
        self.assertEqual([r['quote'] for r in dropped], ['on Sept. 23'])
        self.assertEqual(anchors['time'], [])

    def test_object_listed_as_subject_does_not_keep_anothers_date(self):
        # Seen live: the context step also listed the object (Sara Duterte) as a subject.
        claim = ('The Senate impeachment court is examining allegations of unexplained wealth '
                 'against Vice President Sara Duterte.')
        anchors = {'subject': [ref(claim, 'The Senate impeachment court', origin='claim'),
                               ref(claim, 'Vice President Sara Duterte', origin='claim')],
                   'action': [ref(claim, 'is examining', origin='claim')],
                   'time': [ref(C01, 'on Sept. 23')]}
        self.assertEqual([r['quote'] for r in limit_inherited_times(anchors, C01)], ['on Sept. 23'])

    def test_follow_up_keeps_the_date_of_its_own_event(self):
        anchors = {'subject': [{'origin': 'claim', 'quote': 'Dela Torre'}], 'time': [ref(C07, 'Sept. 17')]}
        self.assertEqual(limit_inherited_times(anchors, C07), [])
        self.assertEqual([r['quote'] for r in anchors['time']], ['Sept. 17'])

    def test_pronoun_subject_keeps_borrowed_date(self):
        anchors = {'subject': [{'origin': 'claim', 'quote': 'She'}], 'time': [ref(C07, 'Oct. 4')]}
        self.assertEqual(limit_inherited_times(anchors, C07), [])

    def test_claims_own_date_is_never_dropped(self):
        claim = 'The court met on Sept. 23.'
        anchors = {'subject': [{'origin': 'claim', 'quote': 'The court'}],
                   'time': [ref(claim, 'Sept. 23', origin='claim')]}
        self.assertEqual(limit_inherited_times(anchors, C01), [])

    def test_abbreviated_month_is_not_a_sentence_end(self):
        start = C01.index('Sept. 23')
        left, right = clause_span(C01, start, start + len('Sept. 23'))
        self.assertIn('Baste', C01[left:right])
        self.assertNotIn('examines', C01[left:right])

    def test_dropped_date_does_not_trigger_another_context_review(self):
        claim = 'The Senate impeachment court examines allegations of unexplained wealth against her.'
        units = prepare_components(claim, [claim], [context('The Senate impeachment court', 'examines',
                                                             ref(C01, 'on Sept. 23'))], C01)
        self.assertEqual([r['quote'] for r in units[0]['inherited_time_dropped']], ['on Sept. 23'])
        self.assertFalse(needs_context_review(claim, C01, units))


class ParaphrasedContextTests(unittest.TestCase):
    CLAIM = ('The suspects remain at large, and investigators are reviewing CCTV footage, '
             'interviewing witnesses, and pursuing leads.')

    def test_filled_in_ellipsis_is_dropped_and_the_claim_still_reviewed(self):
        # Seen live in A03: the model wrote "investigators are interviewing witnesses", which is
        # not one contiguous span of the claim.
        anchors = context('investigators', 'are reviewing')
        anchors['event'] = [{'origin': 'claim', 'quote': 'investigators are interviewing witnesses'}]
        units = prepare_components(self.CLAIM, [self.CLAIM], [anchors])
        self.assertEqual([u['assertion'] for u in units], [self.CLAIM])
        self.assertEqual(units[0]['anchors']['event'], [])
        self.assertEqual([r['field'] for r in units[0]['ungrounded_dropped']], ['event'])

    def test_structurally_invalid_context_still_fails(self):
        with self.assertRaises(ValueError):
            prepare_components(self.CLAIM, [self.CLAIM], [{'subject': 'not a list'}])


class ReportedSpeechTests(unittest.TestCase):
    CLAIM = ('Interior Secretary Jonvic Remulla announced that Austria did not accept the asylum '
             'application of former presidential spokesperson Harry Roque.')

    def test_that_clause_rejoins_its_reporting_verb(self):
        split = self.CLAIM.index('that Austria')
        parts = [self.CLAIM[:split].strip(), self.CLAIM[split:]]
        units = prepare_components(self.CLAIM, parts, [
            context('Interior Secretary Jonvic Remulla', 'announced'),
            context('Austria', 'did not accept')])
        self.assertEqual([u['assertion'] for u in units], [self.CLAIM])

    def test_reporting_verb_without_that_keeps_its_content(self):
        # B02, Facebook's own translation: no "that" after "said".
        claim = ('Malaca\u00f1ang said the president has no business interfering with the issue of the '
                 'necessary votes to convict Vice President Sara Duterte in the impeachment trial.')
        split = claim.index('the president')
        units = prepare_components(claim, [claim[:split].strip(), claim[split:]], [
            context('Malaca\u00f1ang', 'said'), context('the president', 'has no business interfering')])
        self.assertEqual([u['assertion'] for u in units], [claim])

    def test_according_to_frame_keeps_its_content(self):
        claim = 'According to Malaca\u00f1ang, the president will not interfere in the vote.'
        split = claim.index('the president')
        units = prepare_components(claim, [claim[:split].strip(), claim[split:]], [
            context('Malaca\u00f1ang', 'According to'), context('the president', 'will not interfere')])
        self.assertEqual(len(units), 1)

    def test_complete_attributed_sentence_is_not_merged_with_the_next(self):
        claim = 'The suspect fled, the police said. Officers later found the car.'
        parts = ['The suspect fled, the police said.', 'Officers later found the car.']
        units = prepare_components(claim, parts, [context('The suspect', 'fled'),
                                                  context('Officers', 'found')])
        self.assertEqual(len(units), 2)

    def test_independent_clauses_still_split(self):
        claim = 'Remulla announced the plan. Austria rejected the application.'
        parts = ['Remulla announced the plan.', 'Austria rejected the application.']
        units = prepare_components(claim, parts, [context('Remulla', 'announced'),
                                                  context('Austria', 'rejected')])
        self.assertEqual(len(units), 2)


class SpeakerTests(unittest.TestCase):
    POST = ('LOOK: Sen. Robinhood \u201cRobin\u201d Padilla announced on Friday, Sept. 18, that he has no '
            'plans of running in future elections.')

    def test_quoted_nickname_does_not_hide_the_speaker(self):
        from pipeline.attribution_integrity import attribution_phrase_match
        self.assertTrue(attribution_phrase_match('Sen. Robinhood Padilla', self.POST))
        self.assertTrue(attribution_phrase_match('Robin Padilla', self.POST))
        self.assertFalse(attribution_phrase_match('Sara Duterte', self.POST))
        self.assertFalse(attribution_phrase_match('Padilla Robinhood', self.POST))

    def test_articles_may_use_any_name_form_the_post_supplies(self):
        from pipeline.attribution_integrity import speaker_phrase_match, speaker_variants
        speaker = 'Sen. Robinhood \u201cRobin\u201d Padilla'
        self.assertEqual(speaker_variants(speaker),
                         [['sen', 'robinhood', 'robin', 'padilla'], ['sen', 'robinhood', 'padilla'],
                          ['robinhood', 'padilla'], ['robin', 'padilla']])
        for text in ['Senator Robin Padilla said he will not run.',
                     'Robinhood Padilla announced his plans.',
                     'Sen. Robinhood \u201cRobin\u201d Padilla announced.']:
            self.assertTrue(speaker_phrase_match(speaker, text), text)

    def test_a_different_person_or_a_surname_alone_is_not_the_speaker(self):
        from pipeline.attribution_integrity import speaker_phrase_match
        speaker = 'Sen. Robinhood \u201cRobin\u201d Padilla'
        for text in ['Daniel Padilla spoke at the event.', 'Padilla was mentioned briefly.',
                     'Robin Duterte and Padilla spoke.']:
            self.assertFalse(speaker_phrase_match(speaker, text), text)
        self.assertFalse(speaker_phrase_match('Sara Duterte', 'Rodrigo Duterte spoke.'))
        self.assertFalse(speaker_phrase_match('Art Samaniego Jr.', 'A different politician Jr. spoke.'))

    def test_titles_and_institutions_still_match(self):
        from pipeline.attribution_integrity import speaker_phrase_match
        self.assertTrue(speaker_phrase_match('Vice President Sara Duterte', 'Sara Duterte posted bail.'))
        self.assertTrue(speaker_phrase_match('Malaca\u00f1ang', 'Malacanang announced a holiday.'))
        self.assertTrue(speaker_phrase_match(
            'Antonio Carpio', 'former Supreme Court senior associate justice Antonio Carpio said'))

    def test_named_speaker_survives_grounding(self):
        from pipeline.attribution_integrity import ground_attribution
        claim = {'claim_type': 'attributed_statement', 'claim_text': self.POST, 'normalized_claim': self.POST,
                 'attribution': {'speaker': 'Sen. Robinhood Padilla', 'role': None, 'statement': self.POST}}
        grounded = ground_attribution(claim, self.POST)
        self.assertEqual(grounded['attribution']['speaker'], 'Sen. Robinhood Padilla')
        self.assertEqual(grounded['attribution_integrity']['field_checks']['speaker'], 'grounded')

    def test_unresolved_speaker_does_not_reject_every_article(self):
        import app as iris
        article = {'url': 'https://www.philstar.com/headlines/2026/09/17/2556893/example',
                   'text': 'The judges ruled that the reports do not contain any new information.'}
        claim = {'claim_type': 'attributed_statement', 'attribution': {'speaker': None, 'role': 'judges'},
                 'normalized_claim': 'The judges ruled that the reports contain no new information.'}
        gate = iris.attribution_evidence_gate(article, claim, anchors_only=True)
        self.assertTrue(gate['matches'])
        self.assertEqual(gate['anchor_checks']['speaker'], 'unresolved_not_required')

    def test_named_speaker_absent_from_an_article_still_rejects_it(self):
        import app as iris
        article = {'url': 'https://www.philstar.com/headlines/2026/09/17/2556893/example',
                   'text': 'An unrelated agency began a different investigation this week.'}
        claim = {'claim_type': 'attributed_statement', 'attribution': {'speaker': 'Melvin Matibag'},
                 'normalized_claim': 'Matibag said his agency began the investigation.'}
        gate = iris.attribution_evidence_gate(article, claim, anchors_only=True)
        self.assertFalse(gate['matches'])
        self.assertIn('speaker', gate['missing'])


if __name__ == '__main__':
    unittest.main()
