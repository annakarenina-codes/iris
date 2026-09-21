# Approved Sources

Defined in [pipeline/sources.py](pipeline/sources.py). Fact-checking organizations are searched first and receive a small ordering bonus in similarity ranking; they are not treated as automatically correct.

| Layer | Source | Domain | Evidence access |
|---|---|---|---|
| Fact-check | VERA Files | verafiles.org/articles | Full text |
| Fact-check | Rappler | rappler.com | Full text |
| News | ABS-CBN News | abs-cbn.com | Full text |
| News | GMA News | gmanetwork.com | Full text |
| News | Philippine Daily Inquirer | inquirer.net | Search excerpt |
| News | Philippine Star | philstar.com | Full text |
| News | Manila Bulletin | mb.com.ph | Search excerpt |
| News | Philippine News Agency | pna.gov.ph | Search excerpt |
| News | Philippine Information Agency | pia.gov.ph | Search excerpt |
| News | DZRH News | dzrh.com.ph | Full text |
| News | OneNews.PH | onenews.ph | Full text |

## Evidence access

- **Full text:** IRIS downloads the article page and extracts its body text.
- **Search excerpt:** IRIS does not download the page. It uses the article passages that the Brave Search API returns for that result (the result description plus up to five `extra_snippets`). These are the publisher's own sentences, cleaned of highlight markup and de-duplicated. Records are labeled `evidence_type: search_excerpt` and `extraction_quality: excerpt` in API responses and TRACE.
- If a full-text download fails (for example HTTP 429 from VERA Files), IRIS uses that result's search excerpt instead, with `excerpt_reason: download_failed` and the original `download_error` retained.
- An excerpt shorter than 8 words is not evidence. Excerpts pass through the same URL rules, attribution/incident gates and component evidence review as full text.

Limits: an excerpt contains only a few passages, so a detail that appears only deep in a long article can be missed and the claim remains Not Found. Excerpt availability depends on the search provider.

Publication dates returned by the search provider are deliberately **not** recorded or used as time evidence.

## Search passes

Every claim is searched on its own, in its own words, against every source ([pipeline/search.py](pipeline/search.py)). The passes of one claim run at the same time, and their results are merged in pass order, so what is read never depends on which request answered first:

1. **primary**: the claim's query, with any date, number or short quoted title from the claim that the generated query dropped appended to it ([pipeline/search_queries.py](pipeline/search_queries.py)). An attributed claim that names its speaker only as "she" or by surname gets the speaker's name in front.
2. **recent**: the same query restricted to the past month (Brave `freshness=pm`), so current coverage is not pushed out of the top results by older articles on the same subject. This only ranks search results. A publication date is never evidence: retrieved text must state the claimed date itself.
3. **original_language**: for Filipino/Taglish posts, the post's own sentence that the claim was translated from.
4. **translated**: when the claim keeps a quotation in the language it was said in, the claim with that quotation in English. It takes the place of the original-language pass, whose words the claim itself then carries.
5. **backup**: the previous fallback, only when the other passes return fewer than two results.

The fact-checkers' sitemap lookup runs beside the passes and never holds them up: an index already in memory is answered at once and refreshed in the background, and only a first read is waited for, at most six seconds.

Up to three articles per source are read, taking each pass's best result before any pass's second. All the claims of a post search at the same time, and every Brave request in the process takes its turn under a limit of 40 a second (the plan allows 50).

Every readable article that any claim of a post found is offered to the post's other claims: at most 12 per claim, those sharing most of the claim's words first. Offered articles pass the same gates and the same component review as a claim's own, so sharing an article is never evidence by itself.

The reviewer reads at most 60,000 characters, each article cut to its first 12,000. When a claim's articles do not all fit, they are ranked by their best passage, not by their opening, so where in an article the evidence sits no longer decides whether it is read.

Known limit: some pages are not in the search provider's index at all (for example the GMA article for saved case A09, which does not appear even for its exact headline, and GMA's 24 Oras video transcript pages). No query change can retrieve those.

## Change record: 19 September 2026

Reason: a review of 47 saved TRACE requests found that direct downloads from four approved publishers failed consistently: PNA 185/185, PIA 169/169, Manila Bulletin 155/155 and Inquirer nearly all attempts. A single test request confirmed a Cloudflare bot challenge. Their RSS feeds are also challenged, except Inquirer's, which contain only about 40 recent short excerpts. VERA Files returned HTTP 429 for about one in three downloads. IRIS does not attempt to circumvent publisher bot protection.

Changes:

