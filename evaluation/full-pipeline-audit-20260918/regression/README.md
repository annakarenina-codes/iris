# IRIS Regression Checks

## What Is Ready

The 34 saved cases, their inputs, expected behavior, reference IDs and original results already exist in the parent assessment. This folder adds executable **offline output checks**, with all 34 cases included in the generated checklist.

These checks do not run the backend, contact OpenAI or Brave, or prove that the backend is fixed. They examine recorded outputs. The historical 13 passed / 18 failed / 3 cannot yet judge assessment remains unchanged.

## Three Different Kinds of Test

| Kind | Purpose | Current coverage |
|---|---|---|
| Checker self-tests | Confirm our checker recognizes known bad captures and does not silently accept missing data | Seven tests, including eight saved defect examples |
| Offline output checks | Detect specific regressions in saved baseline or future run files | All 34 input identities and completion outcomes; eight targeted defect patterns; signature-change alerts for the 13 previously passing cases |
| Evidence-quality review | Check actual meaning, source identity, completeness, contradictions and relevant citations | Still required for every new run; use the existing assessment expectations |

An unchanged count or verdict is not proof of accuracy. A changed wording or decomposition may need review rather than indicate a regression. A missing matching assertion is flagged for review, never automatically passed.

## First Fix Acceptance Set

| Case | Required behavior | What the automated check can establish |
|---|---|---|
| B05 | No credit from another shooting's arrest | Flags credit to the saved detached arrest fragment; complete-event matching still requires evidence review |
| B12 | Preserve the environmental-causes assertion | Flags a detached causes component; wider extraction coverage still requires review |
| C02 | Accept the directly supported DICT/Zuckerberg assertion | Expects Verified for the matched assertion; inspect the new candidate pool if this fails |
| C03 | Accept the complete, directly supported Wintour quotation | Expects Verified for the matched quotation; does not validate every citation automatically |
| B15 | Preserve the explicit year evidence for the fan meeting | Expects the supported event to be Verified; the June article alone does not prove the year |
| C06 | Retain the explicitly named speaker | Flags null speaker metadata; does not certify alias resolution |
| B07 / B16 | Stop generic advocacy / out-of-scope verification | Flags delivered factual claims; inspect the explanation and whether search ran separately |
| A03 / A05 | Complete successfully or expose a technical failure, never invent a verdict | Separates availability failure from correct no-verdict error handling |

Other known failures, including A02 attribution, A07 duplicates, C04 retrieval and C08 denial handling, remain explicitly recorded in the 34-case checklist. They do not yet have dedicated automatic semantic assertions. Add those assertions with their respective fixes; do not treat the absence of an automatic failure as a case pass.

## Baseline Check

From the repository root:

```powershell
python -m unittest discover -s evaluation/full-pipeline-audit-20260918/regression -p test_*.py -v
python evaluation/full-pipeline-audit-20260918/regression/check_results.py
```

The second command intentionally exits with code 1 on the unchanged baseline: **10 checks fail**, covering eight targeted defects and two incomplete requests. The checker's tests should pass because detecting those known defects is correct behavior.

Exit codes: 1 means an automated failure; 2 means unresolved/missing captures or a change requiring review without an automated failure; 0 means only that the narrow automated checks passed. Semantic review is still required.

[Read the baseline check results](baseline-check/RESULTS.md). The JSON alongside it contains every check, expected behavior, exact input hash and reference ID for all 34 cases. The 81 passing checks are mostly integrity/completion checks, NOT 81 accurate verdicts.

## After a Backend Fix

1. Run the focused existing backend tests and the checker self-tests.
2. Capture new backend results in a separate directory, using the exact saved inputs and the same saved-run JSON envelope as current-baseline. Record source version, settings, TRACE ID and cache policy. Never overwrite the original baseline.
3. Evaluate those captures with the command below. Missing cases remain review flags.
4. Inspect supporting passages, event context and coverage. A new evidence pool can explain a changed result; this is not a fixed-evidence replay.
5. Rerun all 34 cases and review the 13 passing cases before declaring the combined changes successful. Keep the three unresolved cases unresolved until evidence permits judgment.

```powershell
python evaluation/full-pipeline-audit-20260918/regression/check_results.py --results-dir evaluation/next-retest --output-dir evaluation/next-retest/checks
```

The old run_baseline.py deliberately refuses changed production hashes. Do not disable that protection to overwrite the baseline. A post-fix live capture runner must use a new run directory/version; it has not been added or executed in this preparation step.

## Safety Boundaries

- No production logic changes in this preparation.
- No fresh external-service tests or charges from these commands.
- A rate-limit error must not become Verified, Partially Verified or Not Found.
- Known articles supplied manually do not count as automatic search success.
- Passing a narrow check does not replace evidence-quality review or establish real-world accuracy.
