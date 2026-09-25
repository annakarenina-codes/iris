import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.sources import get_all_sources
from pipeline.evidence_urls import article_url_rejection, clean_article_url
from pipeline import article_extractor as extractor
from pipeline import search
from pipeline.component_evidence import event_identity_input, event_identity_schema, apply_event_identity_checks
from pipeline.component_evidence import rate_limit_retry_delay, rate_limit_details, review_components, RATE_LIMIT_ATTEMPTS
from pipeline.political_checker import flag_claim_political, flag_political
from pipeline.ocr_layout import select_content_regions


ABS = 'https://www.abs-cbn.com/entertainment/showbiz/2026/9/18/example-story'
GMA = 'https://www.gmanetwork.com/entertainment/showbiznews/news/123/example/story/'
VERA = 'https://verafiles.org/articles/fact-check-example'


class SourcePolicyTests(unittest.TestCase):
    def test_all_abs_and_gma_sections_are_searched(self):
        sources = {s['name']: s for s in get_all_sources()}
        self.assertEqual(sources['ABS-CBN News']['site_query'], 'site:abs-cbn.com')
        self.assertEqual(sources['GMA News']['site_query'], 'site:gmanetwork.com')
        for url in [ABS, GMA, VERA, ABS.replace('entertainment/showbiz', 'lifestyle/style'),
                    ABS.replace('entertainment/showbiz', 'sports/basketball')]:
            self.assertIsNone(article_url_rejection(url))

    def test_search_listing_and_unapproved_pages_cannot_be_evidence(self):
        for url in ['https://verafiles.org/?s=Poquiz', 'https://verafiles.org/articles',
                    'https://verafiles.org/articles/page/2', 'https://verafiles.org/search/poquiz',
                    'https://www.abs-cbn.com/news', 'https://www.abs-cbn.com/news/nation',
                    'https://www.gmanetwork.com/news/tags/tag/123',
                    'https://www.abs-cbn.com.evil.test/news/2026/9/story',
                    'https://unapproved.example/news/a', 'javascript:alert(1)']:
            with self.subTest(url=url):
                self.assertIsNotNone(article_url_rejection(url))

    def test_tracking_removed_without_inventing_article_slug(self):
        self.assertEqual(clean_article_url(ABS + '?fbclid=test&utm_source=fb#section'), ABS)
        self.assertEqual(article_url_rejection(VERA, 'GMA News'), 'unapproved_publisher')

    def test_search_filters_bad_results_before_extraction_budget(self):
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'web': {'results': [
            {'url': 'https://verafiles.org/?s=Poquiz'}, {'url': VERA, 'title': 'Actual article'}]}})
        with patch.object(search, '_get_api_key', return_value='fixture'), \
             patch.object(search.requests, 'get', return_value=response):
            result = search.brave_search('Poquiz', get_all_sources()[0])
        self.assertEqual([r['url'] for r in result['results']], [VERA])
        self.assertEqual(result['rejected_results'][0]['reason'], 'search_results_page')


class ExtractionIsolationTests(unittest.TestCase):
    def test_primary_body_does_not_include_related_articles(self):
        primary = {'headline': 'Main story', 'body_html': '<p>Anna made this exact statement about Eala.</p>',
                   'associations': {'relatedContent': [
                       {'headline': 'Different story', 'body_html': '<p>Unrelated singer released a song.</p>'}]}}
        payload = {'props': {'pageProps': {'dataStr': json.dumps({'article': primary}),
                                          'related': {'headline': 'Other', 'body_html': 'Other news body.'}}}}
        html = '<meta property="og:title" content="Main story"><script type="application/json">' + json.dumps(payload) + '</script>'
        text = extractor._json_article_text(extractor.BeautifulSoup(html, 'html.parser'))
        self.assertEqual(text, 'Anna made this exact statement about Eala.')

    def test_article_body_html_is_rendered_as_text(self):
        html = '<script type="application/ld+json">' + json.dumps({
            'articleBody': '<p>DepEd plans 640 hours of training.</p><p>Not yet implemented.</p>'}) + '</script>'
        self.assertEqual(extractor._json_article_text(extractor.BeautifulSoup(html, 'html.parser')),
                         'DepEd plans 640 hours of training. Not yet implemented.')

    def test_multiple_unidentified_bodies_are_not_combined(self):
        html = '<script type="application/json">' + json.dumps([
            {'body_html': 'First story with enough words to verify here.'},
            {'body_html': 'Second unrelated story with a different meaning here.'}]) + '</script>'
        self.assertEqual(extractor._json_article_text(extractor.BeautifulSoup(html, 'html.parser')), '')

    def test_search_url_never_downloaded(self):
        with patch.object(extractor.requests, 'get') as get:
            result = extractor.extract_article_text('https://verafiles.org/?s=poquiz')
        get.assert_not_called()
        self.assertEqual(result['status'], 'skipped')

    def test_redirect_to_search_is_not_valid_evidence(self):
        response = SimpleNamespace(url='https://verafiles.org/?s=poquiz',
                                   text='<p>Some results from unrelated stories.</p>', raise_for_status=lambda: None)
        with patch.object(extractor.requests, 'get', return_value=response):
            result = extractor.extract_article_text(VERA)
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['error'], 'redirect_search_results_page')


class EventPassageOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.articles = [{'url': GMA, 'text': 'The first article reports its own event.'},
                         {'url': ABS, 'text': 'The second article reports another event.'}]
        self.reviewed = {'components': [{'component': 'Claim', 'status': 'supported', 'citations': [
            {'url': a['url'], 'quote': a['text']} for a in self.articles]}]}
        self.payload = event_identity_input('Claim', self.reviewed, self.articles)

    def test_source_ids_follow_article_order_and_each_passage_identifies_owner(self):
        self.assertEqual(self.payload['sources'][0]['url'], GMA)
        self.assertEqual([p['source_id'] for p in self.payload['passages']], [0, 1])

    def test_schema_limits_each_source_to_its_own_passages(self):
        schema = event_identity_schema(1, 2, 2, {0: [0], 1: [1]})
        sources = schema['properties']['groups']['items']['properties']['sources']['properties']
        self.assertEqual(sources['0']['properties']['passage_ids']['items']['enum'], [0])
        self.assertEqual(sources['1']['properties']['passage_ids']['items']['enum'], [1])

    def test_validator_still_rejects_cross_source_passages(self):
        groups = [{'component_ids': [0], 'referent': 'Claim', 'sources': {
            '0': {'status': 'matched', 'passage_ids': [1], 'reason': 'Wrong owner'},
            '1': {'status': 'matched', 'passage_ids': [1], 'reason': 'Right owner'}}}]
        with self.assertRaisesRegex(ValueError, 'invalid_event_identity_passages'):
            apply_event_identity_checks('Claim', self.reviewed, groups, self.payload, self.articles)


