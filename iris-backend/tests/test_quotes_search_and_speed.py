"""
The fixes of 22 September: quotations kept as said, speakers named in queries, quotations routed
to checking, evidence ranked by its best passage, and search passes run at the same time.

No network access and no models: embeddings, search and sitemaps are replaced where used.
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import component_evidence, fact_check_index as index, search
from pipeline.attribution_integrity import ground_attribution, speaker_query
from pipeline.content_profiler import _local_profile, _merge_openai_segment_advice, profile_content
from pipeline.quotation_context import restore_original_quotations, translated_quotations
from pipeline.text_boundaries import has_reported_quote

QUOTE = ("“Para kasi sa administrasyong Marcos, mas madali ang maging inutil, magnakaw, at "
         "magsamantala kaysa magsilbi nang tapat sa bayan,” Duterte stated.")
ENGLISH = ("“Because for the Marcos administration, it is easier to be useless, to steal, and to "
           "exploit rather than to serve the country honestly,” Duterte stated.")
LEAD = ("Vice President Sara Duterte criticized the Marcos administration over the South Cotabato "
        "school shooting.")
POST = f"{LEAD}\n{QUOTE}"
TRANSLATION = f"{LEAD}\n{ENGLISH}"

ATASHA = ("‘Bongga Ka 'Day’ musical star Atasha Muhlach opens up about the best advice she received "
          "from her parents, Aga Muhlach and Charlene Gonzales, on how to handle showbiz intrigues.\n"
          "“Of course they gave me the best advice, which was, ‘You know what, just work hard, keep on "
          "your feet on the ground and focus lang,’” she shared.\n"
          "#CelebrityNews #AtashaMuhlach #AgaMuhlach See less")


class QuotationsKeepTheirWords(unittest.TestCase):
    def claim(self, text):
        return {'claim_id': 2, 'claim_text': text, 'normalized_claim': text, 'claim_type': 'attributed_statement',
                'attribution': {'speaker': 'Sara Duterte', 'statement': text}}

    def test_a_translated_quotation_is_put_back_and_its_english_kept(self):
        restored = restore_original_quotations(self.claim(ENGLISH), POST, TRANSLATION)
        self.assertEqual(restored['claim_text'], QUOTE)
        self.assertEqual(restored['normalized_claim'], QUOTE)
        self.assertEqual(restored['attribution']['statement'], QUOTE)
        self.assertEqual(restored['quote_translation'], ENGLISH)
        self.assertEqual(len(restored['restored_quotations']), 1)

    def test_a_post_that_was_not_translated_is_left_alone(self):
        claim = self.claim(QUOTE)
        self.assertIs(restore_original_quotations(claim, POST, POST), claim)
        self.assertEqual(translated_quotations(POST, POST), [])

    def test_a_claim_without_the_quotation_is_left_alone(self):
        claim = self.claim(LEAD)
        self.assertIs(restore_original_quotations(claim, POST, TRANSLATION), claim)

    def test_the_whole_quotation_goes_back_before_a_headline_that_repeats_it(self):
        # Saved case A08: the headline repeats the opening words of the full quotation.
        post = ("'NAGLALARO AKO NG CALL OF DUTY'\n"
                "\"Naglalaro ako ng Call of Duty, walang ebidensya sa laro,\" Samaniego said.")
        translation = ("'I AM PLAYING CALL OF DUTY'\n"
                       "\"I am playing Call of Duty, there is no evidence in the game,\" Samaniego said.")
        claim = self.claim("\"I am playing Call of Duty, there is no evidence in the game,\" Samaniego said.")
        restored = restore_original_quotations(claim, post, translation)
        self.assertEqual(restored['claim_text'],
                         "\"Naglalaro ako ng Call of Duty, walang ebidensya sa laro,\" Samaniego said.")

    def test_the_english_rendering_is_searched_as_its_own_pass(self):
        calls = []

        def search_one(query, source, count=search.RESULTS_PER_SOURCE, freshness=None):
            calls.append((query, freshness))
            return {'source': source['name'], 'query': query, 'status': 'ok', 'error': None, 'results': []}

        with patch.object(search, 'brave_search', side_effect=search_one), \
             patch.object(search, 'fact_check_candidates', return_value=[]):
            result = search.search_with_backup(QUOTE, translated_query=ENGLISH)
        self.assertEqual(result['search_passes'], ['primary', 'recent', 'translated'])
        self.assertIn((ENGLISH, None), calls)
        self.assertEqual(result['translated_query'], ENGLISH)


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


class EvidenceIsRankedByItsBestPassage(unittest.TestCase):
    CLAIM = QUOTE

    def articles(self):
        filler = ' '.join(f"Unrelated update number {i} about traffic in the city." for i in range(200))
        front = [{'url': f'https://www.philstar.com/nation/{i}', 'text': filler[:11000]} for i in range(6)]
        live = {'url': 'https://www.gmanetwork.com/news/live-updates/1003096/story/',
                'text': filler[:3000] + ' ' + QUOTE + ' Malacanang has yet to comment.'}
        return front + [live]

    def fake_scores(self, claim, passages, extra_queries=None):
        return [0.9 if 'inutil' in passage['text'] else 0.1 for passage in passages]

    def test_an_article_with_the_quotation_deep_inside_is_read(self):
        # Ranked by its opening, the live-updates page came last of 28 and was cut.
        articles = self.articles()
        with patch.object(component_evidence, '_passage_scores', side_effect=self.fake_scores):
            evidence = component_evidence.review_evidence(self.CLAIM, articles)
        self.assertEqual(evidence[0]['url'], articles[-1]['url'])
        self.assertLessEqual(sum(len(e['text']) for e in evidence), component_evidence.REVIEW_CHARACTER_BUDGET)

    def test_articles_that_all_fit_keep_their_order_and_need_no_model(self):
        articles = [{'url': f'https://www.philstar.com/nation/{i}', 'text': 'Short report.'} for i in range(3)]
        with patch.object(component_evidence, '_passage_scores', side_effect=AssertionError('ranked')):
            evidence = component_evidence.review_evidence(self.CLAIM, articles)
        self.assertEqual([e['url'] for e in evidence], [a['url'] for a in articles])

    def test_without_the_model_the_search_order_is_kept(self):
        articles = self.articles()
        with patch.object(component_evidence, '_passage_scores', return_value=None):
            evidence = component_evidence.review_evidence(self.CLAIM, articles)
        self.assertEqual(evidence[0]['url'], articles[0]['url'])

    def test_the_english_rendering_is_scored_too(self):
        seen = []
        with patch.object(component_evidence, '_passage_scores',
                          side_effect=lambda claim, passages, extra_queries=None: seen.append(extra_queries) or
                          [0.5] * len(passages)):
            component_evidence.review_evidence(self.CLAIM, self.articles(), claim_translation=ENGLISH)
        self.assertEqual(seen[0], [ENGLISH])


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class SearchRunsTogether(unittest.TestCase):
    def test_passes_run_at_the_same_time_and_merge_in_pass_order(self):
        def slow_search(query, source, count=search.RESULTS_PER_SOURCE, freshness=None):
            time.sleep(0.2)
            label = 'recent' if freshness else ('fil' if 'Lalaki' in query else 'en')
            results = [] if source['name'] != 'GMA News' else [
                {'source': 'GMA News', 'title': f'{label}-1', 'description': '', 'extra_snippets': [],
                 'url': f'https://www.gmanetwork.com/news/{label}-1/story/'}]
            return {'source': source['name'], 'query': query, 'status': 'ok', 'error': None, 'results': results}

        with patch.object(search, 'brave_search', side_effect=slow_search), \
             patch.object(search, 'fact_check_candidates', return_value=[]):
            started = time.monotonic()
            result = search.search_with_backup('man shot ex partner arrested',
                                               original_language_query='Lalaking bumaril arestado')
            elapsed = time.monotonic() - started
        # One after another the three passes take at least 0.6 seconds here.
        self.assertLess(elapsed, 0.55)
        self.assertEqual(result['search_passes'], ['primary', 'recent', 'original_language'])
        self.assertEqual([r['title'] for r in result['results']], ['en-1', 'recent-1', 'fil-1'])

    def test_brave_requests_are_paced_across_threads(self):
        clock = FakeClock()
        pace = search._RequestPace(4)
        started = []
        with patch.object(search.time, 'monotonic', side_effect=clock.monotonic), \
             patch.object(search.time, 'sleep', side_effect=clock.sleep):
            for _ in range(9):
                pace.wait_turn()
                started.append(clock.now)
        for i, moment in enumerate(started):
            within = [t for t in started if moment <= t < moment + 1.0]
            self.assertLessEqual(len(within), 4, f'request {i}')
        self.assertGreaterEqual(started[-1], 2.0)


class SitemapLoading(unittest.TestCase):
    SITEMAP = 'https://verafiles.org/sitemap.xml'
    INDEX = ("<sitemapindex><sitemap><loc>https://verafiles.org/post-sitemap12.xml</loc></sitemap>"
             "<sitemap><loc>https://verafiles.org/post-sitemap13.xml</loc></sitemap></sitemapindex>")
    PAGE = "<urlset><url><loc>https://verafiles.org/articles/fact-check-one</loc></url></urlset>"

    def setUp(self):
        index._cache.clear()
        index._loading.clear()

    def finish_background_read(self):
        future = index._loading.get(self.SITEMAP)
        if future is not None:
            future.result(timeout=5)

    def test_an_incomplete_index_is_used_and_read_again_behind_the_claim(self):
        pages = {self.SITEMAP: self.INDEX, 'https://verafiles.org/post-sitemap13.xml': self.PAGE}
        fetched = []
        fake_get = lambda url: fetched.append(url) or pages.get(url)
        with patch.object(index, '_get', side_effect=fake_get):
            self.assertEqual(index.recent_article_urls(self.SITEMAP), ['https://verafiles.org/articles/fact-check-one'])
            self.assertEqual(index._cache[self.SITEMAP]['lifetime'], index.PARTIAL_CACHE_SECONDS)
            index._cache[self.SITEMAP]['fetched'] -= index.PARTIAL_CACHE_SECONDS + 1
            # The stale index is answered at once; the new read happens in the background.
            self.assertEqual(index.recent_article_urls(self.SITEMAP), ['https://verafiles.org/articles/fact-check-one'])
            self.finish_background_read()
        self.assertEqual(fetched.count(self.SITEMAP), 2)

    def test_a_slow_first_read_holds_a_claim_only_briefly(self):
        release = threading.Event()

        def slow_get(url):
            release.wait(5)
            return {self.SITEMAP: self.INDEX}.get(url, self.PAGE)

        with patch.object(index, '_get', side_effect=slow_get):
            started = time.monotonic()
            self.assertEqual(index.recent_article_urls(self.SITEMAP, wait=0.2), [])
            self.assertLess(time.monotonic() - started, 1.0)
            release.set()
            self.finish_background_read()
            # The read carried on behind the claim, so the next one finds the fact-checks.
            self.assertEqual(index.recent_article_urls(self.SITEMAP),
                             ['https://verafiles.org/articles/fact-check-one'] * 2)

    def test_claims_arriving_together_read_the_sitemap_once(self):
        pages = {self.SITEMAP: self.INDEX, 'https://verafiles.org/post-sitemap12.xml': self.PAGE,
                 'https://verafiles.org/post-sitemap13.xml': self.PAGE}
        fetched, lock = [], threading.Lock()

        def slow_get(url):
            with lock:
                fetched.append(url)
            time.sleep(0.05)
            return pages.get(url)

        with patch.object(index, '_get', side_effect=slow_get):
            threads = [threading.Thread(target=index.recent_article_urls, args=(self.SITEMAP,)) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.finish_background_read()
        self.assertEqual(fetched.count(self.SITEMAP), 1)
        self.assertEqual(index._cache[self.SITEMAP]['lifetime'], index.CACHE_SECONDS)


class ClaimsWithNothingToReviewCostNoModelCall(unittest.TestCase):
    def test_the_split_is_not_asked_for_when_nothing_readable_was_found(self):
        import app as iris
        claim = {'claim_id': 1, 'claim_text': 'DOH reports dengue cases.', 'normalized_claim': 'DOH reports dengue cases.'}
        unapproved = {'total_search_results': 1, 'searched_articles': 1, 'extracted_articles': 1,
                      'source_summary': [], 'articles': [{'url': 'https://example.com/dengue', 'status': 'extracted',
                                                          'text': 'DOH reported new dengue cases.', 'word_count': 5}],
                      'search': {'searches': [{'source_reports': [{'source': 'GMA News', 'status': 'ok'}]}]}}
        with patch.object(iris, 'search_and_extract', return_value=unapproved), \
             patch('pipeline.component_evidence.prepare_component_review',
                   side_effect=AssertionError('model called')):
            gathered = iris.gather_claim_evidence(claim, 'english', iris.plan_claim(claim))
        self.assertIsNone(gathered['prepared'])
        self.assertEqual(gathered['search_status']['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
