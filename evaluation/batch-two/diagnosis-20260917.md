# IRIS second batch diagnosis

## Summary

Reviewed September 17, 2026 against `test_batch_two.docx`, the saved local TRACE
records, and the current backend code. The document contains sixteen requests.
The first-batch Padilla quotation report was also checked against its saved run.
This was a diagnosis of existing runs, not a fresh sixteen-case service retest.
The source DOCX was not edited. No production pipeline or verdict rules were changed.
The approved nickname limitation was added to the backend calibration notes.

The main problems are routing, loss of attribution context, and accepting a
generic component from a different event. Not every failure is a search failure.
In particular, the missing ABS-CBN evidence for request 2 was actually retrieved
and extracted; the attribution-name gate rejected it afterward.

User-reported successes remain observations, not independently scored accuracy
passes. The proposed answers in the document are review hypotheses, not rules
that should be hard-coded into the verifier.

## First batch request 5

TRACE: `ad191708788a408cbc3d1334898316b0` (HTTP 200, three claims).

1. Translation preserved both reported quotations.
2. The Content Profiler retained both and marked them eligible.
3. The extraction coverage reviewer merged the constitutional quote into a shorter
   attributed claim about an impeachable officer. It did not omit that topic
   entirely, but lost the explicit Article 11, Section 2 detail.
4. It excluded the question to Gatchalian and the later quotation. The recorded
   reasons were that asking a question is not a factual claim and that the quote
   contains questions and opinions.
5. Those exclusions occurred before evidence retrieval for that assertion.

The distinction IRIS missed is between the content of a question and the factual
report that somebody asked it. Whether Padilla asked for the Senate's position
is checkable as attribution. It does not require treating his emotional language
or political opinion as independently true.

Expected extraction should account for the constitutional attribution with its
specific citation, the reported impeachment-mechanism statement, the request for
the Senate's position with the complete attributed utterance, and the bail event.
Repeated narrative and quotation versions should enrich one assertion rather
than create duplicates. The exact count can vary with documented granularity;
the requirements are coverage and preservation, not a fixed quota.

Recommended fix: require source-linked coverage of reported speech acts, including
questions and opinions attributed as actually spoken. Preserve a full source
quotation and its qualifiers when merging. Do not apply this rule to anticipated,
imagined or satirical speech, as request 13 illustrates.

## Second batch findings

