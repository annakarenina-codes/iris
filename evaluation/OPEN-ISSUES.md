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

## 3. A claim the evidence refutes is reported as "Not Found" (C08 claim 2)

**Status:** open, decision pending with the project owner (raised 20 Sept 2026).

- Post C08 claim 2: "Retired Maj. Gen. Romeo Poquiz made a statement against President Marcos Jr. and Liza Araneta-Marcos."
- After the VERA Files fix of 20 Sept, IRIS now reads the fact-check that settles it: "VERA Files found no records of Poquiz making this statement." Claim 1 ("at least two Facebook posts are claiming…") is **Verified** on that article.
- Claim 2 comes out **Not Found**, with the message "IRIS did not find enough approved-source evidence confirming that Romeo Poquiz made this statement." The reviewer read the denial — its own reason quotes "there are no records of Poquiz making this statement" — but returned `contradicted: false`, because the passage denies the event rather than asserting a conflicting fact.
- So the user is told nothing was found, when a fact-checker has actually established the opposite. IRIS has no verdict for a refuted claim: the labels are Verified, Partially Verified, Not Found, No Checkable Claims, Opinion Detected and Review Failed.
- Two decisions are needed, and both change what users see:
  1. Whether IRIS should report a refuted claim at all (a "False" or "Refuted" verdict, which the extension and the Android client would also have to display).
  2. Whether an explicit denial of an event should count as `contradicted` in the entailment review, which is a prompt change plus regression checks on every case that currently ends Not Found.
- Until then, "Not Found" covers both "no evidence" and "the evidence says this is false".

## 4. A02 claim 2 — under review by the project owner

**Status:** open, the project owner said on 19 Sept 2026 they are still deciding.

- Listed here so the case is not treated as settled in the final scoring. No code change is planned until the owner decides.

## 5. One person under two names in one post (B08)

**Status:** open, documented limitation.

- Entity resolution treats a nickname or short form and the full name as different people unless the post itself shows both together, so a component naming one form is not matched to evidence using the other.
- Nickname handling added on 19 September covers names quoted inside a fuller name ("Ferdinand 'Bongbong' Marcos Jr.") and forms the post itself introduces. It does not cover a nickname that only the news article uses.
