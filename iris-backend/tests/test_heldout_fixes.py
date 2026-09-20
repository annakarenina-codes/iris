"""Two corrections measured on held-out batch 1: the date ceiling, and scripture as news."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.attribution_integrity import is_calendar_date
from pipeline.coverage_scope import SCRIPTURE_VERDICT, scripture_message, scriptural_narrative
from pipeline.evidence_urls import article_url_rejection, is_staging_host

GO = {'claim_type': 'attributed_statement',
      'attribution': {'speaker': 'Sen. Bong Go', 'date': 'Saturday',
                      'statement': 'Go opposes the passport fee increase.'}}
DATED = {'claim_type': 'attributed_statement',
         'attribution': {'speaker': 'Sen. Robin Padilla', 'date': 'Sept. 18',
                         'statement': 'Padilla said he will not run.'}}
ARTICLE = {'url': 'https://mb.com.ph/2026/09/20/go-passport-fees/', 'status': 'extracted',
           'text': 'Sen. Bong Go opposes the passport fee increase, he said over the weekend.'}


class WeekdayAnchorTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app

    def test_a_weekday_is_not_a_calendar_date(self):
        for phrase in ['Saturday', 'Last Friday', 'this week', 'Monday', 'kahapon']:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_calendar_date(phrase))

    def test_a_day_of_a_month_is(self):
        for phrase in ['Sept. 18', 'September 18, 2026', 'Setyembre 18', '18 September']:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_calendar_date(phrase))

    def test_a_weekday_no_source_prints_does_not_cap_the_verdict(self):
        # H14: three claims the review had verified were downgraded over the word "Saturday".
        self.assertEqual(self.app.cap_unconfirmed_date('Verified', 'Supported.', GO, [ARTICLE]),
                         ('Verified', 'Supported.'))

    def test_a_calendar_date_no_source_states_still_caps(self):
        # C06 keeps its ceiling: the claim named a day of a month and no article printed it.
        verdict, message = self.app.cap_unconfirmed_date('Verified', 'Supported.', DATED, [ARTICLE])
        self.assertEqual(verdict, 'Partially Verified')
        self.assertIn('Sept. 18', message)


class StagingHostTests(unittest.TestCase):
    def test_a_publishers_test_site_is_not_the_publisher(self):
        for url in ['https://qa.philstar.com/opinion/2012/07/01/823288/x',
                    'https://staging.gmanetwork.com/news/x/story/',
                    'https://beta.rappler.com/philippines/x/']:
            with self.subTest(url=url):
                self.assertTrue(is_staging_host(url))
                self.assertEqual(article_url_rejection(url), 'publisher_staging_host')

    def test_editorial_subdomains_are_untouched(self):
        for url in ['https://newsinfo.inquirer.net/2308141/s-cotabato-suspends-classes',
                    'https://globalnation.inquirer.net/338588/duterte-defense',
                    'https://tempo.mb.com.ph/2026/09/20/senate-eyes-school-safety',
                    'https://www.philstar.com/headlines/2026/09/14/2556203/historic-barmm-vote']:
            with self.subTest(url=url):
                self.assertFalse(is_staging_host(url))
                self.assertIsNone(article_url_rejection(url))


class ScriptureTests(unittest.TestCase):
    H22 = ('She had been suffering for 12 years. But when she heard Jesus was passing by, she did '
           'not wait for the perfect words. She believed that even touching the hem of His garment '
           'could change everything. Jesus said, Daughter, your faith has healed you.')

    def test_a_post_retelling_scripture_is_not_checked(self):
        self.assertTrue(scriptural_narrative(self.H22))
        self.assertEqual(SCRIPTURE_VERDICT, 'No Checkable Claims')
        self.assertIn('not a judgment about', scripture_message())

    def test_a_verse_reference_is_enough(self):
        self.assertTrue(scriptural_narrative('Reflect on Matthew 9:20 today and be encouraged.'))

    def test_religion_in_the_news_is_still_checked(self):
        # The owner's carve-out: religious people and activities reported in Philippine news.
        for text in ['Cebu Archbishop Jose Palma said the Gospel calls for mercy, in a homily in Cebu City.',
                     'The Iglesia ni Cristo distributed relief packs to Bulacan families this week.',
                     'Thank God the flood in Marikina subsided, residents said.',
                     'The DSWD released cash aid to flood victims in Cotabato.']:
            with self.subTest(text=text):
                self.assertFalse(scriptural_narrative(text))

    def test_a_single_passing_mention_is_not_scripture(self):
        self.assertFalse(scriptural_narrative('The choir sang a psalm at the opening.'))


if __name__ == '__main__':
    unittest.main()
