# IRIS: reported-source and review-error diagnosis

Date: September 18, 2026. Backend cache version: `week7-source-review-repair-v16`.

## Bottom line

All seven authorized posts completed a fresh live rerun after the repairs.
That means the requests completed, not that all seven passed accuracy review.
Four cases have a successful targeted result; DepEd, VERA and Moira still have
retrieval, statement-scope or event-context issues described below.

The original two short timing lines did not contain enough detail to identify
their exact historical cause. The saved local database did not contain these
latest runs, and the local TRACE server was unreachable. We reproduced failures
with fresh requests instead; those reproductions must not be confused with the
original user's missing TRACE exports.

## What was tested

- Seven full `/verify` requests through the configured Brave Search and OpenAI
  services: Baste, Zuckerberg, Alex Eala, DepEd, Rene Baterbonia, Moira, and VERA/Poquiz.
- Verdict-cache reads/writes were bypassed in the evaluation runner. Results and
  TRACE databases were saved separately from the application's normal TRACE history.
- The eighth post, Robin Padilla's political flags, was covered by local regression
  tests, not another paid full-pipeline rerun or a Chrome UI test.
- The five supplied reference URLs were downloaded directly to distinguish
  discovery failure from extraction failure. These known URLs were NOT injected
  into production retrieval or the seven live verdict tests.
- No new failing image was supplied. OCR cleanup was tested locally; the latest
  real-image complaint cannot yet be marked resolved.

## Observed results

| Case | Latest live output | Assessment |
| --- | --- | --- |
| Baste subpoena | One claim, Verified; 31.51 seconds; GMA and PhilStar evidence | Targeted crash repair passed in this rerun. Both original assertion and evidence links were retained. This is not proof of general accuracy. |
| Zuckerberg / DICT budget | One claim, Verified; 24.01 seconds; two PhilStar articles | Targeted crash repair passed in this rerun. |
| Alex Eala / Anna Wintour | Two claims, both Verified; 53.35 seconds | Supplied ABS-CBN Entertainment article retrieved, extracted and cited. The complete Wintour quotation remained a claim. Targeted retrieval/extraction check passed. |
| Rene Baterbonia / UST | Two claims, both Verified; 32.60 seconds | Supplied ABS-CBN Sports article retrieved and cited for both claims. Targeted retrieval check passed. |
| DepEd / OJT | Three claims: Verified, Partially Verified, Not Found; 50.96 seconds | Not resolved. The exact supplied GMA article was absent from the tested search results despite extracting correctly when downloaded directly. Earlier related reporting was used instead. Do not count the whole post as an accuracy pass. |
| VERA / Romeo Poquiz | Two claims, both Not Found; 30.90 seconds | Invalid search-page citation is now blocked. Exact fact-check article still absent from tested search results. Also review extraction: the post's reported allegation and its denial must not be misrepresented as an endorsed assertion. Not a complete accuracy pass. |
| Moira / September 17 appearance | Two claims: Not Found, Partially Verified; 65.82 seconds | Cannot confirm the event from the supplied September 14 article. The partial result used older interviews, which does not establish a September 17 utterance. Event-context matching remains an accuracy concern. |

These durations include the actual service behavior of each saved run and are not
performance guarantees. Claim counts varied between some repeated runs; temperature
zero does not make the full external-service pipeline perfectly deterministic.

## Diagnosis by stage

### 1. Claim extraction and political flags

The supplied Padilla text uses abbreviations such as `Sen.` and then surname-only
quotations. A warning based on each isolated claim can miss that the quoted speaker
is an official. Matching now normalizes abbreviations and can use that speaker's
explicit office from the original post. It does not label unrelated speakers or
all claims political just because the post contains a politician.

The Moira and VERA results still need statement-scope review. For Moira, a generic
healing statement must not lose its connection to a particular media event. For
VERA, reporting that a false statement circulated is different from affirming the
statement itself. These are not fixed by widening source domains.

### 2. Search and candidate selection

ABS-CBN and GMA were restricted to `/news`. Queries now cover each publisher's
whole domain. Five candidates per source are requested instead of three; the
two-article extraction limit remains. Eala and Rene demonstrate that entertainment,
lifestyle and sports articles can now reach the actual evidence review.

