"""Search passes, query anchors, and bounded review retries. No network or API calls."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import search
from pipeline.component_context import FIELDS
from pipeline.component_evidence import review_components, rate_limit_retry_delay
from pipeline.search_queries import anchored_query, original_language_query
from pipeline.sources import get_source_by_name


def context(subject='', action='', origin='claim'):
    values = dict(subject=subject, action=action)
    return {k: [{'origin': origin, 'quote': values[k]}] if values.get(k) else [] for k in FIELDS}


def reply_client(replies, calls):
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
            refusal=None, content=json.dumps(replies.pop(0))))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class QueryAnchorTests(unittest.TestCase):
    def test_adds_dropped_date_number_and_title(self):
        claim = ("Moira Dela Torre faced the media earlier today, Sept. 17, in Quezon City, to talk "
                 "about her upcoming concert 'Where It All Started,' set for Oct. 4.")
        self.assertEqual(anchored_query('Moira Dela Torre media event concert October 4', claim),
                         'Moira Dela Torre media event concert October 4 Sept 17 Where It All Started')
        self.assertEqual(anchored_query('peso dollar exchange rate September 9',
                                        'The peso closed at ₱62.513 = $1 this Wednesday, September 9.'),
                         'peso dollar exchange rate September 9 62.513')

    def test_leaves_query_alone_when_nothing_distinctive_is_missing(self):
        self.assertEqual(anchored_query('man arrested shooting ex partner online insults',
                                        'Man shoots the new partner of ex after online insults, arrested'),
                         'man arrested shooting ex partner online insults')
        self.assertEqual(anchored_query('singer spoke Sept. 17', 'The singer spoke on September 17.'),
                         'singer spoke Sept. 17')

    def test_long_quotations_are_not_added(self):
        claim = 'He said "this is a long quoted sentence that is not a title at all".'
        self.assertEqual(anchored_query('speaker statement', claim), 'speaker statement')


class OriginalLanguageQueryTests(unittest.TestCase):
    def test_aligned_translation_returns_matching_filipino_sentence(self):
        original = ('BABALA: Sensitibong balita. Maging disente sa pagkomento. Lalaking bumaril sa '
                    'bagong kinakasama ng ex matapos mapikon sa patutsada online, arestado')
        translated = ('WARNING: Sensitive news.\nBe decent in commenting.\nMan who shot the new partner '
                      'of ex after getting annoyed by online insults arrested')
        self.assertEqual(
            original_language_query('Man shoots the new partner of ex after getting upset over online insults, arrested',
                                    original, translated),
            'Lalaking bumaril sa bagong kinakasama ng ex matapos mapikon sa patutsada online, arestado')

    def test_unaligned_text_matches_on_names_and_numbers(self):
        original = 'Grabe ang init ngayon. Nagsara ang piso sa 62.513 kontra dolyar ayon sa BSP.'
        translated = 'It is so hot today, really. The peso closed at 62.513 against the dollar. According to BSP.'
        self.assertEqual(original_language_query('The peso closed at 62.513 per dollar.', original, translated),
                         'Nagsara ang piso sa 62.513 kontra dolyar ayon sa BSP.')

    def test_english_or_unmatched_long_text_gives_no_query(self):
        self.assertIsNone(original_language_query('Claim.', 'Same text.', 'Same text.'))
        long_text = ' '.join(['salita'] * 40) + '.'
        self.assertIsNone(original_language_query('Unrelated claim here.', long_text, 'Different words ' * 20))


class SearchPassTests(unittest.TestCase):
    def fake_search(self, calls):
        def search_one(query, source, count=search.RESULTS_PER_SOURCE, freshness=None):
            calls.append((query, source['name'], freshness))
            if source['name'] != 'GMA News':
                return {'source': source['name'], 'query': query, 'status': 'ok', 'error': None, 'results': []}
            label = 'recent' if freshness else ('fil' if 'Lalaki' in query else 'en')
            return {'source': source['name'], 'query': query, 'status': 'ok', 'error': None, 'results': [
                {'source': 'GMA News', 'title': t, 'url': f'https://www.gmanetwork.com/news/{t}/story/',
                 'description': '', 'extra_snippets': []}
                for t in (f'{label}-1', f'{label}-2', 'shared')]}
        return search_one

    def vera_hits(self, count):
        def search_one(query, source, count_=search.RESULTS_PER_SOURCE, freshness=None):
            results = [] if source['name'] != 'VERA Files' else [
                {'source': 'VERA Files', 'title': f'search-{i}', 'description': '', 'extra_snippets': [],
                 'url': f'https://verafiles.org/articles/search-hit-{i}'} for i in range(count)]
            return {'source': source['name'], 'query': query, 'status': 'ok', 'error': None, 'results': results}
        return search_one

    def test_a_sitemap_fact_check_is_read_even_when_search_fills_the_source(self):
        # The VERA Files fact-check that settles a claim was lost behind three search hits.
        found = {'source': 'VERA Files', 'title': 'FACT CHECK: statement is fabricated', 'description': '',
                 'extra_snippets': [], 'matched_terms': ['poquiz', 'romeo'],
                 'url': 'https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement'}
        with patch.object(search, 'brave_search', side_effect=self.vera_hits(3)),              patch.object(search, 'fact_check_candidates', return_value=[found]):
            result = search.search_with_backup('Poquiz said the Marcoses have lost their mandate')
        self.assertEqual(result['search_passes'][0], 'fact_check_index')
        vera = [r['url'] for r in result['results'] if r['source'] == 'VERA Files']
        self.assertEqual(vera[0], found['url'])
        self.assertIn(found['url'], vera[:search.MAX_ARTICLES_PER_SOURCE])

    def test_sitemap_matches_leave_room_for_search_hits(self):
        candidates = [{'source': 'VERA Files', 'title': f'index-{i}', 'description': '', 'extra_snippets': [],
                       'matched_terms': ['a', 'b'], 'url': f'https://verafiles.org/articles/index-{i}'}
                      for i in range(2)]
        with patch.object(search, 'brave_search', side_effect=self.vera_hits(3)),              patch.object(search, 'fact_check_candidates', return_value=candidates) as lookup:
            result = search.search_with_backup('a claim')
        self.assertEqual(lookup.call_args[0][1], search.MAX_INDEX_ARTICLES)
        vera = [r['url'] for r in result['results'] if r['source'] == 'VERA Files']
        self.assertEqual(len(vera[:search.MAX_ARTICLES_PER_SOURCE]), 3)
        self.assertTrue(any('search-hit' in url for url in vera[:search.MAX_ARTICLES_PER_SOURCE]))

    def test_primary_recent_and_original_language_passes_all_run(self):
        calls = []
        with patch.object(search, 'brave_search', side_effect=self.fake_search(calls)), \
             patch.object(search, 'fact_check_candidates', return_value=[]):
            result = search.search_with_backup('man shot ex partner arrested',
                                               original_language_query='Lalaking bumaril arestado')
        self.assertEqual(result['search_passes'], ['primary', 'recent', 'original_language'])
        self.assertEqual({c[2] for c in calls if c[0] == 'man shot ex partner arrested'}, {None, search.RECENCY_WINDOW})
        self.assertIn(('Lalaking bumaril arestado', 'GMA News', None), calls)
        titles = [r['title'] for r in result['results']]
        # Each pass's best hit comes before any pass's second hit, and duplicates are kept once.
        self.assertEqual(titles[:3], ['en-1', 'recent-1', 'fil-1'])
        self.assertEqual(titles.count('shared'), 1)
        self.assertFalse(result['backup_query_used'])

    def test_top_hit_from_every_pass_is_read(self):
        calls = []
        with patch.object(search, 'brave_search', side_effect=self.fake_search(calls)), \
             patch.object(search, 'fact_check_candidates', return_value=[]), \
             patch.object(search, 'extract_article_text', side_effect=lambda url: {
                 'url': url, 'status': 'extracted', 'error': None, 'title': url, 'text': 'Enough text here.',
                 'word_count': 3}):
            result = search.search_and_extract('query', original_language_query='Lalaking query')
        read = [a['url'] for a in result['articles']]
        for label in ('en-1', 'recent-1', 'fil-1'):
            self.assertIn(f'https://www.gmanetwork.com/news/{label}/story/', read)

    def test_recency_filter_is_sent_and_search_429_is_retried_once(self):
        responses = [SimpleNamespace(status_code=429, raise_for_status=lambda: None, json=lambda: {}),
                     SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                     json=lambda: {'web': {'results': []}})]
        params = []

        def fake_get(url, headers=None, params=None, timeout=None, _p=params):
            _p.append(dict(params))
            return responses.pop(0)

        with patch.object(search, '_get_api_key', return_value='fixture'), \
             patch.object(search.requests, 'get', side_effect=fake_get), \
             patch.object(search.time, 'sleep') as sleep:
            report = search.brave_search('q', get_source_by_name('GMA News'), freshness='pm')
        self.assertEqual(report['status'], 'ok')
        self.assertEqual([p.get('freshness') for p in params], ['pm', 'pm'])
        sleep.assert_called_once()


class ReviewRetryTests(unittest.TestCase):
    CLAIM = 'Cases rose in the city.'

    def replies(self):
        return [
            {'assessments': {'0': {'status': 'supported', 'passage_ids': [0]}}},
            {'groups': [{'component_ids': [0], 'referent': self.CLAIM, 'sources': {
                '0': {'status': 'matched', 'passage_ids': [0], 'reason': 'Same assertion.'}}}]},
            {'checks': {'0': {'same_subject_and_event': True, 'assertion_supported': True,
                              'qualifiers_preserved': True, 'citation_ids': [0], 'reason': 'Explicit support.'}}},
        ]

    def test_unusable_answer_gets_one_corrective_retry(self):
        calls = []
        # A structurally unusable answer: contexts must be a list, one entry per component.
        replies = [{'split_after': [], 'contexts': 'not a list'},
                   {'split_after': [], 'contexts': [context('Cases', 'rose')]}, *self.replies()]
        article = {'url': 'https://example.org/news', 'text': self.CLAIM}
        with patch('openai.OpenAI', return_value=reply_client(replies, calls)):
            result = review_components(self.CLAIM, [article], self.CLAIM)
        self.assertEqual(result['verdict'], 'Verified')
        self.assertEqual(len(calls), 5)
        self.assertNotIn('CORRECTION', calls[0]['messages'][0]['content'])
        self.assertIn('incomplete_component_contexts', calls[1]['messages'][0]['content'])

    def test_second_invalid_answer_is_a_processing_error(self):
        calls = []
        bad = {'split_after': [], 'contexts': 'not a list'}
        with patch('openai.OpenAI', return_value=reply_client([bad, bad], calls)):
            result = review_components(self.CLAIM, [], self.CLAIM)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_code'], 'invalid_review_response')
        self.assertIsNone(result['verdict'])

    def test_entailment_only_receives_cited_articles(self):
        calls = []
        cited = {'url': 'https://example.org/news', 'text': self.CLAIM}
        uncited = {'url': 'https://example.org/other', 'text': 'A long unrelated weather report for Cebu.'}
        replies = [{'split_after': [], 'contexts': [context('Cases', 'rose')]}, *self.replies()]
        with patch('openai.OpenAI', return_value=reply_client(replies, calls)):
            result = review_components(self.CLAIM, [cited, uncited], self.CLAIM)
        self.assertEqual(result['verdict'], 'Verified')
        entailment = json.loads(calls[-1]['messages'][1]['content'])
        self.assertEqual([a['url'] for a in entailment['articles_for_reference_resolution']], [cited['url']])

    def test_rate_limit_backoff_grows_without_headers(self):
        error = SimpleNamespace(body={}, response=SimpleNamespace(headers={}))
        self.assertEqual([rate_limit_retry_delay(error, attempt) for attempt in range(3)], [5, 10, 20])


if __name__ == '__main__':
    unittest.main()