1. Inquirer, Manila Bulletin, PNA and PIA moved to search-excerpt access instead of being removed. In saved case C07, the correct Inquirer article was the top search result, and its search excerpts alone contain the press-conference date, place and concert details.
2. Added Rappler (IFCN-signatory fact-checker, priority layer), DZRH News and OneNews.PH (TV5/Cignal news; TV5's own news site is challenged). All three served article pages and were indexed by the search API during testing. The lookalike domain dzrhnews.com.ph is a parked site and is not approved.
3. Verdict cache version changed to `week7-sources-excerpts-v18` so results computed with the old source list are not reused.

Evaluation note: this changes the evidence pool, so results after this date are not directly comparable to the 18 September 34-case baseline without noting the source-policy change. Each claim now makes 11 search requests instead of 8.

## Change record: 20 September 2026 — VERA Files behind a challenge page

Reason: every VERA Files page (articles, home page, RSS feed) began answering automated requests with HTTP 429 and a "Verifying if your connection is secure" page served by Deflect, a DDoS-protection service. The same is true for a browser-like request. This cost IRIS its most reliable source: saved case C08 is verified only by a VERA fact-check, and the sitemap lookup added on 19 September found that article but could not read it.

IRIS does not attempt to solve or circumvent the challenge. Instead it reads the article through the **public article API the same site publishes** (`verafiles.org/wp-json/wp/v2/posts`), which returns 200 and the article's own full text. The sitemap (`sitemap.xml`) also still serves normally, so fact-check discovery is unaffected.

Changes ([pipeline/publisher_api.py](pipeline/publisher_api.py)):

1. A source may declare a `content_api`. Only VERA Files declares one. For such a source the article is read from the API first and downloading is the fallback, which is faster and sends the publisher fewer requests.
2. The API is asked for the article's slug; if the stored slug differs, it is asked for the slug's words. **The returned article's own address must match the address IRIS asked for**, otherwise nothing is used. Text is used only if it is at least 8 words.
3. An API failure is never fatal: the article falls back to a download, and then to a search excerpt.
4. Records read this way are `extraction_method: publisher_api`. They are full article text, so they stay `evidence_type: full_text`.

Request volume ([pipeline/article_extractor.py](pipeline/article_extractor.py)): a post with several claims used to download the same article once per claim. Readings are now cached in process for 15 minutes per URL, requests to one publisher are serialised and spaced at least 1 second apart, and a 429 is retried twice. C08 read the VERA fact-check in 1.6 seconds.

Result: C08 claim 1 is **Verified** on the VERA fact-check `fact-check-romeo-poquiz-did-not-make-viral-statement-vs-marcoses`, which IRIS previously could not read at all.

## Change record: 22 September 2026 — every claim searches, quotations keep their words

Reason: a Sara Duterte post came back Not Found for a quotation that Inquirer and GMA both printed. Claims taken from quotations did not search on their own at all: they read a single search built for the whole post from its capitalised words, so neither the claim's words, nor its Filipino sentence, nor the fact-check lookup was ever searched. The same path accounted for held-out posts H15 and H16. The post was also read as Tagalog and translated whole, so the claim carried the quotation in English rather than as said.

Changes:

1. Every claim runs its own passes; the post-wide search is gone. The claims of a post share what they find, as described above.
2. A quotation translated with its post is put back in its original words in the claim; the English rendering becomes the `translated` pass and is shown to the reviewer as a non-evidence aid (`claim_english_rendering_not_evidence`).
3. The passes of a claim, and the claims of a post, search at the same time under a process-wide Brave limit.
4. The sitemap lookup no longer holds up a search (see above). The newest VERA Files sitemap page was 627 KB and took 23 seconds that day.
5. Articles that do not all fit the reviewer's budget are ranked by their best passage. Only passages sharing a distinctive word with the claim are embedded, at most 400 a claim, and embeddings are cached for the whole process.

Follow-up the same day, from the 34-case check of these changes. Quotation claims searching on their own for the first time exposed two limits of the search provider:

6. Straight double quotes are removed from every query. Brave reads them as an exact phrase, so a quotation typed with them could only be found worded exactly as the post worded it; in saved case A02 its five quotation claims got 2, 1, 0, 0 and 1 results. Curly quotes were never read that way.
7. Every query is cut, at a word, to Brave's limit of 400 characters and 50 words with its site filter. Two claims of saved case A08, whole sentences carrying their Filipino quotation, were refused by every source (HTTP 422) and reported as a search failure.
8. Articles shared between a post's claims are ranked on the claim's English rendering and speaker as well as its own words, so English reporting of a Filipino quotation is offered to it.
9. Passages are embedded by the review, for the articles it reads, and no longer ahead of it for every article a claim's search could read. Claims embed one at a time, so that work queued up: once quotation claims found their articles, a post with nine of them (A08) waited 29 seconds for embedding where its reviews needed 5.

Cache version `week8-own-search-v40`.