The exact DepEd and VERA targets were not returned by the tested broad or targeted
Brave queries. This establishes a discovery gap, not definitive proof that Brave
has never indexed those pages. Increasing similarity thresholds or trusting a
search-results page would not repair it. A bounded publisher-side discovery
fallback is a possible next step and has NOT been implemented here.

### 3. Article extraction

One ABS-CBN page embedded related article bodies in its structured data. Combining
all those bodies made unrelated reporting appear to belong to the Eala article.
Extraction now isolates the primary article, parses HTML stored in article-body
fields and removes repeated paragraphs.

| Supplied article | Repaired body word count | Finding |
| --- | ---: | --- |
| Eala | 427 | Previously 2,642 words due to unrelated embedded articles. Primary story now isolated. |
| DepEd | 906 | Main body extracts successfully; missing discovery is the outstanding problem. |
| Rene | 383 | Sports article body extracts successfully. |
| Moira | 145 | Legitimately short article, still labeled `thin`; it covers a Spotify milestone and the concert, not the September 17 media appearance. |
| VERA | 530 | Fact-check body extracts successfully; duplicate paragraphs removed. |

See `source-baseline.json`, `source-reextract.json` and the saved HTML snapshots.
The repaired extraction comparison uses saved HTML with network access mocked;
the Eala/Rene full-pipeline results separately confirm live extraction.

### 4. Evidence review errors

Fresh baseline Baste and Zuckerberg requests both failed during
`event_identity_check`. Source IDs were assigned in sorted-URL order while
passages stayed in article order, without explicit ownership in each passage.
Model responses referenced passages belonging to the wrong source, and the strict
validator correctly rejected them.

Sources now use consistent article order, passages identify their owner, and each
source's response schema only permits that source's own passage IDs. Cross-source
validation remains strict. Both posts subsequently completed without this error.

### 5. External-service limits

Five requests in the first repaired batch hit OpenAI rate limits during the final
entailment check, so those intermediate runs are technical failures, not factual
Not Found results. A bounded single retry was then added for transient limits.

The final Moira run recorded a token rate limit, a provider-requested 25-second
wait and successful completion afterward. The new diagnostics identified it as
`rate_limit_exceeded`, not an oversized request. Other successful reruns did not
record this retry event; do not attribute all improvement to retrying.

Quota exhaustion, oversized requests, waits above 60 seconds and a second failed
attempt still yield a clear processing error with no fabricated verdict.

### 6. Citation safety and OCR

Search/category URLs and unapproved publisher URLs are filtered before extraction
and final citation. The VERA search page can no longer be presented as evidence.
This is a guardrail, not a replacement for retrieving the actual fact-check.

OCR now rejects narrowly matched interface text such as engagement counts and
Like/Comment/Share labels. It retains uncertain alphabetic words, especially
negation, and does not rewrite headlines. Existing layout selection remains.
Without a new failing image, no claim is made that all noisy-image cases are fixed.

## Saved run references

| Case | Result file | TRACE ID |
| --- | --- | --- |
| Baste | `rate-diagnosis/baste.json` | `f022db979c2f42899c6772d8b61d23fe` |
| Zuckerberg | `repaired-v16/zuckerberg.json` | `d59fa105107f4de28c676be61cc2cd89` |
| Eala | `bounded-retry/eala.json` | `266cf5aafbca4ee89aca2d7aba0a45a8` |
| DepEd | `bounded-retry/deped.json` | `f1161a3e70c94d788ee0ee5c7b58a086` |
| Rene | `bounded-retry/rene.json` | `c0eee467a90e4aad8d4d814c3a73bba9` |
| Moira | `bounded-retry/moira.json` | `8de06af62d52443fa38e0f07f62754dd` |
| VERA | `repaired-v16/vera.json` | `bb945a891f8e4894a1084fe6e4720347` |

Each run folder has its own `traces.sqlite3`. `baseline/` retains the reproduced
pre-repair failures. `search-probes.json` retains the extra targeted query results.

## Validation and next action

Final local suite: **239 passed, 1 skipped, 70 subtests passed**. The skipped test
is an existing manual full-post-count placeholder, not a passing live check.
Machine-readable output: `tests.xml`. No frontend rebuild was needed for these
backend changes; restart the backend to load the new code/cache version.

Next priorities: repair same-event context retention for the Moira case and add
bounded article discovery for the DepEd/VERA retrieval gaps. Retest those exact
failures before broad threshold or verdict changes. A failing image is still
needed to evaluate the latest OCR complaint end to end.
