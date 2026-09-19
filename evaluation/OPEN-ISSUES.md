# IRIS open issues

Known problems deliberately left open, with the evidence gathered so far. Decisions pending with the project owner.

## 1. Old evidence can verify an undated "current" claim (B15 claim 1)

**Status:** open, deferred by the project owner on 19 Sept 2026.

- Post: "South Korean actor Byeon Woo-seok posted a photo update on Instagram." The post is about his 2026 fan-meeting announcement.
- 19 Sept rerun: **Verified**, citing a **2024** Manila Bulletin photo caption: "Korean star Byeon Woo-seok posted these photos taken in Manila on his Instagram account" (`mb.com.ph/2024/6/25/korean-star-byeon-woo-seok-feels-the-love-of-filipinos-moved-to-tears-at-fan-meeting`, search excerpt).
- Why it passes: the claim states no date, so the date rule (Step 2) has nothing to enforce, and "posted photos on Instagram" is true of many different posts. The 18 Sept audit recorded the same issue: "an old Instagram photo report supports an unspecified current update."
- The project owner judged the case acceptable in the 19 Sept review. It stays listed because the same pattern could let any old report verify a generic "recent" action.
- Possible directions: treat an undated claim as referring to the post's own event when the post contains other dated context; or require evidence that shares a distinguishing detail with the post (the fan-meeting tour) rather than only the generic action.

## 2. Articles the search provider cannot return (C04, A09, B05)

**Status:** open, decision pending: add a second search source, build a feed archive, or document as a limitation.

| Case | Article | What was tried |
|---|---|---|
| C04 | GMA, "Are K-12 grads ready for work, adult life? DepEd eyes longer OJT" (`gmanetwork.com/news/topstories/nation/1001536/...`) | Six Brave queries, including the exact headline, with and without `site:gmanetwork.com` and the past-month filter: never returned. It verifies all three C04 claims, including "He added that longer OJT could also improve graduates' chances…", which only this article contains. |
| A09 | GMA, "Peso rebounds to P62.513:$1, PSEi rises to 6,116.53" (`gmanetwork.com/news/money/economy/1001776/...`) | Exact headline, `P62.513`, `62.513`, Filipino text: never returned. |
| B05 | GMA 24 Oras Express video page with transcript (`gmanetwork.com/news/video/24oras/768350/...`) | Exact Filipino headline, keyword variants, recency filter: never returned. |

- All three are GMA pages that IRIS can download and read directly (a direct extraction works), so the gap is in the search provider's index, not in access.
- GMA's open RSS feed (`data.gmanetwork.com/gno/rss/news/feed.xml`) holds only about 16 items covering about one day, so it cannot reach older articles on demand.
- Options:
  1. **Second search API** as a fallback when Brave returns no usable evidence for a claim. Best coverage; needs an account and possibly a cost (to be evaluated).
  2. **Rolling feed archive**: poll open publisher feeds (GMA, Rappler, Inquirer) every 15–30 minutes and search that local archive as an extra pass. Free, but only covers articles published after it starts running.
  3. **Document as a known limitation** in the thesis.
- Manually supplying a URL does not count as retrieval success (audit rule).
