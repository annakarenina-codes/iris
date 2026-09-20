"""Reading an article through the publisher's own API when its pages answer with a challenge."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import article_extractor as extractor
from pipeline import publisher_api
from pipeline.publisher_api import article_from_api, content_api

C08 = 'https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses'
BODY = ('<p>At least two Facebook posts falsely attributed a viral statement to retired Air Force '
        'Maj. Gen. Romeo Poquiz denouncing the leadership of President Ferdinand Marcos Jr.</p>'
        '<script>tracker()</script><p>Poquiz told VERA Files he did not write the statement.</p>')


def post(link=C08, body=BODY, title='FACT CHECK: Romeo Poquiz did NOT make viral statement vs Marcoses'):
    return {'link': link, 'title': {'rendered': title}, 'date': '2026-09-18T10:00:00',
            'content': {'rendered': body}}


def answer(payload):
    return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)


class PublisherApiTests(unittest.TestCase):
    def setUp(self):
        extractor._article_cache.clear()
        self.addCleanup(extractor._article_cache.clear)

    def test_only_a_source_that_declares_an_api_is_read_this_way(self):
        self.assertEqual(content_api('VERA Files'), 'https://verafiles.org/wp-json/wp/v2/posts')
        self.assertIsNone(content_api('GMA News'))
        with patch.object(publisher_api.requests, 'get') as get:
            self.assertIsNone(article_from_api('https://www.gmanetwork.com/news/topstories/nation/1/x/story/',
                                               'GMA News'))
        get.assert_not_called()

    def test_the_article_text_is_read_from_the_api(self):
        with patch.object(publisher_api.requests, 'get', return_value=answer([post()])) as get:
            article = article_from_api(C08, 'VERA Files')
        self.assertEqual(get.call_count, 1)
        self.assertEqual(article['status'], 'extracted')
        self.assertEqual(article['extraction_method'], 'publisher_api')
        self.assertIn('Romeo Poquiz', article['text'])
        self.assertNotIn('tracker()', article['text'])
        self.assertNotIn('<p>', article['text'])
        self.assertEqual(article['published_at'], '2026-09-18T10:00:00')

    def test_an_article_stored_under_another_slug_is_found_by_its_words(self):
        replies = [answer([]), answer([post(link='https://verafiles.org/articles/unrelated'), post()])]
        with patch.object(publisher_api.requests, 'get', side_effect=replies) as get:
            article = article_from_api(C08, 'VERA Files')
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].kwargs['params']['search'],
                         'fact check romeo poquiz did not make viral statement vs marcoses')
        self.assertIn('Romeo Poquiz', article['text'])

    def test_text_is_never_taken_from_a_different_article(self):
        other = post(link='https://verafiles.org/articles/some-other-fact-check')
        with patch.object(publisher_api.requests, 'get', return_value=answer([other])):
            self.assertIsNone(article_from_api(C08, 'VERA Files'))

    def test_a_failing_api_returns_nothing_instead_of_raising(self):
        with patch.object(publisher_api.requests, 'get', side_effect=publisher_api.requests.RequestException('503')):
            self.assertIsNone(article_from_api(C08, 'VERA Files'))

    def test_a_search_listing_is_never_requested(self):
        with patch.object(publisher_api.requests, 'get') as get:
            self.assertIsNone(article_from_api('https://verafiles.org/?s=poquiz', 'VERA Files'))
        get.assert_not_called()

    def test_the_article_is_asked_for_once_per_post(self):
        with patch.object(publisher_api.requests, 'get', return_value=answer([post()])) as get:
            first = article_from_api(C08, 'VERA Files')
            second = article_from_api(C08, 'VERA Files')
        self.assertEqual(get.call_count, 1)
        self.assertEqual(second['text'], first['text'])


if __name__ == '__main__':
    unittest.main()
