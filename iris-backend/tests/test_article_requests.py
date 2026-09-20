"""How often IRIS asks a publisher for a page: once per URL, spaced out, and retried on 429."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import article_extractor as extractor

VERA = 'https://verafiles.org/articles/fact-check-poquiz-statement'
OTHER = 'https://verafiles.org/articles/fact-check-another-statement'
BODY = '<article>' + '<p>' + ('The fact check explains the claim in detail. ' * 12) + '</p></article>'


def page(status=200, url=VERA):
    def raise_for_status():
        if status >= 400:
            raise extractor.requests.HTTPError(f'{status} Client Error: Too Many Requests')

    return SimpleNamespace(url=url, text=BODY, status_code=status, raise_for_status=raise_for_status)


class RequestVolumeTests(unittest.TestCase):
    def setUp(self):
        extractor._article_cache.clear()
        extractor._host_last_request.clear()
        self.addCleanup(extractor._article_cache.clear)
        self.addCleanup(extractor._host_last_request.clear)
        self.sleeps = []
        patcher = patch.object(extractor.time, 'sleep', self.sleeps.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_second_claim_reuses_the_downloaded_article(self):
        # Every claim in a post asks for the same sources; VERA Files answers 429 if IRIS obeys.
        with patch.object(extractor.requests, 'get', return_value=page()) as get:
            first = extractor.extract_article_text(VERA)
            second = extractor.extract_article_text(VERA)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first['status'], 'extracted')
        self.assertEqual(second['text'], first['text'])

    def test_a_stale_reading_is_downloaded_again(self):
        with patch.object(extractor.requests, 'get', return_value=page()) as get:
            extractor.extract_article_text(VERA)
            entry = extractor._article_cache[VERA]
            entry['read'] -= extractor.ARTICLE_CACHE_SECONDS + 1
            extractor.extract_article_text(VERA)
        self.assertEqual(get.call_count, 2)

    def test_a_failed_download_is_not_remembered(self):
        with patch.object(extractor.requests, 'get', return_value=page(status=429)) as get:
            failed = extractor.extract_article_text(VERA)
            extractor.extract_article_text(VERA)
        self.assertEqual(failed['status'], 'error')
        self.assertEqual(get.call_count, 2 * (extractor.RATE_LIMITED_RETRIES + 1))

    def test_a_rate_limited_page_is_retried_and_then_read(self):
        answers = [page(status=429), page()]
        with patch.object(extractor.requests, 'get', side_effect=answers) as get:
            result = extractor.extract_article_text(VERA)
        self.assertEqual(result['status'], 'extracted')
        self.assertEqual(get.call_count, 2)
        self.assertEqual(self.sleeps[0], extractor.RATE_LIMITED_WAIT_SECONDS)

    def test_pages_from_one_publisher_are_spaced_apart(self):
        extractor._wait_for_host(VERA)
        extractor._wait_for_host(OTHER)
        self.assertTrue(self.sleeps and 0 < self.sleeps[0] <= extractor.HOST_REQUEST_INTERVAL_SECONDS,
                        f'expected a gap between two verafiles.org requests, slept {self.sleeps}')

    def test_a_publisher_left_alone_is_not_made_to_wait(self):
        extractor._wait_for_host(VERA)
        extractor._host_last_request['verafiles.org'] -= extractor.HOST_REQUEST_INTERVAL_SECONDS + 1
        extractor._wait_for_host(VERA)
        self.assertEqual(self.sleeps, [])


if __name__ == '__main__':
    unittest.main()
