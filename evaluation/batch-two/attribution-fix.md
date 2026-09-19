# Attribution matching: diagnosis and repair

Date: 2026-09-18
Backend cache version: `week7-attribution-matching-v15`

## What was wrong

1. In batch-two request 2, the claim named **Malacañang**, but the saved ABS-CBN
   article used **Malacanang**. The old ASCII token comparison rejected the speaker
   before the final evidence reviewer could assess this article.
2. In request 1, `/via Zyann Ambrosi` was treated as a required source for the
   statement attributed to Melvin Matibag. That is a contributor credit, not a
   condition independent reporting must repeat. Another saved extraction left it
   null, demonstrating the inconsistency.
3. The old speaker fallback could accept the last name token alone, including
   `Jr`, while phrase matching could accept substrings or disconnected name words.
   These shortcuts could also admit the wrong person.

## Changes

- Normalize ordinary accents, case, punctuation and dotted initialisms for
  comparison, preserving the submitted assertion and original display spelling.
- Require contiguous whole-token names. Do not infer identity from a shared
  surname, suffix, nickname, or partial spelling.
- Remove explicit credit-only metadata requirements. Preserve real speakers,
  explicit interview outlets/programs/dates, and negation in the assertion.
- Add instructions to extraction and coverage review to prevent credit invention
  before deterministic grounding runs.
- Record per-field grounding reasons and evidence anchor checks for diagnosis.
- Advance the cache version so earlier verdicts do not bypass the new rules.
- Keep statement review, cross-event protection and valid-link checks unchanged.

## Local results

| Check | Outcome | What this establishes |
| --- | --- | --- |
| Saved Malacañang/ABS-CBN pair | Passed | The 284-word article passes speaker matching and reaches candidate review. |
| Saved NBI reporter credit | Passed | Credit-only source removed; Matibag remains the required speaker. |
| Cosmetic-surgery article without Matibag's name | Passed | It is still rejected as proof that Matibag made the statement. |
| Different people with a shared surname/suffix | Passed | They cannot satisfy a supplied full speaker name. |
| Speaker present, different statement | Passed | Candidate admission alone is not statement confirmation. |
| Full backend regression suite | Passed | 217 passed, 1 existing skip, 52 subtests passed. |

The local replay admitted 8 candidates for the Matibag claim and 7 for the
Malacañang claim. These counts mean eligible for review, not supporting sources.
Several saved Matibag articles concern other investigations; their presence must
not establish this cosmetic-surgery investigation attribution.

## Live review

The user-approved live OpenAI review completed successfully for both cases, using
saved claims and article bodies. There was no fresh translation, screening,
extraction, search, URL fetch, or UI run. Results are specific to these snapshots.

| Case | Live outcome | Evidence and interpretation |
| --- | --- | --- |
| Malacañang | Verified | Three components supported. The known ABS-CBN conviction-threshold article appears in supporting URLs, along with a broader Philstar article. The accent mismatch no longer excludes the relevant ABS-CBN evidence. |
| Matibag / reporter credit | Not Found | Zero of one component supported, no supporting URLs. Removing the incidental reporter condition did not turn other investigations into final evidence for this death investigation. This is not a finding that the claim is false. |

Live traces: `15bac26e98824e09920198743f40a1e6` (Malacañang) and
`15dcc57ee24e4c8aa351f4d0c12e8fba` (Matibag). Full results, passage citations,
checks and per-article admission decisions are in `attribution-live-result.json`.

### Remaining reviewer weaknesses observed

- In the Matibag replay, the intermediate event-identity reviewer marked the
  Taguig flood-control investigation as matched despite recognizing it was not
  the cosmetic-surgery death investigation in the submitted context. The final
  entailment reviewer caught this and removed all support. The final negative
  control passed, but this is NOT a pass for every intermediate event decision.
- The Malacañang review also included a broader Philstar non-interference passage.
  It does not independently specify the conviction threshold. ABS-CBN supplies
  that detail. Do not describe every returned link as individually proving every
  component; citation precision still needs calibration.

These observations are retained for the next focused evidence-review calibration;
this attribution repair does not change the event or entailment reviewers.

## Reproducible records

- Fixtures: `iris-backend/tests/fixtures/attribution_cases.json`, mechanically
  exported from saved TRACE artifacts, including full extracted text.
- Original traces: `43ffed6000b44606957e33c1fb6897c4` (reporter credit) and
  `65c9640cd64746d4bbb23a8a8ef678de` (diacritic).
- Tests: `iris-backend/tests/test_attribution_integrity.py`.
- Suite output: `evaluation/batch-two/attribution-tests.xml`.
- Local replay: `evaluation/batch-two/attribution-replay-result.json`.
- Live replay: `evaluation/batch-two/attribution-live-result.json`.
- Replay script: `evaluation/batch-two/replay_attribution.py`; no flag is local-only,
  `--live` sends the saved cases and admitted article bodies to configured OpenAI.
- Replay traces: `evaluation/batch-two/attribution-traces.sqlite3`.

## Limits and next action

This does not resolve informal nicknames, prove all attribution cases, or repair
missing retrieval. A surname-only article can still be insufficient for a full-name
claim. Explicit credit detection is bounded; unusual layouts may need additional
labeled examples. No accuracy percentage is inferred from these two repairs.

Restart the backend before retesting through either frontend. No extension or
Android rebuild is needed for this backend-only change.
