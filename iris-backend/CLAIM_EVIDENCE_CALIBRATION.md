# Claim coverage and passage matching

## Scope

The `week7-source-review-repair-v16` cache version adds publisher-wide ABS-CBN/GMA
search, article-URL filtering, primary-body extraction isolation, and consistent
source/passage identifiers. It retains v15 typography-aware attribution matching
and contributor-credit grounding, v14 quotation-scope/coverage guards, and the
shared source/incident identity gate introduced in v13.
Previously saved verdicts are not reused under this version.
This is an accuracy change, not a latency optimization.

## September 18 source and review repairs

- ABS-CBN and GMA queries cover their whole domains, including entertainment,
  lifestyle and sports, instead of restricting discovery to `/news`. Existing
  publisher labels remain unchanged for API compatibility. The source count is
  still VERA Files plus seven approved Philippine publishers.
- Brave returns up to five candidates per source; extraction remains capped at
  two per source. Search/category pages and unapproved publisher URLs are filtered
  before extraction and again before citation. VERA queries target `/articles`.
  URL-shape checks reject known non-article patterns; they are not proof that every
  accepted page is a valid, relevant article. Body and evidence validation still apply.
- Structured article extraction selects the primary body matching the page title,
  rather than combining embedded related articles. HTML inside `articleBody` is
  parsed as text, and repeated paragraphs are deduplicated. Existing short-text
  extraction fallback and `thin` quality labeling remain in effect.
- Event review uses source IDs in article order, includes each passage's owning
  source ID, and constrains each source's response to its own passage IDs. The
  validator still rejects cross-source passage references; it has not been relaxed.
- Political warnings recognize office abbreviations and can inherit an explicitly
  identified attributed speaker's office from post context. Other claims do not
  automatically inherit the entire post's political warning.
- OCR region filtering rejects narrowly recognized social-interface labels/counts.
  It does not rewrite the claim or discard uncertain alphabetic words such as
  negation. Raw extraction remains available for diagnosis. A new real-image
  regression capture is still needed for the latest noisy-OCR report.

Fresh, cache-bypassed seven-post retests, original failure reproductions and
remaining retrieval/context gaps are documented in
[`../evaluation/reported-issues-20260918/diagnosis.md`](../evaluation/reported-issues-20260918/diagnosis.md).
Completion of a request is not automatically an accuracy pass.

## Attribution matching

- Attribution grounding and evidence anchors share Unicode normalization: accents,
  case, punctuation and dotted initialisms are normalized for comparison only.
  Submitted assertions and displayed names are not rewritten by this matching step.
- Matches require contiguous whole tokens. A truncated name, scattered name words,
  or another person's shared surname/suffix is no longer sufficient to match a
  supplied full speaker name. A missing speaker fails the attribution gate.
- Explicit name-like `/via`, `| via`, byline and photo-credit lines are excluded
  from metadata grounding. Credit-only speaker/source fields become null. Names
  independently used as actual speakers or sources in the prose remain eligible.
  Extraction and coverage prompts also distinguish credits from statement attribution.
- `attribution_integrity` records removed fields, per-field reasons (`grounded`,
  `absent`, `credit_only`, `not_in_input`) and incidental credits. The evidence
  gate records `anchor_checks` for speaker/source/program/date in TRACE and audit output.
- Evidence anchors are checked against extracted article body text, not URLs/titles.
  Passing this gate only admits candidates: mandatory component, event-identity and
  passage-entailment reviews still decide whether the actual assertion is supported.
  The existing valid-link requirement is unchanged.
- This is not general entity resolution. Unresolved nicknames, semantic aliases,
  name omissions and spelling errors are not automatically repaired. An article
  naming only a surname may conservatively fail when the claim names a full speaker.
  Credit detection is deliberately bounded to explicit, name-like credit lines.

Saved-case fixtures and replay results are described in
[`../evaluation/batch-two/attribution-fix.md`](../evaluation/batch-two/attribution-fix.md).

## Extraction

- The profiler no longer silently stops at thirty sentences; extraction and
  finalization no longer silently stop at ten claims.
- A second extraction review inventories every profiler-approved source segment.
  It merges repeated descriptions of the same assertion, separates independently
  checkable actions, and separates evaluative wording from factual clauses.
- The coverage ledger links each source segment to output claim indexes, or
  records why the segment was excluded. Original source sentences are attached
  directly using validated IDs; the model does not regenerate source quotations.
  Missing ledger entries, invalid indexes and incomplete API responses fail
  validation. This prevents Unicode/quotation regeneration errors without
  relaxing the requirement for provenance in the submitted text.
- Source passages are provenance from the submitted post, NOT supporting evidence.
- Local attribution heuristics and the longest fallback list no longer overwrite
  a successful reviewed inventory. If extraction fails, the existing local
  fallback remains explicitly labeled in the extraction status and method; it
  has not passed the model-assisted coverage audit.
