# Cross-event evidence fix

## What went wrong

Second-batch request 5 concerned a man shooting his ex's new partner after online
taunts. Saved TRACE `11530398d3ef40c6815f036fabd93f80` had rejected the victim
relationship and motive in a retrieved GMA article but still credited its arrest
passage. That produced Partially Verified using evidence whose incident identity
had not been established. An arrest in another story is not partial confirmation
of this story.

The saved article describes a victim employed by the suspect's former partner,
not an established new romantic partner. This report does not adopt the earlier
reviewer's inaccurate description of the victim as the suspect's ex-girlfriend.

## Changes

- Added a shared identity review between proposed passage support and final
  entailment review. Every component is included in the grouping, even an
  unsupported component identifying the incident.
- An article receives one matched/mismatched/uncertain decision per incident
  group. Mismatched or uncertain sources lose credit across that group,
  including dependent fragments such as "arrested".
- Separate events within one article may receive different decisions. Rejecting
  one article does not blacklist a different, matching article.
- Identity and truth are separate: an established event can retain partial
  support even when its alleged motive or confession is unsupported/contradicted.
- The final assertion review runs only on the remaining citations. Matching an
  incident alone never establishes a factual component or overrides speaker,
  assertion, qualifier, or valid-link checks.
- Validate complete/non-overlapping component membership, real source IDs and
  verbatim passage provenance. Short identity fragments (for example a location
  split after an abbreviation) can accompany substantial evidence. This does
  not relax the existing minimum length for factual-support quotations.
- Provider/validation failures return a technical error with no verdict, not
  an invented Not Found. TRACE retains group decisions, citations, and rejection
  reasons. Rejection records are deduplicated per component/source.
- Cache version is `week7-event-identity-v13`. Old verdicts are bypassed, without
  deleting historical TRACE records. No frontend rebuild is required.

## Live saved-evidence results

| Test | Expected | Observed | Result |
|---|---|---|---|
| Original translated shooting claim with the saved unrelated GMA article | No component borrows support from that article | Not Found; 0/3 supported; no evidence link | Passed |
| Constructed control identifying the article's actual suspect/victim/date/location, plus an unsupported confession about online taunts | Keep the supported incident and arrest; reject the confession | Partially Verified; 2/3 supported; correct article retained | Passed |

The final paired replay took 20.63 seconds. This is not an end-to-end latency
benchmark. Negative replay TRACE: `a2199a0a74c8444084752b7dd7c868d7`.
Control TRACE: `9bd3bb24d2e34769bff151777623b3fa`.

These were live OpenAI component reviews using saved article text, not fresh
search, translation, extraction, or complete frontend/backend requests. The
control is constructed for calibration, not an additional original user case.
Not Found here means this evidence does not establish the claim; it does not
mean the original story is false or that no matching article exists elsewhere.

An earlier live control failed. TRACE identified a short-passage validation edge
case and a reviewer confusing an unsupported motive with a different incident.
Both were corrected before the final paired replay. Earlier attempts are retained
as timestamped JSON files, not silently counted as passes.

## Verification and remaining limits

Regression coverage includes the exact saved failure, uncertain identity, genuine
partial support, multiple independent events, mixed good/bad sources, malformed
output, invented source references, short identity fragments, timeouts, and
preservation of final assertion checks. See `cross-event-tests.xml` for the
full backend suite result and `cross-event-live-result.json` for the paired replay.
Final backend suite: **182 passed, 1 skipped, 40 subtests passed** in 39.48 seconds.
The skip is the existing manual full-post count placeholder, not a new skipped test.

Event grouping and identity are still model judgments, not guaranteed truth.
The extra bounded review can add latency. This fix does not claim to repair
quotation routing, informal nicknames, ordinary-name normalization, search recall,
or every second-batch case. Those remain separate calibration work.

Restart the backend before testing request 5 again. Review the new
`component_review.event_identity_checks` in TRACE and verify which incident each
accepted source actually describes. A fresh search can legitimately change the
verdict if it finds evidence for the correct event.
