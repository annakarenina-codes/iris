# Live Translation and Screening Retest

Date: September 13, 2026 (Asia/Manila).

## Scope

Ran all ten exact saved inputs through the current language detector, translation function, and Content Profiler. External services were enabled; no mocked responses were used. Each run has a fresh TRACE ID in summary.json, a case JSON file, and events in traces.sqlite3.

This is NOT a full regression verdict run. Claim extraction, article retrieval, evidence matching, and final verdict generation were not executed. The earlier full-system results remain unchanged.

## Service Results

- All ten runs completed without an uncaught error.
- Five English inputs skipped translation as intended: cases 1, 3, 4, 7, 10.
- All five translation attempts returned a response rejected as service_error_response: cases 2, 5, 6, 8, 9. TRACE records translation.fallback with action preserve_original. Translation availability therefore FAILED this retest; the error-containment behavior PASSED.
- The translated_text field equals the original text for all ten cases. No service-error response became downstream verification text in this run.
- OpenAI profiling returned status ok for all eight calls: cases 2, 3, 4, 5, 6, 8, 9, 10. Cases 1 and 7 used local screening without an OpenAI call.
- All ten inputs remained eligible for further processing. Eligibility is permission to attempt claim extraction, NOT a factual verdict and NOT proof that every statement survived intact.

## Observed Results Per Case

The assessments below concern screening and text preservation only. Passing rows do not certify extraction counts, reference truth, or verdict accuracy.

| Case | Topic | Screening assessment | Observed result |
| --- | --- | --- | --- |
| 1 | Imaginary nine-dash-line ownership | Passed for approved cautious routing | Original sentence, including imaginary, preserved; proceed_with_caution and imaginary_qualifier_needs_context. Context and truth remain unresolved. |
| 2 | Padilla-Wamil hearing | Failed | Seven segments forwarded, but the quotation is split. Hindi po siya imbestigasyon is discarded while Evaluation po and the witness attribution remain. The confidential-agent question is also discarded while its follow-on instruction remains. This changes the available statement context. |
| 3 | Kent Carpenter | Passed for factual-content retention, with follow-up needed | Fourteen candidate segments retained, including the main factual assertions. Three opinion/eulogy segments excluded. Vague framing and mixed evaluative wording still reach extraction; this run cannot confirm that extraction will exclude or deduplicate them. |
| 4 | Bea Borres reunion and denial | Passed for preservation and routing | Entire original sentence and the denial retained as one eligible segment; no longer stopped as No Checkable Claims. This does not resolve the reference-evidence distinction about co-parenting. |
| 5 | Senate position and bail | Passed for retention, with quotation-grouping warning | All eleven segments retained, including the bail amount and named recipient. Quotations are still divided across segments, although no text was discarded here. Attribution and extraction accuracy remain untested. |
| 6 | EDSA rehabilitation | Failed clean segmentation; initial block resolved | All six substantive paragraphs reach further processing, including the amount and attributions. However, the abbreviation SEC. splits the headline: ANG GALING NI SEC. is dropped, leaving VINCE followed by a closing quotation mark attached to the first factual paragraph. |
| 7 | Padilla medicines and terrorism | Passed for preservation and routing | Whole original assertion retained as one eligible segment; local screening proceeds. Earlier evidence-review errors are outside this run. |
| 8 | Samaniego interview | Failed attribution-context preservation | Ten segments retained, including the named interview and date, but the quoted recommendation and rhetorical comparison are removed while adjacent fragments remain. These are not standalone factual events, but their attribution can be checked; screening currently loses that distinction and breaks quotation context. |
| 9 | Peso exchange rate | Passed for preservation and routing | Original Filipino sentence retained with currency symbol, 62.513, dollar amount, and date. It now proceeds cautiously instead of stopping. English translation itself did not succeed. |
| 10 | National Artists announcement | Passed for preservation and routing | Entire announcement and quantity ten retained as one eligible segment. No longer stopped before extraction. Confirmation of the actual announcement is outside this run. |

## What Improved

The previous whole-post screening blocks in cases 4, 6, 9, and 10 no longer occur. Translation failures are now contained instead of masquerading as claim text. However, case 6 still has a text-boundary defect, so it is not a complete pass.

## Next Narrow Repairs

1. Repair sentence boundaries around quotations and abbreviations before screening. Preserve a complete attributed utterance instead of filtering individual pieces of it.
2. Distinguish a recommendation or rhetorical question from the factual assertion that a named person said it. Do not treat a hypothetical comparison as a real event.
3. Diagnose the translation provider separately. Safe original-text fallback is working, but it does not demonstrate successful translation or adequate later multilingual retrieval.
4. Repeat this stage-only check after those repairs, then run claim extraction and the full evidence/verdict tests. Do not change final-verdict thresholds based on these preprocessing results.

No production code was changed during this retest. The Google Docs workbook was not edited in this run; these results are saved alongside the new local TRACE records.
