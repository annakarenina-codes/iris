# IRIS claim completeness and evidence matching: review

Date: September 14, 2026 (Asia/Manila)

## Bottom line

The code changes and local regression tests are complete for this iteration.
There is measurable progress, but the verdict system is NOT fully calibrated.
Brave Search worked in the latest full live run. OpenAI interrupted the long
case with HTTP 429 (a provider rate limit), not a search failure.

The latest code is `week7-coverage-entailment-v12`. Restart the backend to load it.
No extension or Android rebuild is required for these backend changes.

## Changes made

- Removed silent ten-claim and thirty-segment truncation.
- Added a source coverage ledger: each approved input sentence is linked to
  claims or given an exclusion reason. Source passages come from the actual
  input, not model-generated quotations.
- Added reviewed merging/splitting and full-assertion duplicate fingerprints.
  Different dates, negation and speakers are not collapsed as exact duplicates.
- Stopped a longer local fallback from replacing a successful reviewed inventory.
  A rejected merge now keeps the validated inventory and records its failure.
- Preserved the whole single assertion when nothing was split or excluded,
  including the Padilla/Wamil sentence's final funds rationale.
- Applied final component review to factual as well as attributed claims.
  Similarity and the earlier AI fallback cannot bypass this review.
- Replaced generated evidence quotations with selection of original passage IDs.
  Valid-source links and speaker/context requirements remain in place.
- Used fixed component-ID response keys; the final input word is always included.
  Improved component boundaries and kept possessives with their objects.
- Added rejection of a missing asserted year, and a bounded named-victim guard
  for referential incident claims. Unrelated CCTV articles cannot pass that
  guard without mentioning the resolved victim. This is not proof by itself.
- Kept technical failures separate from factual verdicts. Rate limits now have
  their own diagnostic reason; errors do not reuse a positive fallback verdict.
- Pinned the new coverage, partition and independent evidence-check steps to
  GPT-4.1 by default, with separate environment overrides. The global draft
  model setting was not changed. This adds cost and may add latency.

## Results in plain language

| Check | Result | Reason |
|---|---|---|
| Local regression suite | Passed | 169 tests passed, 1 skipped; 28 subtests also passed. This measures code behavior, not real-world accuracy. |
| Case 3: core extraction coverage | Passed for the latest full run | Eleven claims covered the incident, injured companion, investigation, condemnation, 1975 work, written evidence, oral testimony, ruling, research, advocacy and tributes. Written and oral testimony were separate. |
| Case 3: duplicate removal | Passed for that run, not proven consistent | The latest full run did not repeat the written-evidence assertion. An earlier replay did, so repeatability remains a calibration risk. |
| Case 3: removal of evaluative wording | Failed | Some wording such as 'overwhelmingly' and 'strong advocate' remained. The ledger does not guarantee perfect semantic cleanup. |
| Case 3: complete live verdict run | Cannot yet judge | The request reached claim 10, then OpenAI returned HTTP 429. The endpoint returned HTTP 503, null verdict and no evidence links. It did not finish all eleven claims. |
| Wrong-incident negative test | Passed | The saved Yulo-ambush article was rejected for the Carpenter investigation. The identity guard and the independent model check both rejected it in the focused replay. |
| Wrong-year negative test | Passed | A passage describing oral testimony in 2016 did not verify testimony specifically in 2015. The whole assertion was preserved, rather than scoring the person's name separately. |
| Investigation component boundaries | Passed in the focused replay | Four action groups were retained. 'Pursuing leads' was no longer split into a verb and an isolated noun. |
| Investigation paraphrase judgment | Cannot yet judge | The reviewer rejected intelligence validation/reconstruction of movements as support for 'pursuing leads.' This may be too literal and needs a reference-evidence judgment, not a forced label. |
| Case 7: fresh full request | Passed for completion | HTTP 200 in 25.692 seconds, Partially Verified, with three accepted links. The full input assertion was retained. This was the v10 run, before the final boundary changes. |
| Case 7: final boundary replay | Passed for text preservation | Four components retained the full sentence; 'Duterte's use of confidential funds' stayed together. Overall result remained Partially Verified. |
| Case 7: funds-rationale evidence judgment | Failed | The final reviewer still treated evidence about terrorism/security and funds as supporting the plural rationale, without adequately establishing the medicines connection. The overall partial verdict does not excuse this component-level error. |
| All ten cases on the final code | Cannot yet judge | This iteration retested saved cases 3 and 7 and focused evidence pairs, not all ten. The workbook has not been marked passed. |

## Exact run records

| Run | Scope | TRACE reference / result |
|---|---|---|
| `coverage-entailment-v10-live/case-03.json` | Fresh complete endpoint request with Brave/OpenAI; cache bypassed | `c394b883bd34430faabfcd993558e8df`; HTTP 503 after 219.722 seconds; provider rate limit |
| `coverage-entailment-v10-live/case-07.json` | Fresh complete endpoint request with Brave/OpenAI; cache bypassed | `e5cde146525349c29a8cbc3da507b7d0`; HTTP 200; Partially Verified |
| `coverage-entailment-v11-boundaries/investigation.json` | Fresh model review of saved relevant articles only | `c2326f42b5b543bf97458874e94a08b5`; Partially Verified; four components |
| `coverage-entailment-v11-boundaries/wrong-incident.json` | Fresh model review of saved unrelated article only | `6f97f676c96d420fbe3e07c5a295bd5d`; Not Found |
| `coverage-entailment-v11-boundaries/testimony-year.json` | Fresh model review of saved mismatched-year evidence only | `6cd23730044946bcaf7c1358303838c5`; Not Found |
| `coverage-entailment-v12-padilla/padilla-wamil.json` | Final-code model review of saved ABS-CBN/Philstar articles only | `8e8c37f3f32248388219f3414bb55fb6`; Partially Verified; three of four components marked supported, including the disputed rationale |

Paths in the table are relative to this report. Each run directory retains
the inputs/results and a manifest with model settings and code hashes. SQLite
TRACE files retain available diagnostics; TRACE captures can be truncated and
should not be treated as exhaustive logs. A saved-article replay does not test
fresh search, translation, extraction, HTTP delivery or browser timeouts.

The final local test record is `coverage-entailment-tests.xml`: 169 passed,
1 skipped, 28 subtests passed in 31.52 seconds. The skipped test is the existing
manual full-post claim-count placeholder, which has no filled-in input/count.

## What still needs work

1. Fix the plural-rationale evidence error using an explicit reference decision:
   proving the terrorism/funds relationship must not silently prove a separate
   medicines/funds relationship. Preserve faithful paraphrases without granting
   support merely because topics appear together.
2. Check extraction wording and repeatability on held-out posts, not only these
   two examples. A complete sentence ledger is not a completeness guarantee.
3. Complete one fresh eleven-claim run after provider capacity is available,
   then rerun all ten saved cases. The 219-second run also exceeds a 120-second
   frontend timeout, so long-post delivery remains an operational limitation.

## Short glossary

- **Claim:** the statement IRIS is trying to check.
- **Component:** a distinct factual part inside one claim; not a word or topic.
- **Coverage ledger:** a list showing where each input sentence went.
- **Verbatim passage:** words copied directly from a retrieved article.
- **Entailment:** whether the passage actually establishes the assertion, not
  merely discusses the same person or topic.
- **Negative test:** evidence deliberately chosen because it should not support
  the claim, such as another incident or the wrong year.
- **Replay:** a fresh model check using articles already saved from an earlier run.
- **HTTP 429:** the external service refused the request because of a limit.
- **HTTP 503:** IRIS could not finish processing; this is not a truth verdict.