| Request | Finding | Stage and expected handling |
|---|---|---|
| 1 | Confirmed attribution metadata defect in one run | TRACE `43ffed6000b44606957e33c1fb6897c4` put the truncated reporter credit `Zyann Ambrosi` into the required source field. Another run, `2e89a9b745524d67bb3863f49f704d66`, left it null. A reporter credit must not become an interview/source condition unless the assertion requires it. Grounding by substring alone does not establish the field's correct role. |
| 2 | Confirmed false rejection of relevant evidence | TRACE `65c9640cd64746d4bbb23a8a8ef678de` retrieved the exact ABS-CBN link and extracted 284 words, with full quality. Its body uses `Malacanang`; the claim uses `Malacañang`. The speaker gate reported `speaker` missing. This is ordinary name normalization, not the newly excluded nickname problem. The accepted fallback components also need review because 'Malacañang said' alone is not a complete assertion. |
| 3 | Reported success; not independently accepted | TRACE `adcb8b846fe14973b948e2385889b596` completed with two claims. Retain it as a positive regression case, but confirm the passages support both reported actions before marking accuracy passed. |
| 4 | Confirmed external-service failure with incomplete TRACE visibility | Four recorded ICC attempts returned HTTP 503. Their saved component-review artifacts report `RateLimitError`, `review_rate_limited`, at `entailment_check`. Event captures are marked partial. Preserve terminal errors separately from the event capture budget so the diagnostic view cannot hide the reason. This is not a factual Not Found result. |
| 5 | Confirmed cross-event support error | In TRACE `11530398d3ef40c6815f036fabd93f80`, the reviewer rejected both the victim relationship and online-taunt motive, yet accepted the isolated component 'arrested' from the unrelated shooting. A dependent detail cannot inherit support after the source is identified as a different incident. The two ignored segments were the sensitivity warning and comment instruction, not two missing crime facts. |
| 6 | Confirmed routing error | TRACE `7bb61e21b74f47068bc6e43228fcaf8c` passed an opinion/prediction about motives to extraction. The two components were the predicted decision based on bias and the prevailing public mood. These are not two observed factual events. Stop ordinary verification for this commentary; a future official decision or announced procedure would be a different kind of claim. |
| 7 | Confirmed over-extraction of generic advocacy | TRACE `40484e95fd85427288f7e01abc5550a4` extracted broad vote/education, work, healthcare and laws statements from a civic appeal. For this input and IRIS's news-verification scope, these should not become event-verification requests without a concrete asserted outcome. The DOCX repeats the work statement as claim 3, but TRACE shows healthcare there; do not score that transcription as a confirmed backend duplicate. |
| 8 | Approved scope limitation plus separate attribution issue | TRACE `fc9b9a267e944e83a74cd5fe3d868c2c` kept 'Solar boy' rather than inventing a name, but emitted 'projects ... are said to be okay' as an attributed statement with no speaker. The unresolved subject, evaluative wording and anonymous attribution are distinct issues. Explain the identity limitation rather than implying a named speaker was identified and disproved. |
| 9 | No extraction is plausible; explanation needs review | TRACE `e510dea09852408da0d385dcdbe6d3a2` returned no claims for a vague/rhetorical post. Do not invent a concrete mugshot event or assume a person's identity from this alone. The recorded 'No extracted claims yet' wording sounds like a diagnostic placeholder, not an explanation of why the content was skipped. Check its frontend/TRACE provenance before changing the API. |
| 10 | Mixed assertions need separate review | TRACE `0bca685524f44da4ac4cf6eacc989046` completed with one claim. A speculation about returning home and a reported imprisonment event require different handling. A partial verdict is not enough to establish that the correct part was extracted and supported. |
| 11 | Plausible mixed-content handling; evidence still needs checking | TRACE `f974412e5d344e88a705874315f4d2fe` completed with one claim. The BIR/VAT action can be checked separately from congratulations and political appraisal. The reported Verified result should remain a positive candidate, not an automatic benchmark answer. |
| 12 | Several distinct evidence checks, plus a compound claim | TRACE `c9baafbe081546e2b6912a6f65d56b43` retained seven claims. The final claim already had separate components for 'twice impeached' and use of the political-persecution expression; both were marked unsupported. The next check is retrieved evidence for the historical component, not simply forcing an extraction split or awarding Partial from outside knowledge. Recorded short speaker-only components and broken quotation marks also warrant review. |
| 13 | Confirmed routing and context-loss defects | TRACE `e896ffdbe66c4fd8bb99fe58373960fe` shows the profiler keeping the first anticipated question and excluding the second and third as unclear. The extractor then called the expectation a checkable attribution. This is not merely visual truncation: the later questions were removed before extraction. Preserve the hypothetical/satirical framing; do not verify that Robin actually asked them. |
| 14 | Reported success; retain as a regression | TRACE `4ef5f9af349944858d36e449df69ac5b` completed with one claim. Attribution evidence must confirm that Carpio said it. That is separate from giving an independent legal ruling on the statement's correctness. |
| 15 | Compound-event specificity and retrieval gap | TRACE `16e45425882848a48c4d0c5487e479d9` reviewed the schedule as one component. The final check rejected it because selected passages lacked 2026. The supplied ABS-CBN event link was not among the saved extracted articles for this run. Confirm that candidate's full body, event identity and date before deciding Partial. A different date must be reported as a mismatch, not silently treated as missing detail; a different tour/year must not be reused as the same event. |
| 16 | Confirmed lack of a scope-based stop on this input | TRACE `79740d5ef657430d857e9ada9e01590f` extracted three NASA claims. Checkability and Philippine relevance are separate: under the stated scope rule, no Philippine anchor should route this input to out of scope, not imply that a factual astronomy claim is invalid or false. This diagnosis does not independently validate the astronomy assertions. |

## Evidence notes and corrections

- Request 2's saved article is [the supplied ABS-CBN report](https://www.abs-cbn.com/news/nation/2026/9/16/palace-marcos-jr-won-t-interfere-with-impeachment-conviction-threshold-issue-1610).
  The saved extraction contains the spokesperson's explanation of leaving the
  threshold issue to the Senate. The observed rejection happened after extraction.