- Exact duplicate detection uses the complete assertion rather than the first
  eighteen non-stopwords. It retains negation, dates and numbers, and distinguishes
  different speakers. Semantic merging remains the coverage review's task.
- An indexed consolidation plan merges same-incident descriptions and splits
  independent actions. Every input claim must be accounted for exactly once;
  numeric literals and listed uncertainty/negation markers cannot disappear.
  Speaker-attribution checks cannot be merged with underlying event assertions.
- An invalid consolidation plan is discarded without discarding the validated
  coverage inventory. `grouping_status: not_applied` and `grouping_error` record
  this degraded result; it is not a successful duplicate-removal audit.
- A single wholly checkable assertion that was neither split nor partly excluded
  is restored from the original text, preventing a shortened summary from silently
  dropping its final rationale. Explicit fact-check headlines remain an exception:
  their embedded verdict is not restored as the proposition to be verified.

The new coverage-review step defaults to the pinned `gpt-4.1-2025-04-14` model.
`IRIS_CLAIM_REVIEW_MODEL` overrides this step alone. The independent final
entailment check and component partitioning also default to this snapshot,
separately configurable through `IRIS_EVIDENCE_REVIEW_MODEL`. The draft extractor
and initial evidence assessment retain `OPENAI_MODEL`; no global setting was changed.
This is a deliberate quality-first choice after the smaller reviewer retained
evaluative wording and redundant incident descriptions in the saved-case replay.
It adds API usage and must be evaluated, not assumed to improve every case.
GPT-4.1 supports the existing Chat Completions interface and structured outputs;
see the [official model documentation](https://developers.openai.com/api/docs/models/gpt-4.1).

## Quotation handling

- Screening and extraction share explicit speech-framing rules. Reported questions,
  opinions, recommendations and hypothetical comparisons remain checkable as
  attribution, not as independently true assertions inside the quotation.
- Explicitly imagined/anticipated speech is not converted into an actual utterance.
  Consecutive quote-only segments inherit that framing; independent prose or a
  newly attributed speaker resets it. This is bounded English/Filipino pattern
  handling plus model instructions, not a general-purpose satire detector.
- Narrative speech reports remain covered even without quotation marks. Repeated
  descriptions link to their enriched claim, while distinct factual events remain
  eligible too. Speech coverage supplements ordinary factual extraction.
- Coverage validation requires reported direct utterances in the displayed and
  normalized assertion, allowing punctuation/case normalization but not deleted
  words, numbers or negation. Original source passages remain attached separately.
  Consolidation that shortens a protected utterance is rejected, retaining the
  pre-consolidation inventory. Quoted titles such as a named law are distinguished
  from a direct utterance.
- Parsing no longer rewrites every attribution as "speaker said"; it preserves the
  reviewed reporting frame, including questions and denials. A validated empty
  inventory does not resurrect excluded content through a local fallback.
- Coverage has one bounded repair attempt. TRACE captures `claims.coverage_ai`
  responses and `claims.speech_coverage_retry` reasons. If a direct reported quote
  cannot be reviewed safely, missing configuration or review failure raises a
  quotation extraction error instead of using guessed local attribution. HTTP 503
  returns `quotation_extraction_failed`, a null verdict, no evidence sources, and
  `failed_stage: claim_extraction`. Ordinary non-quotation fallback is unchanged.

Live screening/extraction replays used saved translations, not fresh translation
or evidence search. The final Padilla replay retained four claims with both full
quotations, Article 11/Section 2, the impeachment-mechanism statement and the bail
event. The anticipated-question post stopped before extraction. These are routing
and extraction passes, NOT proof of the posts' truth or final verdict accuracy.
See `evaluation/batch-two/quotation-fix.md` for results and limits.

## Evidence

Every claim with a successful search now goes through component review, not only
attributed statements. Semantic scores and the existing RAG fallback remain
diagnostic inputs; they cannot bypass the final passage review.

1. Partition the exact assertion using internal token boundaries. The application
   appends the final token boundary, so the model cannot drop the final clause.
   A possessive modifier cannot be separated from its object. The stronger model
   is used here because the smaller model split verbs from objects in live tests.
2. Propose support for each component from retrieved, approved-source articles.
   The model selects numbered source passages; original text and URLs are attached
   by the application, not generated by the model.
3. Check mechanically that every quoted passage occurs in its supplied article.
4. Group components by the subject/incident they refer to, including unsupported
   components. Dependent fragments such as "arrested" inherit the incident, not
   an independent generic meaning. Review each cited source once per group as
   matched, mismatched, or uncertain. Both mismatched and uncertain sources lose
   citation credit for every component in that group. Require actual source
   passages for a match; validate source IDs, passage provenance, and complete,
   non-overlapping component membership. Independent events can have different
   decisions for the same article. Missing a motive alone does not disqualify an
   otherwise established event. The identity review uses IRIS_EVIDENCE_REVIEW_MODEL.
5. Independently review the REMAINING proposed passages for the same subject/event, the actual
   assertion, and preserved qualifiers. Record the reason and accepted passage IDs.
   The response schema restricts each component to its actual passage IDs, and
   local validation still rejects missing/duplicate components or invalid references.
   Both review responses use fixed component-ID object keys to prevent missing
   or repeated component entries. A selected passage set missing an asserted
   four-digit year cannot support that component, even if the model approves it.
6. Derive Verified from all supported components, Partially Verified from some,
   and Not Found from none. Publish only the accepted source links.

Existing speaker/source/program/date gates and valid-link requirements remain.
The submitted post is passed as explicitly unverified context to resolve pronouns
and event identity, never as proof. Cache keys include that context so identical
generic claims about different incidents do not share a verdict.

For referential incident claims, a bounded English-language identity guard resolves
a unique explicitly named shooting/killing victim from the post. It adds that name
to the search query and requires the victim's surname in eligible article text.
An unrelated investigation cannot pass that guard merely because it mentions CCTV.
This is a necessary condition, not proof of the same event. Multiple/unresolved
victim identities are not guessed; the model must still assess them. Standalone
claims such as a tribunal ruling do not inherit the victim requirement. Reasons
are recorded in `incident_evidence_audit` and TRACE's `evidence.incident_gate`.

Review failures still produce HTTP 503 with a null verdict and no evidence links.
They must not silently reuse a positive fallback verdict or write it to cache.
Rejection reasons are retained in `component_review.entailment_checks`,
`component_review.event_identity_checks`, per-component `event_rejections`, and
TRACE's `component.event_identity_checked` event. Identity-review failures retain
`failed_stage: event_identity_check`; they do not invent a Not Found verdict.
Provider rate limits have a distinct `review_rate_limited` reason code. Each
component-review API call may retry once after a transient rate limit, using a
numeric provider wait hint where available (maximum 60 seconds; default 5).
Quota exhaustion, oversized requests and waits exceeding that bound are not
retried. A second failure still returns a processing error with no factual
verdict. This does not remove provider limits or retry invalid review output.
TRACE records the failed stage and bounded retry delay without raw provider error
messages. Some token-limit header fields are redacted by TRACE's existing sanitizer.

## Limits and calibration

### Informal nicknames and epithets

Approved scope clarification, September 17, 2026: IRIS is not designed to resolve
informal, satirical or rapidly evolving nicknames and epithets for public figures
into formal names for search. These user-generated labels are inconsistent and
unbounded; maintaining comprehensive coverage is outside the current scope.
When the only subject identifier is an unresolved nickname, Not Found may reflect
an unmatched search term rather than an absence of relevant evidence. This is an
entity-resolution limitation, not a judgment that the underlying assertion is false.

This does not exclude ordinary spelling/diacritic variants, supported abbreviations,
or identity explicitly supplied by the same post. IRIS must not guess a formal
name or fabricate attribution to compensate. An unresolved subject should be
explained separately from a completed evidence search with no support. This
section records the scope policy; it does not claim that a dedicated runtime
nickname detector or user-facing diagnostic has been implemented.

The coverage ledger demonstrates accounted-for source segments, not guaranteed
semantic completeness. Verbatim quotation checks establish provenance, not truth.
Event grouping/identity and independent entailment are still LLM judgments and
can be wrong; mechanical validation ensures consistent application of the
decisions and real citations, not guaranteed factual accuracy.
Manual review and held-out cases remain necessary, especially for partial support,
ambiguous attribution, chronology and related-but-different events.
The v12 Padilla/Wamil replay still over-credited the plural funds rationale,
despite retaining the full text and returning Partially Verified overall. This
specific component is NOT an accepted calibration result. See the review report.

These added reviews may increase runtime, especially for long posts with many
claims. Provider calls have bounded timeouts; total request duration can exceed a
frontend's timeout because multiple claims are processed. Do not interpret the
fraction of supported components as a calibrated probability or an overall
accuracy score.

Fresh authorized live runs of saved cases 3 and 7 are recorded separately in
`evaluation/trace-ten-cases/coverage-entailment-v10-live/` at the workspace root.
That full run predates the final boundary refinement: case 3 was interrupted by
OpenAI HTTP 429; case 7 completed. The final v11/v12 checks used saved articles,
not fresh search or a complete endpoint rerun. Their directories are
`coverage-entailment-v11-boundaries/` and `coverage-entailment-v12-padilla/`.
Earlier experiments remain in `coverage-entailment-retest/` (initial live attempt,
which encountered Brave HTTP 402) and `coverage-entailment-replay/` (saved-article
replay, not fresh retrieval). Intermediate v5-v9 runs include failed experiments;
their directory names do not indicate acceptance. Do not mix those outcomes.
The ten-case workbook and source approvals are not automatically changed by this
implementation. Use the run's review report before marking accuracy items passed.
The current report is `evaluation/trace-ten-cases/claim-evidence-review.md`.
