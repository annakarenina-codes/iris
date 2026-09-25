"""Routing a post whose every claim names nothing a source could confirm."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.checkable_claims import (MIN_GENERAL_CLAIMS, is_general_statement,
                                       only_general_statements, verifiable_handles)

ADVOCACY = {'contains_opinion': True, 'contains_recommendation': True}
REPORTING = {'contains_opinion': False, 'contains_recommendation': False}


def claim(text, claim_type='factual_claim'):
    return {'claim_text': text, 'normalized_claim': text, 'claim_type': claim_type}


B07 = [claim('One vote can influence the quality of education your children receive.'),
       claim('One vote can influence the opportunities available to workers.'),
       claim('One vote can influence the healthcare your family depends on.'),
       claim('One vote can influence the laws that shape your everyday life.'),
       claim('Some people vote based on popularity, catchy slogans, viral videos, family influence.')]


class HandleTests(unittest.TestCase):
    def test_a_sentence_with_nothing_to_look_up(self):
        for text in ['One vote can influence the quality of education your children receive.',
                     'A vote is not a gift to a politician.',
                     'The future we complain about tomorrow is often built by the choices of today.']:
            with self.subTest(text=text):
                self.assertEqual(verifiable_handles(text), [])

    def test_names_numbers_and_dates_are_handles(self):
        self.assertIn('name', verifiable_handles('Padilla said he will not run again.'))
        self.assertIn('name', verifiable_handles('The DSWD will release the aid.'))
        self.assertIn('number', verifiable_handles('The project is estimated to cost P1.2 billion.'))
        self.assertIn('date', verifiable_handles('He spoke on Friday about the budget.'))
        self.assertIn('date', verifiable_handles('Sa Setyembre, nagsalita siya.'))

    def test_a_capitalised_first_word_is_not_a_name(self):
        self.assertEqual(verifiable_handles('Many people think elections are about popularity.'), [])
        self.assertEqual(verifiable_handles('Imagine hiring a manager without checking.'), [])

    def test_an_attributed_claim_is_never_a_general_statement(self):
        # Someone said it, so a source can confirm that they said it.
        self.assertFalse(is_general_statement(claim('He said the vote matters.', 'attributed_statement')))


class RoutingTests(unittest.TestCase):
    def test_an_advocacy_post_of_general_statements_is_not_checked(self):
        self.assertTrue(only_general_statements(B07, ADVOCACY))

    def test_one_named_party_keeps_the_whole_post_checked(self):
        mixed = B07 + [claim('The DSWD released cash aid to flood victims.')]
        self.assertFalse(only_general_statements(mixed, ADVOCACY))

    def test_a_figure_anywhere_keeps_the_whole_post_checked(self):
        mixed = B07 + [claim('Turnout reached 83 percent of registered voters.')]
        self.assertFalse(only_general_statements(mixed, ADVOCACY))

    def test_a_post_that_does_not_read_as_advocacy_is_still_checked(self):
        self.assertFalse(only_general_statements(B07, REPORTING))

    def test_a_single_vague_claim_is_still_checked(self):
        # B05, a terse report naming nobody, is protected twice over: a lone claim never routes
        # here, and a capitalised opening word counts as a name rather than being assumed away.
        lone = [claim("Man who shot ex's new partner after online taunts arrested.")]
        self.assertFalse(is_general_statement(lone[0]))
        self.assertFalse(only_general_statements(lone, ADVOCACY))
        self.assertFalse(only_general_statements(lone * 2, ADVOCACY))
        self.assertEqual(MIN_GENERAL_CLAIMS, 2)

    def test_a_name_opening_a_sentence_is_still_a_name(self):
        # "Padilla said he will not run again." read as general until this was fixed.
        for text in ['Padilla said he will not run again.', 'Marcos signed the budget into law.',
                     'DSWD released the cash aid this week.']:
            with self.subTest(text=text):
                self.assertFalse(is_general_statement(claim(text)))

    def test_no_claims_at_all_is_not_this_rule(self):
        self.assertFalse(only_general_statements([], ADVOCACY))


if __name__ == '__main__':
    unittest.main()
