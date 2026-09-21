"""
The fixes of 22 September: quotations routed to checking and speakers named in queries.

No network access and no models.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.attribution_integrity import ground_attribution, speaker_query
from pipeline.content_profiler import _local_profile, _merge_openai_segment_advice, profile_content
from pipeline.text_boundaries import has_reported_quote

ATASHA = ("‘Bongga Ka 'Day’ musical star Atasha Muhlach opens up about the best advice she received "
          "from her parents, Aga Muhlach and Charlene Gonzales, on how to handle showbiz intrigues.\n"
          "“Of course they gave me the best advice, which was, ‘You know what, just work hard, keep on "
          "your feet on the ground and focus lang,’” she shared.\n"
          "#CelebrityNews #AtashaMuhlach #AgaMuhlach See less")


class SpeakersAreNamedInQueries(unittest.TestCase):
    def test_a_pronoun_attribution_searches_with_the_speakers_name(self):
        text = "“Of course they gave me the best advice,” she shared."
        claim = {'claim_type': 'attributed_statement', 'claim_text': text, 'normalized_claim': text,
                 'attribution': {'speaker': 'Atasha Muhlach'}}
        grounded = ground_attribution(claim, ATASHA)
        self.assertEqual(grounded['search_query'], f"Atasha Muhlach {text}")
        # The displayed claim and the assertion stay exactly as extracted.
        self.assertEqual(grounded['claim_text'], text)
        self.assertEqual(grounded['normalized_claim'], text)

    def test_a_sentence_that_names_the_speaker_is_searched_as_it_is(self):
        text = "Sen. Bong Go said the higher cost would add to the burden."
        self.assertEqual(speaker_query("Sen. Bong Go", text), text)

    def test_titles_are_left_out_of_the_added_name(self):
        self.assertEqual(speaker_query("Vice President Sara Duterte", "“…,” she said."),
                         "Sara Duterte “…,” she said.")
        self.assertEqual(speaker_query(None, "He added that OJT helps."), "He added that OJT helps.")


class QuotationsAreRoutedToChecking(unittest.TestCase):
    def test_a_quotation_she_shared_is_checked(self):
        profile = profile_content(ATASHA, None, use_ai=False)
        self.assertTrue(all(segment['eligible_for_verification'] for segment in profile['segments'][:2]))
        self.assertEqual(profile['segments'][1]['top_label'], 'factual_claim')

    def test_a_superlative_in_reported_speech_is_not_the_posts_opinion(self):
        first = _local_profile(ATASHA.split('\n')[0], None)['segments'][0]
        self.assertNotEqual(first['top_label'], 'opinion')
        self.assertTrue(first['eligible_for_verification'])

    def test_a_superlative_with_nobody_named_is_still_opinion(self):
        segment = _local_profile("THE COUNTRY DESERVES BETTER AND SO DO WE.", None)['segments'][0]
        self.assertEqual(segment['recommended_route'], 'stop_opinion_detected')

    def test_more_verbs_hand_a_quotation_to_its_speaker(self):
        for verb in ('shared', 'says', 'added', 'wrote', 'recalled', 'dagdag'):
            with self.subTest(verb=verb):
                self.assertTrue(has_reported_quote(f"“It is her life,” she {verb}."))
        self.assertFalse(has_reported_quote("“So handsome,” komento ng isang netizen."))

    def test_quote_advice_is_accepted_but_imagined_speech_stays_out(self):
        reported = "“We will not stop,” the mayor answered reporters."
        imagined = "Hinihintay ko tanong ni Robin: “Saan kayo graduate?”"
        for text, expected in ((reported, True), (imagined, False)):
            local = _local_profile(text, None)
            advice = {'status': 'ok', 'used': True, 'result': {'segments': [
                {'segment_id': s['segment_id'], 'top_label': 'quote', 'eligible_for_verification': True}
                for s in local['segments']]}}
            merged = _merge_openai_segment_advice(local, advice)
            with self.subTest(text=text):
                self.assertEqual(merged['segments'][0]['eligible_for_verification'], expected)


if __name__ == '__main__':
    unittest.main()