class ReviewRateLimitTests(unittest.TestCase):
    def error(self, headers=None, code='rate_limit_exceeded', message='Slow down'):
        error = type('RateLimitError', (Exception,), {})('provider error')
        error.body = {'code': code, 'message': message, 'type': 'tokens'}
        error.response = SimpleNamespace(headers=headers or {})
        return error

    def test_numeric_provider_wait_is_bounded(self):
        for headers, expected in [({'retry-after': '12'}, 12),
                                  ({'retry-after-ms': '1500'}, 1.5),
                                  ({'x-ratelimit-reset-tokens': '2s500ms'}, 2.5),
                                  ({'retry-after': '61'}, None),
                                  ({'retry-after': '-2'}, None), ({}, 5)]:
            with self.subTest(headers=headers):
                self.assertEqual(rate_limit_retry_delay(self.error(headers)), expected)

    def test_quota_or_oversized_request_is_not_retried(self):
        self.assertIsNone(rate_limit_retry_delay(self.error(code='insufficient_quota')))
        self.assertIsNone(rate_limit_retry_delay(self.error(message='Request too large for this model')))

    def test_diagnostics_do_not_copy_raw_provider_message_or_arbitrary_headers(self):
        details = rate_limit_details(self.error({'authorization': 'secret', 'retry-after': '2'},
                                               message='private account details'))
        self.assertNotIn('secret', json.dumps(details))
        self.assertNotIn('private account details', json.dumps(details))

    def test_transient_limit_retries_once_then_keeps_normal_validation(self):
        claim = 'The agency opened a new clinic.'
        replies = [self.error({'retry-after': '2'}), {'split_after': [], 'contexts': [
            {k: [] for k in ('subject', 'action', 'event', 'time', 'negation', 'speaker')}]},
                   {'assessments': {'0': {'status': 'not_supported', 'passage_ids': []}}}]
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',
                message=SimpleNamespace(refusal=None, content=json.dumps(reply)))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kw: client)}), \
             patch('pipeline.component_evidence.time.sleep') as sleep:
            result = review_components(claim, [{'url': ABS, 'text': 'Unrelated music news with no clinic.'}])
        sleep.assert_called_once_with(2)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(result['verdict'], 'Not Found')
        self.assertEqual(result['supporting_urls'], [])

    def test_second_limit_or_quota_error_never_invents_a_verdict(self):
        for code, expected_calls in [('rate_limit_exceeded', RATE_LIMIT_ATTEMPTS), ('insufficient_quota', 1)]:
            with self.subTest(code=code):
                from unittest.mock import Mock
                create = Mock(side_effect=self.error(code=code))
                client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
                with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=lambda **kw: client)}), \
                     patch('pipeline.component_evidence.time.sleep') as sleep:
                    result = review_components('Example claim.', [])
                self.assertEqual(create.call_count, expected_calls)
                self.assertEqual(sleep.call_count, expected_calls - 1)
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error_code'], 'review_rate_limited')
                self.assertIsNone(result['verdict'])
                self.assertEqual(result['supporting_urls'], [])


class PoliticalContextTests(unittest.TestCase):
    def test_titles_punctuation_and_accents(self):
        for text in ['Sen. Robinhood "Robin" Padilla spoke.', 'Sens. A and B endorsed a candidate.',
                     'Malaca\u00f1ang gave a statement.', 'Rep. Marcoleta spoke.']:
            self.assertTrue(flag_political(text)['politically_sensitive'])

    def test_quote_inherits_only_its_speakers_explicit_office(self):
        context = 'Sen. Robinhood "Robin" Padilla announced his plans. Moira spoke about music.'
        claim = {'claim_type': 'attributed_statement', 'claim_text': 'Padilla said he does not belong here.',
                 'attribution': {'speaker': 'Padilla'}, 'evidence_context': context}
        result = flag_claim_political(claim)
        self.assertTrue(result['politically_sensitive'])
        self.assertEqual(result['speaker_context'][0]['role'], 'Sen.')
        claim['attribution']['speaker'] = 'Robin Padilla'
        self.assertTrue(flag_claim_political(claim)['politically_sensitive'])
        claim.update(claim_text='Moira spoke about music.', attribution={'speaker': 'Moira'})
        self.assertFalse(flag_claim_political(claim)['politically_sensitive'])

    def test_unrelated_person_with_shared_surname_does_not_inherit_office(self):
        self.assertFalse(flag_claim_political({'claim_type': 'attributed_statement',
            'claim_text': 'Daniel Padilla discussed acting.', 'attribution': {'speaker': 'Daniel Padilla'},
            'evidence_context': 'Sen. Robin Padilla announced his plans.'})['politically_sensitive'])


class OcrInterfaceTests(unittest.TestCase):
    def test_cleanup_removes_interface_but_not_claim_words(self):
        regions = [{'text': s, 'confidence': .99} for s in [
            'Like Comment Share', '1.2K Likes', '45 Comments', '640 hours of training',
            'Not confirmed', 'The post received 45 comments.']]
        selected, rejected = select_content_regions(regions)
        self.assertEqual([r['text'] for r in selected], [r['text'] for r in regions[3:]])
        self.assertTrue(all(r['reason'] == 'social_interface' for r in rejected))

    def test_uncertain_negation_is_not_deleted_as_noise(self):
        regions = [{'text': 'NOT', 'confidence': .2}, {'text': 'a confirmed report', 'confidence': .9}]
        self.assertEqual(select_content_regions(regions)[0], regions)


if __name__ == '__main__':
    unittest.main()
