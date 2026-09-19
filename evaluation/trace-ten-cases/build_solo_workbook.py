"""Adapt the existing review workbook for one human reviewer; preserve case evidence."""
import json
import re
from pathlib import Path

root = Path(__file__).parent
source = (root / 'IRIS_Beginner_Reference_Workbook.md').read_text(encoding='utf-8')
records = json.loads((root / 'observed_trace_records.json').read_text(encoding='utf-8'))

intro = '''# IRIS Solo Calibration Workbook

## Your next small step
Start with Case 10 and review its extraction and routing only. Read the input, decide whether the ten-person announcement and award description are checkable, and record your decision. You do not need to settle every source problem before testing this stage.

This workbook is designed for one person developing IRIS. You are the sole human reviewer and decision owner. AI can help prepare, compare and question the material, but it is not an independent human reviewer. A later self-check is optional and does not create independent reviewer agreement.

Solo Draft 0.2, redesigned on 12 September 2026. All ten original inputs, proposed targets, evidence assessments and fourteen source records are retained from the previous workbook. Source-access observations remain dated 11 September 2026; they were not reverified for this redesign. No backend change or fresh IRIS test was performed.

## The shortest useful workflow
1. Read one original input before reading IRIS outputs or AI suggestions. Write your own quick list of checkable statements.
2. Compare with the proposed extraction table. Mark Approve, Revise or Hold for the stage you are reviewing. Add one sentence explaining why.
3. For evidence or verdict review, open the listed source and inspect the actual passage. Record its source ID, paragraph or timestamp, important missing details and publication date.
4. Freeze only the approved claim IDs and stages, then run a controlled test. Leave everything else on Hold and report that limited scope honestly.

Suggested session: about 25 minutes, not a deadline for correctness. Spend roughly 5 minutes on wording, 15 minutes on evidence when needed, and 5 minutes recording decisions. If a source stays blocked or ambiguous after your timebox, record the blocker and move on. A timebox ends the session, not the search for truth.

## One decision log instead of multiple reviewers
| Review status | What you mean | Can this be scored? |
|---|---|---|
| Approve | I checked the proposed answer and accept it for the named stage and claim ID. | Yes, after recording the version and required evidence. |
| Revise | I recorded replacement wording, route or judgment and its reason. | Only after I explicitly approve the revised version. |
| Hold | A source, date, scope decision or meaning remains unresolved. | No for the unresolved stage; another approved stage can still be tested. |

These are workbook statuses, not IRIS verdicts. Approve does not mean Verified: you can approve an expected exclusion or a contradiction judgment. Evidence relationships such as Full or Partial describe passages; they are separate from your review status.

## Work queue
Suggested order is based on workload and useful coverage, not a prediction that the expected verdict will be positive. Keep all ten cases in the inventory. Do not present a selected easy subset as the accuracy of the entire batch.

| Order | Cases | First useful task |
|---|---|---|
| 1 | 10 | Approve extraction and routing; keep the later-source cutoff separate. |
| 2 | 4 and 9 | Check that factual celebrity and numerical statements are not discarded. Evidence and source-path issues may remain on Hold. |
| 3 | 2 and 7 | Review the hearing together to reuse source reading, but independently match passages to each statement and speaker. |
| 4 | 8 | Check attribution, complete context and the interview-date mismatch. |
| 5 | 3 | Resolve the later investigation updates before settling disputed incident details. Approve clear biography targets separately. |
| 6 | 5 and 6 | Resolve recipient, date, project scope and no-response wording. |
| 7 | 1 | Decide ambiguity and satire handling without adding context absent from the input. |

## What you fill in
Each case has one row per proposed target. Enter stage, Approve/Revise/Hold, and a short reason. For extraction, cite the original words and retain necessary names, dates and negation. For evidence/verification, include source ID, passage location, supported or missing components, and the proposed verdict. Put different stage decisions on separate lines or duplicate that row.

Record your name or initials and date once per case. The later self-check only needs attention for changed, disputed or high-risk judgments, plus a small preselected sample of straightforward decisions. Record which items you selected. This is a consistency check, not an independent review or an inter-reviewer reliability statistic.

## Faster assistance without handing over the answer key
Use AI for bounded tasks: suggest search phrases, prepare candidate claim lists, compare a source passage with one assertion, explain terminology, or calculate scores from your approved labels. You retain the final source inspection and approval. Do not have AI certify its own proposed answers or invent a passage when a page is unavailable.

Your ChatGPT Pro subscription does not change this evaluation rule. This workflow does not depend on a specific paid feature or promise a particular quota. Record the model name shown, date and assistance used. Hide IRIS results during the initial label draft where feasible; because these cases are already familiar, that reduces but does not remove bias.

Read a shared source once and refer to its source ID again, but review each claim-source relationship separately. Reuse approved labels across unchanged inputs; recheck them when evidence, the date cutoff, source policy or label definitions change. Keep a short change log rather than rewriting the full report after every test. Never treat repeated AI agreement as independent corroboration.

### Prompt for a first claim draft
Using only this original input, list independently checkable assertions, their exact input spans, the speaker if explicitly identified, and whether the target is a fact or a reported statement. Preserve negation, dates, quantities and uncertainty. Leave absent publisher attribution empty. Separate opinion and repeated framing. Do not see or infer IRIS results. These are proposals for my review, not approved labels.

### Prompt for one evidence comparison
Compare this claim with the supplied article passage. List each factual component and mark supported, contradicted, background only or unresolved. Quote only words present in the supplied passage and name the speaker. Check the publication date against my evaluation cutoff. Do not fill gaps from memory, a headline or topic similarity. Return a short table and tell me what I still need to inspect.

### Prompt after a controlled run
Compare these TRACE outputs with my frozen reference labels. Report matched, extra, duplicate and missed claim IDs, then routing, evidence and verdict disagreements separately. Preserve errors, cache flags and incomplete logs. Do not rewrite my reference labels to match IRIS. Flag uncertainty and calculate only metrics with approved labels and explicit denominators.

## When you can proceed
You can begin a scoped calibration cycle when you have approved the original inputs, claim IDs and rules for the stage being tested, recorded the reference version, and selected consistent test settings. Final-verdict testing additionally needs inspected evidence and an approved judgment for those IDs. There is no claim here that a fixed small number of examples proves overall accuracy.

Change one responsible stage at a time, retest affected cases, then run the approved regression subset. Include at least one different case type as a guard against unintended changes. Report how many of the ten cases were eligible for each metric and why others were held. Use separately selected unseen examples for later generalization testing.

## Method description for your thesis
This phase uses a single-reviewer, AI-assisted development evaluation. The researcher records and approves expected extraction, routing and evidence judgments, with targeted later self-checks. AI suggestions are not treated as independent labels or ground truth. Unresolved labels are documented and excluded only from the corresponding semantic metric, while technical failures remain in operational reporting. The ten known cases guide calibration and are not a held-out test set. Confirm final thesis evaluation requirements with the adviser; this workflow does not certify compliance with institutional requirements.
'''

