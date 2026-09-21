"""A quote claim searches its own words; the pool query drops Facebook's furniture; and a quote
closed by "she shared" is recognised as somebody else's words."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import content_profiler as profiler
from pipeline.event_retrieval import build_event_search_query
from pipeline.search import search_quote_excerpts
from pipeline.search_queries import verbatim_quote_query
from pipeline.text_boundaries import has_reported_quote

# The two posts reported from testing on 21 September.
SARA = (
    "‘WE DESERVE BETTER LEADERSHIP THAN THIS’\n"
    "Vice President Sara Duterte criticized the Marcos administration over the South Cotabato "
    "school shooting, accusing the government of focusing on “political survival and "
    "consolidation” and compromising the protection of children.\n"
    "“Para kasi sa administrasyong Marcos, mas madali ang maging inutil, magnakaw, at "
    "magsamantala kaysa magsilbi nang tapat sa bayan,” Duterte stated.\n"
    "READ MORE: https://inqnews.net/Sarablamesadmin See less"
)
SARA_TRANSLATED = (
    "‘WE DESERVE BETTER LEADERSHIP THAN THIS’\n"
    "Vice President Sara Duterte criticized the Marcos administration over the South Cotabato "
    "school shooting, accusing the government of focusing on “political survival and "
    "consolidation” and compromising the protection of children.\n"
    "“For the Marcos administration, it is easier to be useless, to steal, and to exploit "
    "than to serve the country honestly,” Duterte stated.\n"
    "READ MORE: https://inqnews.net/Sarablamesadmin See less"
)
SARA_QUOTE = ("Para kasi sa administrasyong Marcos, mas madali ang maging inutil, magnakaw, at "
              "magsamantala kaysa magsilbi nang tapat sa bayan")
ATASHA_QUOTE_SENTENCE = (
    "“Of course they gave me the best advice, which was, ‘You know what, just work "
    "hard, keep on your feet on the ground and focus lang,’” she shared."
)
ATASHA = (
    "‘Bongga Ka 'Day’ musical star Atasha Muhlach opens up about the best advice she "
    "received from her parents, Aga Muhlach and Charlene Gonzales, on how to handle showbiz "
    "intrigues.\n" + ATASHA_QUOTE_SENTENCE + "\n#CelebrityNews #AtashaMuhlach #AgaMuhlach See less"
)


class ReportingVerbTests(unittest.TestCase):
    def test_the_verbs_philippine_reporting_uses_are_recognised(self):
        for tail in ["she shared.", "he added.", "she revealed.", "he recalled.", "she explained."]:
            with self.subTest(tail=tail):
                self.assertTrue(has_reported_quote(f"“We will keep going,” {tail}"))

    def test_the_verbs_that_already_worked_still_do(self):
        self.assertTrue(has_reported_quote("“We will keep going,” she said."))
        self.assertTrue(has_reported_quote("“Hindi ako aalis,” aniya."))

    def test_a_verb_inside_the_quotation_is_still_not_an_attribution(self):
        self.assertFalse(has_reported_quote("“She shared everything with us today.”"))

    def test_atashas_quote_is_no_longer_filed_as_opinion(self):
        """Its one opinion word, "best", is hers; the reported quote goes on to be checked."""
        routed = profiler._route_segment(ATASHA_QUOTE_SENTENCE, "s2", None)

        self.assertTrue(routed["eligible_for_verification"])
        self.assertNotEqual(routed["recommended_route"], "stop_opinion_detected")


class PostChromeTests(unittest.TestCase):
    def test_the_footer_link_and_see_less_leave_the_pool_query(self):
        query = build_event_search_query(SARA, SARA_TRANSLATED)

        for chrome in ["READ MORE", "Sarablamesadmin", "inqnews", "See"]:
            with self.subTest(chrome=chrome):
                self.assertNotIn(chrome, query.split())
        self.assertIn("Sara Duterte", query)
        self.assertIn("South Cotabato", query)

    def test_see_more_and_bare_links_go_too(self):
        query = build_event_search_query(
            "Senator Robin Padilla files a bill on juvenile justice. See more www.example.ph/story")

        self.assertNotIn("See", query.split())
        self.assertNotIn("www.example.ph/story", query)
        self.assertIn("Robin Padilla", query)


class VerbatimQuoteQueryTests(unittest.TestCase):
    def test_a_translated_claim_searches_the_words_as_they_were_said(self):
        claim = {
            "claim_text": ("“For the Marcos administration, it is easier to be useless, to "
                           "steal, and to exploit than to serve the country honestly,” "
                           "Duterte stated."),
            "attribution": {"speaker": "Sara Duterte"},
        }

        result = verbatim_quote_query(claim, SARA, SARA_TRANSLATED)

        self.assertEqual(result["quote"], SARA_QUOTE)
        self.assertTrue(result["query"].startswith("Duterte Para kasi"))

    def test_an_english_post_with_a_quote_inside_a_quote(self):
        claim = {"claim_text": ("Atasha Muhlach said her parents advised her to just work hard, "
                                "keep her feet on the ground and focus."),
                 "attribution": {"speaker": "Atasha Muhlach"}}

        result = verbatim_quote_query(claim, ATASHA, ATASHA)

        self.assertIn("just work hard", result["quote"])
        self.assertNotIn("‘", result["query"])
        self.assertTrue(result["query"].startswith("Muhlach "))

    def test_a_tagalog_quote_inside_an_english_post_is_found_as_it_is(self):
        """Held-out H15: detected as English, so a Filipino-only rule never reached it."""
        post = ("Sen. Robin Padilla said the school incident strengthened his decision.\n"
                "Sen. Robin Padilla said, “Hindi naman ako bulag at bingi.”")
        claim = {"claim_text": "Sen. Robin Padilla said, “Hindi naman ako bulag at bingi.”",
                 "attribution": {"speaker": "Robin Padilla"}}

        result = verbatim_quote_query(claim, post, post)

        self.assertEqual(result["quote"], "Hindi naman ako bulag at bingi")
        self.assertEqual(result["query"], "Padilla Hindi naman ako bulag at bingi")

    def test_a_quotation_too_short_to_search_for_is_left_alone(self):
        post = "The mayor called the plan “very bad” on Monday."
        claim = {"claim_text": "The mayor called the plan very bad on Monday.",
                 "attribution": {"speaker": "the mayor"}}

        self.assertIsNone(verbatim_quote_query(claim, post, post))

    def test_the_surname_is_not_repeated_when_the_quote_already_says_it(self):
        post = "“Duterte will answer for every peso of this budget,” Hontiveros said."
        claim = {"claim_text": post, "attribution": {"speaker": "Sara Duterte"}}

        result = verbatim_quote_query(claim, post, post)

        self.assertEqual(result["query"].split().count("Duterte"), 1)


def _result(url, source, description):
    return {"url": url, "source": source, "title": url, "description": description,
            "extra_snippets": []}


class QuoteSearchTests(unittest.TestCase):
    def search(self, results, pooled=None):
        # As Brave's pass comes back: one report per source, which is where source order lives.
        reports = [{"source": name, "results": []}
                   for name in dict.fromkeys(result["source"] for result in results)]
        found = {"query": "q", "total_results": len(results), "results": results,
                 "source_reports": reports}
        with patch("pipeline.search.search_sources", return_value=found):
            return search_quote_excerpts("Duterte " + SARA_QUOTE, SARA_QUOTE, pooled)

    def test_an_excerpt_that_repeats_the_quotation_is_kept(self):
        inquirer = _result("https://newsinfo.inquirer.net/2308694/sara-duterte-blames",
                           "Philippine Daily Inquirer",
                           f"“{SARA_QUOTE},” Duterte said in a statement on Sunday.")

        articles = self.search([inquirer])["articles"]

        self.assertEqual([a["url"] for a in articles], [inquirer["url"]])
        self.assertEqual(articles[0]["evidence_type"], "search_excerpt")

    def test_a_page_that_only_shares_a_word_with_it_is_not(self):
        """A PNoy speech says "magnakaw" too. That is not a report of what Duterte said."""
        speech = _result("https://www.gmanetwork.com/news/topstories/nation/213931/pnoy-speech",
                         "GMA News",
                         "Hindi tayo papayag na magnakaw ang sinuman sa kaban ng bayan, sabi ng Pangulo.")

        self.assertEqual(self.search([speech])["articles"], [])

    def test_a_page_the_pool_read_in_full_is_left_to_the_pool(self):
        url = "https://www.gmanetwork.com/news/topstories/regions/1003096/live-updates"
        pooled = [{"url": url, "evidence_type": "full_text", "status": "extracted",
                   "text": "The whole article."}]
        live = _result(url, "GMA News", f"“{SARA_QUOTE},” said Duterte.")

        self.assertEqual(self.search([live], pooled)["articles"], [])

    def test_an_excerpt_the_pool_already_had_gains_the_quoted_passage(self):
        """The pool's excerpt was cut for a different query and did not show the quotation."""
        url = "https://newsinfo.inquirer.net/2308694/sara-duterte-blames"
        pooled = [{"url": url, "evidence_type": "search_excerpt", "status": "extracted",
                   "text": "Duterte blamed the administration for the Banga school shooting."}]
        quoted = _result(url, "Philippine Daily Inquirer", f"“{SARA_QUOTE},” Duterte said.")

        text = self.search([quoted], pooled)["articles"][0]["text"]

        self.assertIn("inutil", text)
        self.assertIn("Banga school shooting", text)

    def test_an_opinion_page_is_judged_by_the_same_gate_as_any_other_evidence(self):
        """
        The quote search makes no opinion decision of its own. Every article, however it was
        found, passes the evidence gate in app.py, which keeps columns out of a factual claim
        and admits them for an attributed statement (saved case B07). A quote search that
        refused them itself would quietly change that policy for quote claims alone.
        """
        import app

        column = _result("https://opinion.inquirer.net/194280/a-column-on-duterte",
                         "Philippine Daily Inquirer", f"“{SARA_QUOTE},” she said.")
        found = self.search([column])["articles"]

        self.assertEqual(len(found), 1)
        self.assertTrue(app.opinion_evidence_blocked(found[0], {"claim_type": "factual_claim"}))
        self.assertFalse(app.opinion_evidence_blocked(found[0], {"claim_type": "attributed_statement"}))


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.pool = {"used": True, "search_result": {
            "articles": [{"url": "https://mb.com.ph/a", "status": "extracted",
                          "evidence_type": "full_text", "text": "Pool article.",
                          "evidence_pool": "event_context"}],
            "total_search_results": 1, "source_summary": [], "search": {}}}

    def test_a_quote_claim_now_searches_its_quotation_first(self):
        claim = {"is_quote_derived": True, "claim_text": "x",
                 "quote_search": {"query": "Duterte " + SARA_QUOTE, "quote": SARA_QUOTE}}
        found = {"articles": [{"url": "https://newsinfo.inquirer.net/2308694/a",
                               "status": "extracted", "text": SARA_QUOTE}],
                 "total_search_results": 1, "source_summary": [], "search": {}}

        with patch.object(self.app, "search_quote_excerpts", return_value=found) as searched:
            result, mode = self.app.build_claim_search_result(claim, "tagalog", "x", "x", self.pool)

        searched.assert_called_once()
        self.assertEqual(mode, "quote_search_plus_event_pool")
        self.assertEqual([a["url"] for a in result["articles"]],
                         ["https://newsinfo.inquirer.net/2308694/a", "https://mb.com.ph/a"])

    def test_a_quote_claim_with_nothing_to_search_keeps_to_the_pool_as_before(self):
        claim = {"is_quote_derived": True, "claim_text": "x", "quote_search": None}

        with patch.object(self.app, "search_quote_excerpts") as searched:
            _, mode = self.app.build_claim_search_result(claim, "english", "x", "x", self.pool)

        searched.assert_not_called()
        self.assertEqual(mode, "event_pool_only")

    def test_a_quote_search_that_finds_nothing_leaves_the_pool_as_it_was(self):
        claim = {"is_quote_derived": True, "claim_text": "x",
                 "quote_search": {"query": "q", "quote": "q q q q"}}
        empty = {"articles": [], "total_search_results": 0, "source_summary": [], "search": {}}

        with patch.object(self.app, "search_quote_excerpts", return_value=empty):
            _, mode = self.app.build_claim_search_result(claim, "english", "x", "x", self.pool)

        self.assertEqual(mode, "event_pool_only")

    def test_the_quotation_searched_is_part_of_the_cached_verdicts_key(self):
        claim = {"is_quote_derived": True, "claim_text": "x",
                 "quote_search": {"query": "Duterte Para kasi", "quote": "Para kasi"}}

        basis = self.app.build_claim_cache_basis("x", claim, None, None)

        self.assertIn("quote_search:Duterte Para kasi", basis)


if __name__ == "__main__":
    unittest.main()