- The [Philstar Taytay article](https://www.philstar.com/nation/2026/01/19/2501879/man-arrested-taytay-livestream-shooting)
  describes the victim as a vendor and the suspect as the store owner's former
  partner; it does not establish that the victim was the ex's new partner or that
  online taunts caused the shooting. This is more precise than assuming the
  victim was the suspect's ex. A later saved rerun cited GMA rather than this
  Philstar URL, so do not conflate the two runs; the cross-event defect remains.
- The [ABS-CBN fan-meet link](https://www.abs-cbn.com/entertainment/showbiz/events/2026/6/9/byeon-woo-seok-returning-to-ph-for-october-fan-meet-1729)
  is a candidate reference. The web reader exposed its headline/metadata but not
  sufficient body text to independently settle the claimed date in this review.

## Nickname limitation

Accepted: IRIS does not maintain comprehensive mappings for emergent, informal,
satirical or rapidly changing nicknames and epithets. An unresolved nickname may
cause Not Found because search cannot identify the intended subject. That is not
evidence that the underlying assertion is false.

Ordinary name spelling and accents, known abbreviations, and identity supplied
explicitly by the input remain separate. The limitation must not excuse the
Malacañang/Malacanang rejection or create permission to guess a formal identity.
The limitation is now documented; a dedicated runtime explanation is not yet
implemented by this documentation change.

## Category guidance

Keep the six user categories as dataset tags, but also record two separate fields:
whether the input is checkable and whether it is within IRIS's Philippine scope.
The document's introduction lists `unclear` whereas request 16 uses `Invalid`;
these should not be silently treated as synonyms.

- Reserve invalid for empty, unsupported or unusable input.
- Use out of scope as a separate scope outcome for otherwise meaningful content.
- A quote can be checkable as attribution even when its content is an opinion.
- An imagined quote is not a report that the speaker actually said it.
- A factual news post can contain a non-checkable headline, reaction or call to action.
- A mismatch and an absence of evidence are different reasons, even when the
  current verdict vocabulary groups them under the same label.
- Not every statement without a named person/date is uncheckable. Apply the
  generic-advocacy judgment to the actual context, not as a blanket grammar rule.

## Recommended repair order

Update: priority 1 has now been implemented and checked with a live saved-evidence
negative case and same-incident partial-support control. See
[Cross-event evidence fix](cross-event-fix.md) for changes, results, and limits.
Priority 2 has subsequently been implemented with quotation-scope and coverage
guards. See [Quotation handling](quotation-fix.md) for the live screening/extraction
replays and remaining limits. Priority 3's accent/punctuation matching and
reporter-credit fixes have now passed local saved-case tests and the two-case live
evidence-review replay; the replay also exposed a residual intermediate event
decision and citation-precision issue, retained in the report. See
[Attribution matching](attribution-fix.md) for retest scope and limitations.
Priorities 4-6 remain separate work.

1. Prevent cross-event partial positives. Evaluate event identity before counting
   dependent components such as an arrest or date as supporting evidence.
2. Fix reported-versus-imagined speech routing and coverage together. Preserve
   genuine utterances without converting satirical expectations into real speech.
3. Normalize ordinary identity variants and distinguish reporter credits from
   required attribution. Preserve speaker and valid-link requirements.
4. Make terminal provider errors visible even when TRACE's event budget is exhausted.
5. Tighten opinion/prediction, generic advocacy, and Philippine-scope routing.
6. Improve component explanations, then review date/quantity mismatches against
   explicit reference evidence and rerun unchanged baseline inputs.

The first three repairs can be tested with saved inputs and evidence pairs before
repeating expensive full live requests. Keep this second batch as a separate set
from the original ten cases. Do not assign an accuracy percentage until expected
outcomes and source references have been adjudicated consistently.

## Diagnostic references

Original documents: `C:/Users/aquarius12/Downloads/test_batch_two.docx`.
Saved diagnostics: `iris-backend/.iris-trace/traces.sqlite3` in the workspace.
TRACE may prune old runs after its retention period, and several captures are
partial; the trace references above do not promise every stage is retained.

The four ICC error traces checked were:
`a68d967158d1463c9c7fcfe1e7906b8c`, `1d83e40d054745728ddb96d4292ddc65`,
`8d1cb74d34114036a11adde9e066b186`, and `63e6edbecb1a4ea1bc524224b608e2cf`.
All saved the same rate-limit reason in component-review artifacts. The current
TRACE implementation stops storing ordinary events above a 1 MiB per-trace
budget, which explains why a partial event view can end before the final error.
