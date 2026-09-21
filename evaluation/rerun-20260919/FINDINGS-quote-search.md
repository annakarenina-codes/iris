# Quote search, Facebook chrome and reporting verbs — rerun findings

Branch `quote-search`, commit `b3c0ccb`, cache `week7-quote-search-v40`, run 21 September 2026.
Compared against `speed-v38` (baseline) and `heldout-batch-1/results-speed` (held-out), the
latest full runs before the change. Tag `before-quote-search` is the code they ran.

## The first attempt, and why there is a v40

`quote-search-v39` (33 of 36 cases) was stopped when **A02** regressed from Verified to Not
Found. Its quote filter kept 21 excerpts for an auditor's Tagalog answer, 17 of them unrelated
pages that shared "hindi" and "siya". v40 requires an excerpt to name the speaker and repeat the
quotation's own words, not the language's.

## Baseline, 34 cases (+ D01, D02 new)

**70 unchanged, 6 moved, 7 added, 14 dropped.** Between `freeze-v36` and `speed-v38`, whose
change should not have moved verdicts, 6 claims moved and 26 were added or dropped by extraction
variance alone. The move count matches that noise floor exactly.

None of the six moves is on the quote-search path. Every claim that used it kept its verdict:
A02 (three claims), B14, C03 — all Verified before and after.

| moved | path | cause |
|---|---|---|
| A03 PV → Verified | claim search | untouched path |
| A05 Verified → NF | pool | claim reworded ("became emotional") |
| B04 Verified → PV | claim search | volatile claim; moved the other way in the previous run |
| B15 NF → Verified | claim search | untouched path; see OPEN-ISSUES item 1 |
| C06 PV → NF | pool | VERA cooled down 3× in this run; borderline date claim |
| C08 Verified → NF | claim search | **VERA's API unavailable 3× — zero VERA citations, so Refuted could not fire** |

## Held-out, 25 posts

**43 unchanged, 3 moved, 3 dropped.**

- **H16 Not Found → Verified.** One of the two posts flagged as "should be Verified". The
  pool query lost "Read" (from "Read more") and gained "should": fix #2.
- H19 Not Found → Refuted: correct (a VERA-debunked fake), but on an untouched path.
- H25 Not Found → Verified on "Cabanatuan has many coffee shops": a café review that should
  not be checked at all, the known routing gap.

## The two reported posts

- **D02:** No Checkable Claims → an attributed statement, checked. Not Found. Fix #3 works
  where the post failed; no source was supplied, so no verdict is expected yet.
- **D01:** claim 1 Verified; claim 2, the Tagalog quotation, **Not Found in the run.** The quote
  search found the Inquirer report the user supplied and Manila Bulletin; both passed every
  evidence gate; her words ranked **first of 567 passages**. Reviewed again on the same
  evidence, the reviewer verified it. The retrieval fix works; the reviewer is not consistent
  on this claim.

## What the reviewer caught

**H15**'s quotation, "Hindi naman ako bulag at bingi", found five excerpts that name a Padilla
and contain "bulag" and "bingi": Bela Padilla, Zsa Zsa Padilla, Gino Padilla and the OPM song
"Bulag, Pipi at Bingi". None reports Robin Padilla. The reviewer rejected all five, so no wrong
verdict came of it, but a surname and an idiom are still enough to pass the filter.

## Time

The quote search itself: **median 3.3 s, max 3.8 s** per claim, measured from trace spans.

Raw times rose — baseline median 46 → 54 s, held-out 40 → 68 s — but mostly not from this
change. The pool search, a stage it does not touch, went from **11.7 s to 25.8 s** median with
an unchanged query on the same posts. The network was slower on the day.

## Operational

VERA Files' API, the only way IRIS reads VERA (its pages sit behind a bot challenge), timed out
three times out of three after the run, while its homepage answered in 1.7 s.
