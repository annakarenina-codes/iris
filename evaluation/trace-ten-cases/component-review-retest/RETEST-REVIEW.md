# Cases 3 and 7: Live Evidence-Review Retest

Date: September 13, 2026 (Asia/Manila). The user explicitly authorized sending both saved inputs to the configured search and OpenAI services.

## Crash Regression Results

| Case | HTTP result | Duration | Component review | Crash regression |
| --- | --- | --- | --- | --- |
| 3: Kent Carpenter | 200 | 196.763 seconds | Two attributed outputs were reviewed successfully, each with two components and a retained GMA source link. | Passed for this run. |
| 7: Padilla/Wamil, medicines and terrorism | 200 | 22.403 seconds | One attributed claim was reviewed successfully as four components, with ABS-CBN and Philstar source links. | Passed for this run. |

The full /verify requests used the exact saved posts, live retrieval and live OpenAI calls. Cached verdict reads and writes were bypassed, and every returned claim has cache_hit false. No backend code was changed during this retest.

All three completed component reviews reproduce their normalized input claims exactly apart from whitespace. Cardino's original n-tilde, the em dash, and the curly apostrophe survived. No ComponentReviewError or component.review_failed event was observed. This confirms that the previously failing paths completed in this run, not that future provider requests cannot fail.

## Actual Outputs, Not Accuracy Scores

- Case 3 returned ten claims: seven Verified, one Partially Verified, and two Not Found. Claims 6 and 10 are duplicate versions of the police official's statement, both returned as Verified after component review.
- Case 7 returned one claim as Verified. Its component reviewer marked four of four components supported. That is the system's observed output, not an independent endorsement of its correctness.

## Remaining Accuracy Problems

1. Case 3 claim 5 (Carpenter investigation status) cites a Philstar article titled "Probers review MMDA videos in Jose Luis Yulo ambush" from 2019. This is a different event. Topic overlap about CCTV is not support for the Carpenter investigation.
2. Case 3 claims 6 and 10 duplicate the same attributed statement. The ten-output count therefore does not establish correct claim coverage. Separate tribunal-ruling, Verde Island Passage research/advocacy, and tribute assertions are absent as distinct outputs.
3. Case 3 claim 7 combines the 1975 research-start fact with the evaluative description "one of the world's leading experts," then labels the whole claim Verified. That mixed wording still needs extraction/calibration review.
4. Case 7's citation for the personal-background component discusses familiarity with terrorism and security threats rather than explicitly establishing the personal-background assertion.
5. Case 7's citation for the confidential-funds rationale component lists payment dates near communist-group anniversaries. That selected passage does not establish the whole medicines/terrorism rationale in the supplied assertion. Verbatim occurrence and a valid link alone do not establish full support.

Accordingly, the crash regression passes, but neither case receives a blanket factual-accuracy pass. The next repair should address extraction completeness/deduplication and whether each cited passage supports the actual component, while preserving the now-working technical-error handling. No thresholds were lowered and no expected verdict was forced in this run.

## Performance and Capture Limits

Case 3 took approximately 3 minutes 17 seconds. Its last claim's retrieval step took 39.69 seconds and logged repeated HTTP 429 responses for a VERA Files topic page. This is a separate retrieval/performance concern, not the previous component-text crash. Total request time is not the duration of the component review alone: the two component-review calls took approximately 3.97 and 3.53 seconds; case 7's review took approximately 5.36 seconds.

Both TRACE records have capture_status partial. The harness separately saved the complete returned HTTP JSON bodies in case-03.json and case-07.json. Detailed TRACE events may be incomplete, so do not treat these as exhaustive event-by-event captures. The output review statuses and exact-text preservation checks above were also checked directly in those response files.

## Records

- Case 3 TRACE: abb84b373fdd402e873e552ac17e23e8.
- Case 7 TRACE: a4c88fd4a8eb4866b00ca285d84803ac.
- Raw responses: case-03.json and case-07.json.
- Run settings/code hash: manifest.json.
- Run summaries: summary.json.
- Detailed capture: traces.sqlite3 (partial, as noted above).

Earlier baseline files and evidence holds remain unchanged. The Google Docs workbook was not edited during this retest.
