# Reported issues, 21 September 2026

Two posts from testing the deployed extension, traced end to end on the local backend at the
`before-quote-search` tag. They join the development set as **D01** and **D02**, and every
regression run from here on includes them.

## D01 — Sara Duterte's Tagalog quotation

**Reported:** claim 2 was searched as its English translation, not the words she said.

**Found:** worse than reported — it was never searched at all.

- `original_language_query` recovered the Tagalog sentence correctly.
- `build_claim_search_result` sends a quote-derived claim straight to the post-level pool
  (`event_pool_only`) whenever the pool found anything. The Tagalog was passed only on the
  other branch, so it was computed and discarded.
- The pool's query was `Sara Duterte WE DESERVE BETTER LEADERSHIP THAN THIS Marcos South
  Cotabato READ MORE Sarablamesadmin See Para administration`: the footer link, its slug and
  Facebook's "See less" control.
- Inquirer and Manila Bulletin are excerpt sources, so their evidence is Brave's snippet, which
  depends on the query. The Inquirer report was in the pool; its snippet did not show the
  quotation because nothing asked for it.

| searched as | reports carrying the quotation |
|---|---|
| the Tagalog | Inquirer 2308694, Manila Bulletin, GMA live updates |
| its English translation | GMA live updates only |

**Expected:** both claims Verified. The user supplied
- https://www.gmanetwork.com/news/topstories/nation/1003111/sara-duterte-slams-marcos-admin-over-banga-school-shooting-says-pinoys-deserve-better-leadership/story/
- https://newsinfo.inquirer.net/2308694/sara-duterte-blames-marcos-admin-over-recent-school-shootings

**Before the fix:** Verified, Not Found. 78 seconds.

## D02 — Atasha Muhlach's quotation

**Reported:** No Checkable Claims.

**Found:** rejected by the content profiler before anything was searched.

- "she shared" was not a reporting verb, so the quotation read as the page's own words.
- One opinion word, "best", scores 0.05 + 0.12 + a flat 0.30 = 0.47 against a 0.45 line.
  Inside her quotation it is her opinion, not the page's, but without a reporting verb the
  profiler could not tell.
- A reported quote skips the opinion check entirely (`content_profiler.py`, `_route_segment`),
  so recognising "shared" is enough on its own. Discounting opinion words inside quotation
  marks was considered and dropped: it is not needed here, and no case in either the
  development set or held-out batch 1 exercises it.

**Expected:** at least one attributed statement checked, rather than No Checkable Claims. No
source was supplied, so no verdict is expected of it yet.

**Before the fix:** No Checkable Claims. 7 seconds.

## The same fault elsewhere

Every claim of held-out **H15** and **H16** is a quote that never searched its own words —
the two posts flagged as "should be Verified" and set down at the time as retrieval gaps. H15
was detected as English although one of its quotes is Tagalog, which is why the fix searches
quotations in any language rather than only in Filipino posts.
