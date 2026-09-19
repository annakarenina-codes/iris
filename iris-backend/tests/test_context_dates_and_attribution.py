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


if __name__ == '__main__':
    unittest.main()
