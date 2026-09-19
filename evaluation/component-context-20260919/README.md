# Stage 2: Component Context and Decomposition

Date: September 19, 2026. Scope: backend component review, not a new search strategy.

## What changed

- The reviewer receives the unchanged original extracted claim, rather than a normalized rewrite. Search normalization remains separate.
- Each component has an unchanged assertion, source offsets, and grounded references for subject, action, event, time, negation, and speaker. Every reference must occur verbatim in the claim or surrounding post. Missing roles remain empty.
- A component must contain a local subject and predicate to stand alone. Dependent fragments such as `arrested`, `causes`, and detached job titles are joined back to adjacent text. Joining never rewrites the assertion. If the model returns inconsistent component/context counts, the entire claim is conservatively recombined with validated references. Invalid or invented references still cause an explicit processing error.
- A separate context-resolution pass runs when surrounding text contains another explicit month/day but the initial component references omitted inherited time. It can identify the relevant interview without assigning an unrelated concert date. The unverified post is context, never evidence.
- Source identity keeps its semantic review and now records matching, conflicting, or unresolved context. An explicit event-time anchor must be established by selected identity passages, not a URL or article publication date. Matching dates alone never establish the correct person/event.
- Verbatim-citation validation, source eligibility, speaker checks, and independent entailment review remain in place. Provider or malformed-response failures do not produce factual verdicts.
- Cache version changed to `week7-component-context-v17`; the cache basis also includes original claim text. Restart the backend to use this version. No old database was deleted.

## Final live controls

Configured OpenAI models: `gpt-4.1-2025-04-14` for partition/context/identity/entailment and `gpt-4o-mini` for initial assessment. No new searches or article downloads were made.

| Case | Old saved outcome | Final targeted outcome | Stage 2 result and reason |
| --- | --- | --- | --- |
| B05 | Partially Verified | Not Found | Passed: the shooting and arrest remain one assertion. Another shooting's arrest earns no credit. |
| B12 | Partially Verified | Verified | Passed: the statement about Tony La Vina citing Legarda's environmental record stays intact, including `causes`; a matching Philstar passage supports it. This checks what he cited, not broader innocence claims. |
| A09 | Partially Verified | Not Found | Passed: the rate and September 9 session remain tied together. Different-session material does not verify the assertion. |
| C07 | Partially Verified | Not Found | Passed: the follow-up inherits the September 17 media appearance, not October 4's concert. The proposed GMA/ABS-CBN passages do not establish that interview date and are rejected. |

`Not Found` here means the saved evidence did not establish the specific assertion, not that the assertion is false.

## Audit record

- `final/<ID>-input.json`: selected original claim, full saved post context, and saved case article pool.
- `final/<ID>.json`: outcome, full grounded references, source decisions, model names, input/code hashes, elapsed time, and TRACE ID.
- `final/traces.sqlite3`: diagnostic capture for the final controls.
- Root-level outputs retain the initial attempt. B12 first returned a technical partition error; C07 initially returned Not Found for missing qualifiers while still accepting older events at the identity stage. Neither is counted as the successful final control.
- `repaired-partition/` and `context-resolution/` retain intermediate diagnostic retests. `final/` contains all four checks using the same production code revision.

There were ten component-review invocations in total during diagnosis and confirmation, covering four distinct case/claim pairs. Each invocation can make multiple model calls. These are not ten new full-request tests.

## Verification and limits

All 81 tests in the six targeted offline suites passed. They cover context grounding, complete partitions, short independent statements, invalid references, provider failures, original-text forwarding, cache identity, event identity, and existing quote retrieval. Python compilation also passed. The four saved results passed the following offline checker, which makes no API calls:

```powershell
python evaluation/component-context-20260919/check_saved.py
```

The broader quotation/claim-coverage pytest suites were not run: pytest is not installed in either inspected Python runtime. This is not a full test-suite pass.

These controls use successful complete article extractions from each saved case. Older TRACE artifacts do not preserve the exact per-claim review arguments, so this is NOT a byte-identical replay or a fresh end-to-end request. Evidence input retains the reviewer's existing 12,000-character per-article and 60,000-character total limits. Retrieval, URL reachability, upstream claim extraction, and all other 30 cases were not revalidated here.

Reference selection still uses a model: verbatim grounding prevents invented words but cannot alone prove that an antecedent was correctly chosen. Shared-subject clauses may be conservatively merged, reducing partial-verdict granularity. The deterministic date guard covers English month/day expressions and explicit years in selected time references; it does not resolve all relative, numeric, multilingual, or ambiguous dates. Missing years are never invented. A valid same-event article that omits an explicit date can remain unresolved. Further calibration should include such positive controls and genuinely separate events in one sentence.

Next: continue the planned evidence-matching work and fresh-search/end-to-end regressions separately. Do not interpret these four stage checks as overall system accuracy.
