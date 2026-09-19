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

## Change record: 19 September 2026

Reason: a review of 47 saved TRACE requests found that direct downloads from four approved publishers failed consistently: PNA 185/185, PIA 169/169, Manila Bulletin 155/155 and Inquirer nearly all attempts. A single test request confirmed a Cloudflare bot challenge. Their RSS feeds are also challenged, except Inquirer's, which contain only about 40 recent short excerpts. VERA Files returned HTTP 429 for about one in three downloads. IRIS does not attempt to circumvent publisher bot protection.

Changes:

1. Inquirer, Manila Bulletin, PNA and PIA moved to search-excerpt access instead of being removed. In saved case C07, the correct Inquirer article was the top search result, and its search excerpts alone contain the press-conference date, place and concert details.
2. Added Rappler (IFCN-signatory fact-checker, priority layer), DZRH News and OneNews.PH (TV5/Cignal news; TV5's own news site is challenged). All three served article pages and were indexed by the search API during testing. The lookalike domain dzrhnews.com.ph is a parked site and is not approved.
3. Verdict cache version changed to `week7-sources-excerpts-v18` so results computed with the old source list are not reused.

Evaluation note: this changes the evidence pool, so results after this date are not directly comparable to the 18 September 34-case baseline without noting the source-policy change. Each claim now makes 11 search requests instead of 8.
