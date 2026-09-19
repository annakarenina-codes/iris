# Evidence-Review Crash Repair

## Diagnosis

Both historical failures reached the component-partition stage and received altered text from the model. Exact input-coverage validation rejected that text before evidence assessment could complete. The validator was protecting the assertion; weakening it would hide the defect.

- Case 3: the saved component AI artifact contains `Cardi` followed by U+001F and `o`, instead of `Cardi\u00f1o` (Cardino with the original n-tilde). The following review artifact records ValueError and no verdict. Original TRACE: e1954008fae3471796846bcd587d0b01; relevant artifact: 434893339caf41cea41cf9e134025751.
- Case 7: the returned partition substituted U+0014 for the em dash and U+0019 for the curly apostrophe in Duterte's name. The claim's original Unicode characters were intact. Original TRACE: 369d0985d64b4d9885b964977a186fd5; relevant artifact: 48bf8cab085243c0a57b839776e5438c.

These findings come from the saved TRACE outputs, not a new live reproduction. They establish the observed text-corruption/partition-rejection failure, not why the model emitted those particular control characters.

## Repair

1. The model now selects component end positions from numbered source words. Python slices the original claim at those positions; the model no longer reproduces the component wording.
2. Positions must be strictly increasing, in range, and cover the final word. Invalid positions remain processing errors; the system does not silently replace a malformed partition with a verdict.
3. Both API calls request strict JSON schemas. Truncated/refused responses, malformed assessment records, missing IDs, and unknown statuses are rejected. Unicode is sent directly in the JSON payload.
4. The existing exact input-coverage and verbatim-evidence checks remain. Approved-source filtering, attribution anchors, and the requirement for a valid public evidence link are unchanged.
5. Review errors include a safe error code and failed stage in TRACE. HTTP responses use status 503, status processing_error, verdict null, and an empty evidence_sources array. They never present a review crash as Not Found.
6. Regression tests verify that an earlier positive fallback cannot survive a component-review failure and that no failed claim verdict is written to cache.
7. The cache version changed to week7-component-boundaries-v3. Existing cache records are retained, but old-version results cannot bypass the repaired pipeline.

There is no guarantee that every external API request will succeed. An unavailable provider or invalid response must still produce an explicit technical error. This change is not a revision of semantic thresholds or a claim that the model's evidence judgments are now perfectly accurate.

## Validation

- Focused suite: 13 tests and 20 subtests passed.
- Complete backend suite: 143 passed, 1 skipped, and 24 subtests passed. Results are in component-review-tests.xml.
- Tests cover Unicode preservation, invalid/missing/reordered boundaries, missing or malformed assessments, fabricated citation rejection, unchanged full/partial support handling, HTTP error shape, and prevention of positive-fallback/cache leakage after failure.

The prepared retest_component_review.py harness submits the two exact saved posts through the Flask /verify route with fresh TRACE capture and cache reads/writes bypassed. Its output directory is created exclusively, so previous results cannot be overwritten.

## Live Retest Status

Initially blocked pending explicit data-transfer approval. The user subsequently authorized sending both cases to the configured search and OpenAI services, and the live retest completed on September 13, 2026. Both requests returned HTTP 200 and completed component review without the prior crash. Remaining extraction and evidence-matching problems prevent a blanket accuracy pass. See [the live results and limitations](component-review-retest/RETEST-REVIEW.md), including partial TRACE capture status.

The Google Docs workbook was not edited in this repair. Restart the backend before testing the new code through either frontend.