# Keep the existing glossary, policy caveats and metric definitions.
reference = source.split('## Keyword reference and glossary', 1)[1].split('## Case 1 ', 1)[0]
reference = '## Keyword reference and glossary' + reference
reference = reference.replace('| Adjudication | Resolving reviewer disagreement with reasons and evidence. | Agree on whether one sentence has two independent claims. |',
                              '| Decision resolution | Settling your conflicting judgments with evidence and a written reason. | Keep uncertain labels on Hold; outside advice is optional. |')
reference = reference.replace('reviewer-approved', 'researcher-approved').replace('reviewers', 'you')

parts = [intro, reference]
for i in range(1, 11):
    body = source.split(f'## Case {i} ', 1)[1].split('\n## ', 1)[0]
    before, after = body.split('### Reviewer worksheet', 1)
    original_form, retest = after.split('### Retest record', 1)
    ids = list(dict.fromkeys(re.findall(r'\| (P\d\d-C\d\d) \|', before)))
    if i == 10 and 'P10-C02' not in ids:
        ids.append('P10-C02')
    form = ['### My decision log',
            'My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.',
            '| Claim or component ID | Stage and my status | My correction or evidence and reason |',
            '|---|---|---|']
    for ident in ids:
        form.append(f'| {ident} | Not reviewed | To fill in |')
    form += ['Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.',
             'Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.',
             'One next action for this case: __________. Blocker if held: __________.']
    parts += [f'## Case {i} ' + before, '\n\n'.join(form), '### Retest record' + retest]

register = source.split('## Source register', 1)[1].split('## Remaining review priorities', 1)[0]
register = register.replace('Reviewer confirmation and date: pending.', 'My source check and date: pending. Record body access, passage location and any changed content.')
parts += ['## Source register' + register]
priorities = source.split('## Remaining review priorities',1)[1].split('## Release checklist',1)[0]
priorities = priorities.replace('7. Assign two human reviewers and an adjudicator. No names or approvals have been invented.',
                                '7. Record your own name, decisions and dates. No second reviewer or outside sign-off is required for this solo development workflow; unresolved judgments stay on Hold.')
parts += ['## Remaining review priorities' + priorities,
'''## My release checklist
| Item | My entry |
|---|---|
| Approved reference version and date | Pending |
| Approved case and claim IDs by stage | Pending |
| Held IDs and reasons | Pending |
| My name or initials | Pending |
| Optional later self-check performed | Not yet recorded |
| Historical or current replay cutoff | Pending |
| Backend version and uncommitted changes | Pending |
| Source paths and model settings | Pending |
| Fresh run or cache policy | Pending |
| New TRACE IDs and errors | Pending |
| AI assistance and date | Draft adaptation assisted by Codex on 12 September 2026; record further assistance |

Preserve the separate case 8 repeat outside the ten-case denominator. Do not call an approved subset the completed evaluation of all ten. An approved worksheet establishes expected behavior; accuracy still requires comparing actual controlled outputs against it.

## My short change log
| Date | Case and stage | What changed and why |
|---|---|---|
| 12 September 2026 | Workbook workflow | Adapted for one human reviewer; original inputs and evidence notes retained; no human labels approved. |
| To fill in | To fill in | To fill in |
''']
out = '\n\n'.join(parts)
out = re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)', r'\1\n', out)
assert all(r['input']['text'] in out for r in records)
assert len(re.findall(r'^## Case \d+ ', out, re.M)) == 10
assert 'Reviewer A' not in out and 'Reviewer B' not in out
assert len(re.findall(r'^### S\d\d ', out, re.M)) == 14
(root / 'IRIS_Solo_Calibration_Workbook.md').write_text(out, encoding='utf-8')
print('Created solo workbook; all ten inputs and fourteen source records retained.')
