"""Source policy and search-excerpt evidence. No network or API calls."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as iris_app
from pipeline import search
from pipeline.evidence_urls import article_url_rejection
from pipeline.sources import get_all_sources, get_source_by_name, uses_search_excerpts

INQUIRER = 'https://entertainment.inquirer.net/684038/moira-dela-torre-ex-husband-jason-hernandez-have-moved-forward-now-civil'
VERA = 'https://verafiles.org/articles/fact-check-example'
GMA = 'https://www.gmanetwork.com/news/money/economy/1001776/peso-rebounds-to-p62-513-1-psei-rises-to-6-116-53/story/'


def result(url, source, description='', snippets=()):
    return {'source': source, 'title': 'Title <strong>here</strong>', 'url': url,
            'description': description, 'extra_snippets': list(snippets)}


class SourcePolicyTests(unittest.TestCase):
    def test_fact_checkers_first_then_nine_news_sources(self):
        names = [source['name'] for source in get_all_sources()]
        self.assertEqual(names[:2], ['VERA Files', 'Rappler'])
        self.assertEqual(len(names), 11)
        self.assertTrue(all(get_source_by_name(n)['priority'] for n in names[:2]))
        for name in ['DZRH News', 'OneNews.PH', 'ABS-CBN News', 'GMA News', 'Philippine Star']:
            self.assertIn(name, names)

    def test_only_blocking_publishers_use_search_excerpts(self):
        blocked = {'Philippine Daily Inquirer', 'Manila Bulletin',
                   'Philippine News Agency', 'Philippine Information Agency'}
        for source in get_all_sources():
            self.assertEqual(uses_search_excerpts(source['name']), source['name'] in blocked)
        self.assertFalse(uses_search_excerpts('Unknown source'))

    def test_new_publisher_article_urls_are_accepted(self):
        for url in ['https://www.rappler.com/business/philippine-peso-us-dollar-exchange-record-low-explainer/',
                    'https://www.rappler.com/business/economy/147394-philippine-peso-us-dollar-seven-year-low/',
                    'https://www.dzrh.com.ph/post/padilla-questions-senate-stance-on-grave-threats-case-against-vp-duterte',
                    'https://www.onenews.ph/articles/peso-hits-fresh-record-low-61-847-to-us-dollar']:
            with self.subTest(url=url):
                self.assertIsNone(article_url_rejection(url))

    def test_new_publisher_listing_pages_are_rejected(self):
        for url in ['https://www.rappler.com/business/economy/', 'https://www.rappler.com/topic/peso-dollar',
                    'https://www.dzrh.com.ph/nation', 'https://www.dzrh.com.ph/category/nation/page',
                    'https://www.onenews.ph/articles', 'https://www.onenews.ph/videos/some-video',
                    'https://www.dzrhnews.com.ph/post/lookalike-domain']:
            with self.subTest(url=url):
                self.assertIsNotNone(article_url_rejection(url))


class BraveSearchTests(unittest.TestCase):
    def test_requests_and_keeps_extra_snippets(self):
        captured = {}

        def fake_get(url, headers=None, params=None, timeout=None):
            captured.update(params)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'web': {'results': [
                {'url': INQUIRER, 'title': 'Moira', 'description': 'Desc',
                 'extra_snippets': ['One passage.', None, 'Two passage.']}]}})

        with patch.object(search, '_get_api_key', return_value='fixture'), \
             patch.object(search.requests, 'get', side_effect=fake_get):
            report = search.brave_search('Moira', get_source_by_name('Philippine Daily Inquirer'))
        self.assertEqual(captured['extra_snippets'], 'true')
        self.assertEqual(report['results'][0]['extra_snippets'], ['One passage.', 'Two passage.'])


class ExcerptEvidenceTests(unittest.TestCase):
    def test_blocked_publisher_is_never_downloaded(self):
        item = result(INQUIRER, 'Philippine Daily Inquirer',
                      'Dela Torre said during the press conference for her upcoming concert, '
                      '&ldquo;<strong>Where It All Started</strong>,&rdquo; in Quezon City on Thursday, Sept. 17.',
                      ['Dela Torre is set to headline her comeback concert at the Mall of Asia Arena on Oct. 4.'])
        with patch.object(search, 'extract_article_text', side_effect=AssertionError('downloaded')):
            article = search._build_article_from_result(item)
        self.assertEqual(article['status'], 'extracted')
        self.assertEqual(article['evidence_type'], 'search_excerpt')
        self.assertEqual(article['excerpt_reason'], 'publisher_blocks_automated_download')
        self.assertEqual(article['title'], 'Title here')
        self.assertIn('“Where It All Started,” in Quezon City on Thursday, Sept. 17.', article['text'])
        self.assertNotIn('<strong>', article['text'])
        self.assertIn('Oct. 4', article['text'])
        self.assertEqual(article['word_count'], len(article['text'].split()))

    def test_repeated_passages_are_kept_once(self):
        short = 'Moira said she and her former husband have moved forward.'
        longer = short + ' "Yes, we are civil," she said at the press conference.'
        article = search.build_excerpt_article(
            result(INQUIRER, 'Philippine Daily Inquirer', short, [longer, longer]), 'test')
        self.assertEqual(article['text'], longer)

    def test_empty_or_tiny_excerpt_is_not_evidence(self):
        article = search.build_excerpt_article(
            result(INQUIRER, 'Philippine Daily Inquirer', 'Too short.'), 'test')
        self.assertEqual(article['status'], 'skipped')
        self.assertEqual(article['text'], '')
        self.assertEqual(article['word_count'], 0)
        self.assertIsNone(iris_app.compact_evidence_source(article))

    def test_excerpt_never_admits_unapproved_url(self):
        article = search.build_excerpt_article(
            result('https://unapproved.example/news/story-here', 'Philippine Daily Inquirer',
                   'A passage long enough to otherwise count as evidence text here.'), 'test')
        self.assertEqual(article['status'], 'skipped')

    def test_failed_download_falls_back_to_excerpt(self):
        item = result(VERA, 'VERA Files', 'VERA Files found the viral quote card is fabricated and never issued.')
        failure = {'url': VERA, 'status': 'error', 'error': 'Could not download article: 429 Client Error',
                   'title': None, 'text': '', 'word_count': 0}
        with patch.object(search, 'extract_article_text', return_value=failure):
            article = search._build_article_from_result(item)
        self.assertEqual(article['evidence_type'], 'search_excerpt')
        self.assertEqual(article['excerpt_reason'], 'download_failed')
        self.assertIn('429', article['download_error'])

    def test_failed_download_without_excerpt_stays_an_error(self):
        failure = {'url': VERA, 'status': 'error', 'error': 'Could not download article: 429',
                   'title': None, 'text': '', 'word_count': 0}
        with patch.object(search, 'extract_article_text', return_value=failure):
            article = search._build_article_from_result(result(VERA, 'VERA Files'))
        self.assertEqual(article['status'], 'error')
        self.assertEqual(article['evidence_type'], 'full_text')

    def test_readable_publisher_keeps_full_text(self):
        extracted = {'url': GMA, 'status': 'extracted', 'error': None, 'title': 'Peso rebounds',
                     'text': 'The local currency gained 11.2 centavos to close at P62.513:$1.',
                     'word_count': 11, 'extraction_method': 'paragraphs', 'extraction_quality': 'thin'}
        with patch.object(search, 'extract_article_text', return_value=extracted):
            article = search._build_article_from_result(result(GMA, 'GMA News', 'Snippet only.'))
        self.assertEqual(article['evidence_type'], 'full_text')
        self.assertEqual(article['text'], extracted['text'])

    def test_public_evidence_source_is_labeled(self):
        article = search.build_excerpt_article(
            result(INQUIRER, 'Philippine Daily Inquirer',
                   'Dela Torre spoke at the press conference in Quezon City on Thursday, Sept. 17.'), 'test')
        public = iris_app.compact_evidence_source(article, 'component_review')
        self.assertEqual(public['evidence_type'], 'search_excerpt')
        self.assertEqual(public['extraction_quality'], 'excerpt')


if __name__ == '__main__':
    unittest.main()
