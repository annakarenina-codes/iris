"""Fact-check lookup through a publisher's sitemap. No network access."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import fact_check_index as index
from pipeline.sources import get_vera_source

SITEMAP_INDEX = """<sitemapindex>
 <sitemap><loc>https://verafiles.org/post-sitemap12.xml</loc></sitemap>
 <sitemap><loc>https://verafiles.org/post-sitemap13.xml</loc></sitemap>
 <sitemap><loc>https://verafiles.org/post_tag-sitemap8.xml</loc></sitemap>
 <sitemap><loc>https://verafiles.org/category-sitemap.xml</loc></sitemap>
</sitemapindex>"""
PAGE_12 = """<urlset>
 <url><loc>https://verafiles.org/articles/marcos-lays-down-plans-in-first-sona</loc></url>
</urlset>"""
PAGE_13 = """<urlset>
 <url><loc>https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses</loc></url>
 <url><loc>https://verafiles.org/articles/flooded-saturday-in-quezon-city</loc></url>
 <url><loc>https://verafiles.org/category/fact-check</loc></url>
</urlset>"""
PAGES = {'https://verafiles.org/sitemap.xml': SITEMAP_INDEX,
         'https://verafiles.org/post-sitemap12.xml': PAGE_12,
         'https://verafiles.org/post-sitemap13.xml': PAGE_13}
CLAIM = ('At least two Facebook posts are claiming that retired Philippine Air Force Maj. Gen. Romeo '
         'Poquiz made a statement against President Ferdinand Marcos Jr. and his wife.')


class FactCheckIndexTests(unittest.TestCase):
    def setUp(self):
        index._cache.clear()
        self.fetched = []

    def fake_get(self, url):
        self.fetched.append(url)
        return PAGES.get(url)

    def test_matching_fact_check_is_found_through_the_sitemap(self):
        with patch.object(index, '_get', side_effect=self.fake_get):
            found = index.matching_articles(CLAIM, get_vera_source())
        self.assertEqual([article['url'] for article in found],
                         ['https://verafiles.org/articles/fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses'])
        self.assertEqual(found[0]['source'], 'VERA Files')
        self.assertIn('poquiz', found[0]['matched_terms'])
        self.assertTrue(found[0]['title'].startswith('Fact Check Romeo Poquiz'))

    def test_only_article_sitemaps_are_read_and_listing_urls_are_skipped(self):
        with patch.object(index, '_get', side_effect=self.fake_get):
            index.matching_articles(CLAIM, get_vera_source())
        self.assertNotIn('https://verafiles.org/post_tag-sitemap8.xml', self.fetched)
        self.assertNotIn('https://verafiles.org/category-sitemap.xml', self.fetched)
        with patch.object(index, '_get', side_effect=self.fake_get):
            flood = index.matching_articles('Flooded Saturday in Quezon City after heavy rain.', get_vera_source())
        self.assertEqual([a['url'] for a in flood],
                         ['https://verafiles.org/articles/flooded-saturday-in-quezon-city'])

    def test_unrelated_claim_matches_nothing(self):
        with patch.object(index, '_get', side_effect=self.fake_get):
            self.assertEqual(index.matching_articles('The peso closed at 62.513 per dollar.', get_vera_source()), [])

    def test_the_index_is_cached_and_failures_are_silent(self):
        with patch.object(index, '_get', side_effect=self.fake_get):
            index.matching_articles(CLAIM, get_vera_source())
            index.matching_articles(CLAIM, get_vera_source())
        self.assertEqual(self.fetched.count('https://verafiles.org/sitemap.xml'), 1)
        index._cache.clear()
        with patch.object(index, '_get', return_value=None):
            self.assertEqual(index.matching_articles(CLAIM, get_vera_source()), [])

    def test_search_pass_shape_matches_other_passes(self):
        from pipeline import search
        with patch.object(search, 'fact_check_candidates', return_value=[
                {'source': 'VERA Files', 'title': 'Fact Check', 'url': 'https://verafiles.org/articles/fact-check-x',
                 'description': '', 'extra_snippets': [], 'matched_terms': ['romeo', 'poquiz']}]):
            result = search.fact_check_search('claim text')
        self.assertEqual(result['search_pass'], 'fact_check_index')
        self.assertEqual(result['results'][0]['pass_rank'], 0)
        self.assertEqual(result['results'][0]['search_pass'], 'fact_check_index')

    def test_sources_without_a_sitemap_are_skipped(self):
        with patch.object(index, '_get', side_effect=AssertionError('fetched')):
            self.assertEqual(index.matching_articles(CLAIM, {'name': 'Rappler'}), [])


if __name__ == '__main__':
    unittest.main()
