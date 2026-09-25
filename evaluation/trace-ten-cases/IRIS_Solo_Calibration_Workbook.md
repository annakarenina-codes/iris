# IRIS Solo Calibration Workbook

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


## Keyword reference and glossary
| Term | Beginner friendly meaning | Example or rule |
|---|---|---|
| Claim / assertion | A statement whose meaning can be checked. | Padilla asked Wamil a particular question. |
| Extraction | Choosing the checkable statements from the post. | Keep the date and who spoke; remove unrelated praise. |
| Component | One necessary detail inside a claim. | Person, action, recipient, date, amount and negation. |
| Attribution | Checking who said something, not whether their opinion is true. | Evidence must connect Wamil with his answer. |
| Publisher attribution | The outlet named in the input. | Leave empty when the post names no outlet. |
| Content Profiler / routing | The screening step that decides which content goes to verification. | A factual number should not be skipped because nearby wording is emotional. |
| Retrieval | Finding potentially useful sources. | A relevant article is a candidate, not yet proof. |
| Article extraction | Reading usable article text from a webpage. | A title without article paragraphs is metadata-only. |
| Evidence passage | The actual source words addressing the statement. | A short quote plus its surrounding context. |
| Semantic similarity | A measure of how related two texts sound. | Same people and topic do not prove the same action. |
| Full / partial support | All necessary details supported / only some supported. | An event confirmed but its date missing is not full support. |
| Contradiction | Evidence directly conflicts with a necessary detail. | Unharmed versus injured, after confirming the same person/time. |
| Background only | Related information that does not prove the assertion. | GoreBox age rating cannot prove Samaniego made a particular argument. |
| Approved source scope | The sources and paths IRIS is configured to search. | GMA /news and /entertainment are different paths. |
| Gold / reference label | A researcher-approved expected answer. | This draft is not gold until signed off. |
| Decision resolution | Settling your conflicting judgments with evidence and a written reason. | Keep uncertain labels on Hold; outside advice is optional. |
| Granularity | How finely a post is split into claims. | One compound claim may have four components. |
| Cache | A saved result reused instead of a fresh check. | Record it; do not call a cached run a new verification. |
| TRACE | The request record showing which processing stages ran. | A missing log is not proof that a stage succeeded or failed. |
| Regression | A previously working behavior that breaks after a change. | Rerun old cases after a fix. |
| Held out test | New examples not used to design fixes. | These ten known cases are development tests, not held out. |
| Precision | Of the extracted claims, how many are correct targets? | 4 correct out of 5 extracted = 80%. |
| Recall | Of the expected claims, how many were found? | 4 found out of 6 expected = 66.7%. |
| F1 | A combined precision/recall measure. | 2 x precision x recall / (precision + recall). |
| Not Found | Insufficient admissible evidence in that run. | Not a synonym for false. |
| Technical error | Processing did not finish correctly. | HTTP503 is not a factual verdict. |

## Source and date rules
Current sources.py searches VERA Files first and then ABS-CBN /news, GMA /news, Inquirer, Philstar, Manila Bulletin, PNA and PIA. Search-path scope is not automatically proof of runtime link acceptance: this workbook does not claim to have executed the URL validator. Sources outside this set can inform human review but cannot be counted as missed in-policy retrieval without an approved policy change.

Keep two assessments: historical performance using sources available before each original request, and current replay using sources available now. The test input publication date is not automatically its TRACE submission date. This matters for last year, Saturday, no response yet, ongoing investigations and changing prices. Later evidence may inform current truth review but cannot be blamed on earlier retrieval.

Verified and Partially Verified below are proposed outcomes, never automatic results. Mixed contradiction requires explicit review, not a forced partial badge. Attribution verified means the statement was made, not that its underlying proposition is true. Politically Sensitive is a separate per-claim caution, not a verdict; propose it for political/government claims in cases 1, 2, 5, 6, 7 and the arbitration components of case 3, subject to policy approval.

## How to score without overstating accuracy
Agree on expected claim units first. Match outputs one-to-one while preserving meaning. Count correct matches, extra/duplicate outputs and missed targets. Partial component support does not automatically earn full extraction credit. For case 7 score one parent claim plus four components; do not count four cards as mandatory. Case 1 stays out of scored routing/extraction denominators until ambiguity is resolved.

Use precision = matched claims / predicted claims; recall = matched claims / approved expected claims. Report F1 and raw counts, with N/A for empty denominators. Routing agreement uses approved segments, including excluded segments. Evidence precision uses accepted claim-source pairs checked by you. Retrieval success uses only claims with a known accessible in-policy reference available at the evaluation cutoff. Report verdict agreement separately for factual and attribution claims. Never average these percentages into a single accuracy number.

Keep technical failures in operational completion statistics. Do not score unobserved downstream judgments as wrong verdicts or silently discard them. The historical batch had 8/10 completed requests and 5/10 complete captures; neither number measures factual accuracy. Final accuracy remains pending reviewer approval and complete retest records.




## Case 1 Imaginary nine dash line ownership

Original TRACE ID: `1853a5aa61fe4badb1de3fbf18c581d6`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

The Philippines now owns China according to DAILY TRIBUNE’s own imaginary 9-dash line.

### Expected extraction and routing

Proposed unit count: 1; agree before scoring. Case 1 remains unscored pending context review.

| ID | What IRIS should preserve | Route |
|---|---|---|
| P01-C01 | Determine whether the imaginary nine-dash-line ownership assertion is satire or a literal assertion; do not infer intent from absurdity alone. | Review ambiguity |

### What not to turn into a separate claim

Do not decide satire solely because the assertion is implausible. The logged text has no image or emoji; external context cannot be silently added to the input.

### Search keyword guide

- "Philippines now owns China" "Daily Tribune"

- "Daily Tribune" "imaginary" "nine dash line"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P01-C01 | Pending context. None approved | Literal territorial ownership versus satirical media criticism remains ambiguous. | Original post/image and team satire policy. No final factual verdict yet. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Resolve ambiguity rather than invent context. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P01-C01 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 2 Padilla and Wamil hearing exchanges

Original TRACE ID: `fa41f52087f34af4a04dcff78f387a36`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

'NAKARATING NA PO BA KAYO NG BARMM?' Senator-judge Robinhood Padilla asked former state auditor Roderick Wamil if he had ever visited the Bangsamoro Autonomous Region in Muslim Mindanao (BARMM) and whether he was aware of the country's ongoing terrorism threats. During his interjection, Padilla raised preliminary questions about the Audit Observation Memorandum, trying to establish ties to the confidential funds used by Vice President Sara Duterte for surveillance on potential New People's Army (NPA) recruitment. "Pero kayo po ang humahawak ng imbestigasyon patungkol sa confidential funds, tama po ba?" Padilla asked Wamil. "Hindi po siya imbestigasyon. Evaluation po," the witness answered. "Kayo po ba ay naniniwala na ang mga confidential agent ay dapat magpakilala? Sabihin ang kanilang totoong pangalan," the senator furthered. "Wala pong provisions as to that po sa joint circular," Wamil said. Padilla then asked Wamil to define "confidential," to which the auditor replied, "classified."

### Expected extraction and routing

Proposed unit count: 7; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P02-C01 | Padilla asked Wamil about visiting BARMM and terrorism awareness; preserve both components. | Verify attribution |
| P02-C02 | Padilla raised the Audit Observation Memorandum and linked confidential funds to alleged NPA recruitment surveillance. | Verify attribution |
| P02-C03 | Padilla asked whether Wamil handled an investigation concerning confidential funds. | Verify attribution |
| P02-C04 | Wamil answered that it was an evaluation, not an investigation; retain the denial and the question context. | Verify attribution |
| P02-C05 | Padilla asked whether confidential agents must identify themselves and state their real names. | Verify attribution |
| P02-C06 | Wamil said the joint circular had no such provisions; resolve what such provisions refers to. | Verify attribution |
| P02-C07 | Padilla asked for the definition of confidential and Wamil answered classified. | Verify attribution |

### What not to turn into a separate claim

Merge the opening BARMM headline with its detailed question. Keep complete questions and answers. Do not treat a question as a claim that its implied premise is true.

### Search keyword guide

- "Padilla" "Wamil" "BARMM" site:abs-cbn.com/news

- "Wamil" "evaluation" "investigation"

- "Wamil" "classified" "joint circular"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P02-C01 | External full support. S02; S01 metadata | S02 describes both visiting BARMM and awareness of terrorism, naming speaker and witness. | Pending in-policy passage; do not mark Verified from ABS-CBN title. |
| P02-C02 | External partial support. S02; S14 candidate | Broad fund linkage appears; exact AOM/NPA recruitment-surveillance wording not fully established. | Pending exact passage; Partially Verified only after admissible partial coverage is demonstrated. |
| P02-C03 | External partial support. S02 | The correction appears; verbatim wording of the preceding investigation question is not fully reproduced. | Pending question passage and approved-source evidence. |
| P02-C04 | External full support. S02 | Correction is explicitly tied to Wamil and COA role. | Attribution support found outside policy; approved-source verdict remains pending. |
| P02-C05 | External full support. S02 | Agent identity question is reported with Padilla as speaker. | Pending in-policy source and complete wording. |
| P02-C06 | External full support. S02 | Joint circular response is tied to disclosure of identities. | Pending in-policy source; not an independent interpretation of the circular. |
| P02-C07 | External full support. S02 | Question and classified answer are linked. | Pending in-policy source; keep exchange together. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P02-C01 | Not reviewed | To fill in |
| P02-C02 | Not reviewed | To fill in |
| P02-C03 | Not reviewed | To fill in |
| P02-C04 | Not reviewed | To fill in |
| P02-C05 | Not reviewed | To fill in |
| P02-C06 | Not reviewed | To fill in |
| P02-C07 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 3 Kent Carpenter biography and killing

Original TRACE ID: `f73f6e000e924afe9d21ba4b47e2aa3b`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

His work helped defend the Philippines. American marine biologist Dr. Kent Carpenter, whose scientific testimony supported the Philippines in its landmark 2016 South China Sea arbitration case against China, was shot and killed during a home invasion in Negros Oriental province in the Central Visayas region of the Philippines. Police said three unidentified men forcibly entered Carpenter's home in Barangay Ajong, Sibulan, on the night of July 12. One of the intruders allegedly shot the 73-year-old scientist in the head, killing him. His 34-year-old companion was also injured. The suspects remain at large, and investigators are reviewing CCTV footage, interviewing witnesses, and pursuing leads. Police Brigadier General Romano Cardiño condemned the killing as a "senseless act of violence" and vowed to bring those responsible to justice. Carpenter was widely respected in the scientific community for his decades of work in the Philippines. He first began studying the country's marine ecosystems in 1975 and became one of the world's leading experts on Philippine marine biodiversity. Beyond his scientific achievements, Carpenter also played a significant role in one of the Philippines' biggest international legal victories. During the South China Sea arbitration initiated by the Philippines in 2013, he submitted expert written evidence documenting the environmental damage caused by China's island reclamation and destructive fishing practices in the West Philippine Sea. He also delivered oral testimony during the 2015 merits hearing. The tribunal's 2016 ruling overwhelmingly favored the Philippines and found no legal basis for China's sweeping "nine-dash line" claims. Carpenter also conducted extensive research in the Verde Island Passage, often called the "center of the center" of global marine shore fish biodiversity, and was a strong advocate for having the area recognized as a UNESCO World Heritage Site. His death has prompted tributes from Silliman University, the University of the Philippines Marine Science Institute, conservation groups, and fellow scientists. Many remembered him not only as a world-class researcher, but also as a generous mentor who spent five decades helping Filipinos better understand and protect their country's extraordinary marine ecosystems. His life reminds us that science can shape history just as much as politics or diplomacy—and that the people behind those contributions are often remembered long after the headlines fade.

### Expected extraction and routing

Proposed unit count: 10; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P03-C01 | Carpenter supplied written evidence and oral testimony supporting the Philippine arbitration case; preserve 2013 initiation, 2015 hearing and 2016 ruling as different dates. | Verify factual assertion |
| P03-C02 | Carpenter was killed in a home invasion in Ajong, Sibulan, Negros Oriental on July 12; retain alleged perpetrator details as allegations. | Verify factual assertion |
| P03-C03 | His 34-year-old companion was injured. | Verify factual assertion |
| P03-C04 | The suspects and investigation had the reported status at the time of publication. | Verify factual assertion |
| P03-C05 | Carpenter began studying Philippine marine ecosystems in 1975. | Verify factual assertion |
| P03-C06 | The 2016 tribunal ruling rejected the nine-dash-line legal claim. | Verify factual assertion |
| P03-C07 | Carpenter researched the Verde Island Passage. | Verify factual assertion |
| P03-C08 | Carpenter advocated UNESCO recognition for that area. | Verify factual assertion |
| P03-C09 | Named institutions and groups issued tributes. | Verify factual assertion |
| P03-C10 | Cardino condemned the killing and promised accountability. | Verify attribution |

### What not to turn into a separate claim

Do not create separate claims for helped defend, widely respected, leading expert, significant role, world-class, generous mentor or the closing reflection. Keep factual years inside mixed evaluative sentences.

### Search keyword guide

- "Kent Carpenter" "July 12" "Ajong"

- "Kent Carpenter" "1975" "UNESCO" site:philstar.com

- "Kent Carpenter" "Cardino" "companion"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P03-C01 | Partial support. S03 | Scientific reports and hearing testimony supported; verify formal written submission and all chronology separately. | Proposed Partially Verified for enriched compound assertion; reviewer must inspect dated tribunal records. |
| P03-C02 | Mixed evidence. S03; S04; S13 candidate | Killing/home/date supported in reporting; later police account disputes forced entry. | No single final verdict until original publication time and event wording are resolved. |
| P03-C03 | Contradiction candidate. S04 | Later police reporting describes partner as unharmed. Confirm same companion and alleged injury meaning. | Pending temporal and identity review; do not preset Verified or infer innocence/guilt. |
| P03-C04 | Partial support. S04 | Police searching for men on CCTV supported as of July 15; all process details and original timestamp unresolved. | Pending as-of date; no timeless investigation-status verdict. |
| P03-C05 | Full support. S03 | Study of a Philippine marine area in 1975 is explicit. | Proposed Verified, subject to reviewer approval. |
| P03-C06 | Pending passage. None approved | Need a direct passage on the tribunal ruling; avoid converting maritime entitlement findings into sovereignty over all disputed territory. | Pending authoritative record plus in-policy corroboration. |
| P03-C07 | Full support. S03 | Verde Island Passage research is explicit. | Proposed Verified, subject to reviewer approval. |
| P03-C08 | Full support. S03 | UNESCO advocacy is reported as distinct from completed UNESCO inscription. | Proposed Verified for advocacy only. |
| P03-C09 | Full support. S03 | The story cites Silliman, UP MSI and conservation-group statements. | Proposed Verified for issuing tributes, not for evaluative praise. |
| P03-C10 | Pending passage. S13 candidate | No inspected exact Cardino statement found in this pass. | Pending attribution evidence; killing coverage alone is insufficient. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P03-C01 | Not reviewed | To fill in |
| P03-C02 | Not reviewed | To fill in |
| P03-C03 | Not reviewed | To fill in |
| P03-C04 | Not reviewed | To fill in |
| P03-C05 | Not reviewed | To fill in |
| P03-C06 | Not reviewed | To fill in |
| P03-C07 | Not reviewed | To fill in |
| P03-C08 | Not reviewed | To fill in |
| P03-C09 | Not reviewed | To fill in |
| P03-C10 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 4 Bea Borres and Meray Yamada reunion

Original TRACE ID: `214b112b076e42c6a7645335108d3c0c`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

Bea Borres and her ex, Meray Yamada, are back in the same frame, but Bea made it clear that their reunion doesn’t mean they’re co-parenting their daughter, Victoria Hope

### Expected extraction and routing

Proposed unit count: 2; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P04-C01 | Bea Borres and Meray Yamada appeared together again; establish what reunion refers to. | Verify factual assertion |
| P04-C02 | Bea stated the reunion did not mean they were co-parenting Victoria Hope; do not infer actual parenting arrangements from the denial alone. | Verify attribution |

### What not to turn into a separate claim

Do not infer romance, reconciliation or actual parenting arrangements. There is no explicit publisher attribution in the input; leave publisher attribution empty.

### Search keyword guide

- "Bea Borres" "Meray Yamada" "reunion"

- "Bea Borres" "co-parenting" "September"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P04-C01 | External full support. S05 | Reunion content is reported. GMA entertainment path differs from configured search path. | Human support found; in-policy expected verdict pending path-policy decision. |
| P04-C02 | External support with wording review. S05 | Reported clarification includes as a couple; confirm whether this equals the broader denial in the input. | Pending original-vlog wording and path-policy decision; do not overextend denial. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P04-C01 | Not reviewed | To fill in |
| P04-C02 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 5 Padilla Senate position and Duterte bail

Original TRACE ID: `ca9ac265af86450fa09a84ffec43755e`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

Senator-Judge Robin Padilla became emotional as he sought clarification on the Senate’s position regarding the grave threats case against Vice President Sara Duterte. In his manifestation on Monday, Padilla pointed out that Duterte, as a sitting Vice President, is an impeachable officer under the 1987 Constitution. “Ako po ay binalot ng mga karimarimarim na balita nitong nakaraang araw. Ang isang sitting vice president po ay isang impeachable officer. Ito po ay tahasang nakalagay sa 1987 Constitution, Article 11, Section 2,” Padilla said. He noted that impeachment is the constitutional mechanism for holding impeachable officers politically accountable and removing them from office over impeachable offenses. Padilla then asked Senate President Win Gatchalian about the chamber’s position on the developments involving Duterte. “Ginoong Pangulo, ang minorya ay nagtatanong. Ano po ang posisyon ng Senado dito?… Ano ba naman itong nangyayaring ito sa atin, Ginoong Pangulo, kailangan po natin malinawan ito dahil nahahati po ang ating mga kababayan sa nangyayaring ito. Hindi po ito nakakatulong sa atin,” he said. Duterte posted ₱360,000 bail on Saturday for three counts of grave threats involving President Ferdinand Marcos Jr., First Lady Liza Araneta-Marcos and former House Speaker Martin Romualdez.

### Expected extraction and routing

Proposed unit count: 4; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P05-C01 | Padilla said the sitting Vice President is an impeachable officer, citing the constitutional provision; merge repeated direct quote/paraphrase. | Verify attribution |
| P05-C02 | Padilla described impeachment as a mechanism for accountability and removal. | Verify attribution |
| P05-C03 | Padilla asked Gatchalian/the Senate to clarify its position; preserve named recipient. | Verify attribution |
| P05-C04 | Duterte posted PHP360,000 bail on Saturday for three grave-threat counts involving the three named people. | Verify factual assertion |

### What not to turn into a separate claim

Merge repeated quotation and paraphrase. Emotional framing need not be separately verified. Do not infer immunity from being impeachable; reported legal arguments are not legal findings.

### Search keyword guide

- "Padilla" "Gatchalian" "grave threats" "September 7"

- "Sara Duterte" "360000" "September 5"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P05-C01 | External full support. S06 | Padilla's statement and constitutional citation are reported. | Pending approved-source attribution passage. |
| P05-C02 | External partial support. S06 | Report discusses legal reasoning but does not reproduce this exact accountability/removal summary. | Pending statement passage; Constitution alone would not prove Padilla said it. |
| P05-C03 | External partial support. S06 | Request to Senate supported; named addressee Gatchalian not established in inspected text. | Pending recipient evidence; do not drop recipient to obtain full support. |
| P05-C04 | External partial support. S06 | Amount, counts and named people supported; Saturday not established by this report alone. | Pending approved-source and date evidence; posting bail does not establish guilt. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P05-C01 | Not reviewed | To fill in |
| P05-C02 | Not reviewed | To fill in |
| P05-C03 | Not reviewed | To fill in |
| P05-C04 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 6 EDSA repairs and criticism

Original TRACE ID: `48f717ee56b3485a837bd63cb054d10d`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

"ANG GALING NI SEC. VINCE" Muling nabuksan ang usapin sa kalidad ng EDSA rehabilitation project matapos maiulat na ilang bahagi ng kalsadang isinailalim sa road reblocking ay nagkaroon na agad ng mga lubak at pagkabakbak sa kabila ng kamakailang pagkakagawa nito. Batay sa ulat ng 24 Oras, kabilang sa mga apektadong lugar ang ilang seksyon ng EDSA Busway at mga bahagi ng Phase 1 ng road reblocking project na sinimulan noong bisperas ng Pasko noong nakaraang taon. Tinatayang aabot sa P1.2 bilyon ang halaga ng naturang proyekto. Dahil dito, binatikos ni veteran broadcaster Jay Sonza ang Department of Public Works and Highways (DPWH) sa ilalim ni Secretary Vince Dizon. Sa kanyang social media post, kinuwestiyon niya kung bakit nagkaroon agad ng sira ang ilang bahagi ng EDSA sa kabila ng malaking pondong inilaan para sa rehabilitasyon. Sa ngayon, wala pang inilalabas na pahayag si Dizon kaugnay sa mga batikos at sa ulat hinggil sa kondisyon ng ilang bagong inayos na bahagi ng pangunahing lansangan sa Metro Manila.

### Expected extraction and routing

Proposed unit count: 5; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P06-C01 | Recently reblocked EDSA sections developed potholes and surface damage. | Verify factual assertion |
| P06-C02 | 24 Oras reported affected EDSA Busway/Phase 1 locations and the Christmas Eve project start. | Verify attribution |
| P06-C03 | The project estimated cost was PHP1.2 billion; preserve estimate, not actual expenditure. | Verify factual assertion |
| P06-C04 | Jay Sonza criticized DPWH under Dizon and questioned rapid road damage despite funding; merge repeated description. | Verify attribution |
| P06-C05 | No response from Dizon had been issued as of the report; time-bound absence claim requires cautious evidence review. | Verify factual assertion |

### What not to turn into a separate claim

Exclude ANG GALING NI SEC. VINCE as evaluative/sarcastic framing, not the whole post. Do not lose factual Filipino sentences after abbreviations such as Sec. or DPWH.

### Search keyword guide

- "EDSA" "24 Oras" "lubak"

- "EDSA" "Jay Sonza" "Dizon"

- "EDSA" "1.2 billion" "Phase 1"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P06-C01 | External support. S07 | Newly repaired busway damage reported; exact full set of sections unresolved. | Pending approved-source passage matching location and repair timing. |
| P06-C02 | External partial support. S07 | Start date and Phase 1 background supported, not attribution to 24 Oras. | Pending original 24 Oras segment or approved report naming that broadcast. |
| P06-C03 | Scope conflict. S07 | Broader project cost is PHP6 billion here; cannot compare it to PHP1.2 billion without phase scope. | Pending phase-level budget evidence; discrepancy is not automatically contradiction. |
| P06-C04 | Pending passage. None approved | No inspected Jay Sonza statement found. A different critic is not a substitute. | Pending speaker-matching evidence. |
| P06-C05 | Time conflict. S07 | Dizon response is reported by August 11; original post publication time missing. | Pending original timestamp; absence cannot be inferred from silence in one article. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P06-C01 | Not reviewed | To fill in |
| P06-C02 | Not reviewed | To fill in |
| P06-C03 | Not reviewed | To fill in |
| P06-C04 | Not reviewed | To fill in |
| P06-C05 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 7 Padilla medicines and terrorism question

Original TRACE ID: `9fe83e8c73cc45bd8c39589f619b7f38`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

Senator-judge Robin Padilla asks state auditor Roderick Wamil about his personal background, noting whether he understood the need for medicines in far-flung areas and the threat of terrorism in the country—issues cited as among the reasons for Vice President Sara Duterte’s use of confidential funds.

### Expected extraction and routing

Proposed unit count: one parent claim with four separately reviewed components. P07-C01 to P07-C04 below are legacy component IDs, not four mandatory output claims.

| ID | What IRIS should preserve | Route |
|---|---|---|
| P07-C01 | Padilla questioned Wamil about his personal background. | Verify attribution |
| P07-C02 | The questioning included the need for medicines in remote areas. | Verify attribution |
| P07-C03 | The questioning included terrorism threats. | Verify attribution |
| P07-C04 | These issues were cited as reasons for confidential-fund use; do not convert a cited rationale into proof of actual fund use. | Verify attribution |

### What not to turn into a separate claim

Do not replace the claim with general confidential-fund news. No outlet is named in the input. A speaker/source supplied by retrieval must not become invented original attribution.

### Search keyword guide

- "Padilla" "Wamil" "medicines"

- "Padilla" "Wamil" "far-flung"

- "Padilla" "Wamil" "terrorism" site:abs-cbn.com/news

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P07-C01 | Pending passage. S01 metadata; S02 background | Personal-background component not established by inspected material. | Parent verdict pending; no invented source attribution. |
| P07-C02 | Pending passage. S01 metadata; S02 background | Medicine discussion elsewhere involves other senators; do not transfer their words to Padilla. | Parent verdict pending; no cross-speaker evidence credit. |
| P07-C03 | External full support. S02 | Padilla asking Wamil about terrorism awareness is explicit. | Partial parent coverage only; in-policy confirmation pending. |
| P07-C04 | External partial support. S02; S14 candidate | Counter-insurgency rationale appears, not the complete medicine-plus-terrorism linkage. | Do not verify actual spending or justify it; parent remains pending. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P07-C01 | Not reviewed | To fill in |
| P07-C02 | Not reviewed | To fill in |
| P07-C03 | Not reviewed | To fill in |
| P07-C04 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 8 Samaniego video game statements

Original TRACE ID: `1a0a6ff587e14e95a2a421032d4845ff`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

'NAGLALARO AKO NG CALL OF DUTY, HINDI KO NAISIP KAILANMAN NA MAMARIL SA LABAS' The rush to blame video games for school violence is not supported by science, a cybersecurity and technology expert said Saturday, pushing back against calls to ban video games in the wake of a shooting incident involving a minor in Tacloban City. Cybersecurity and technology expert Art Samaniego Jr. made the argument in an interview on DZRH News program "Special on Saturday" on July 4, citing research by the Oxford Internet Institute showing no direct link between violent video games and real-world crime or violence. "Naglalaro ako ng Call of Duty, hindi ko naisip kailanman na mamaril sa labas. Maraming pag-aaral ang ginawa na nagpapatunay na walang matibay na ebidensya na nagsasabing ang video game ay may direktang dahilan sa school violence o crime in real life," Samaniego said. He said the real cause of the Tacloban school shooting was not GoreBox—the game the 14-year-old shooter allegedly played—but the people the child was communicating with online, and that extremist recruiters and online predators follow children across platforms regardless of which game or app they use. "Ang tunay na dahilan nun hindi 'yung laro, kundi 'yung mga taong nakakausap nung bata online. Ang dapat nating gawin hindi i-ban 'yung game, kundi tingnan ang kabuuang isyu," Samaniego said. He warned that banning GoreBox specifically is futile since more than 20 similar games exist on mobile platforms alone, and more on PC and console—and children, he said, have no loyalty to specific platforms and will simply migrate to the next available option. Samaniego said the real enforcement gap is not the existence of violent games but the failure to implement existing age ratings—GoreBox is an 18+ game that a 14-year-old was able to access—drawing a direct comparison to the MTRCB film rating system. "Para 'yang sa MTRCB, merong rating. Kung sa MTRCB may ginawang pelikula ang Vivamax tapos may nakapanood na 12-year-old, ipapasara ba natin ang Vivamax? O titingnan natin bakit siya nakapasok sa sinehan dahil mali ang implementation? Ganun lang 'yun dapat ang isipin ng mga lawmakers," Samaniego said.

### Expected extraction and routing

Proposed unit count: 6; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P08-C01 | Samaniego made the science/video-game argument during the stated DZRH program and date; verify attribution independently of scientific truth. | Verify attribution |
| P08-C02 | He used his own Call of Duty experience as an example; do not present anecdote as causal evidence. | Verify attribution |
| P08-C03 | He attributed the shooting to online contacts rather than GoreBox and warned about predators across platforms. | Verify attribution |
| P08-C04 | He said over 20 similar mobile games existed and warned that bans would prompt migration. | Verify attribution |
| P08-C05 | He described the failure to enforce age ratings, including the reported age mismatch. | Verify attribution |
| P08-C06 | He made the MTRCB/Vivamax analogy; preserve it as a hypothetical argument, not an actual incident. | Verify attribution |

### What not to turn into a separate claim

Merge repeated headline and quotation. Treat the Vivamax example as hypothetical, not a real screening incident. Do not independently assert the shooting cause because Samaniego allegedly said it.

### Search keyword guide

- "Art Samaniego" "Special on Saturday" "July 4"

- "Samaniego" "Call of Duty"

- "Samaniego" "20" "GoreBox"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P08-C01 | Partial support with event mismatch. S08 | Similar science argument attributed to same person; dzMM June 24 is a different event from DZRH July 4. | Not full support. Pending specific interview; Partially Verified only if policy permits explicit unsupported event details. |
| P08-C02 | Pending passage. None approved | No inspected Call of Duty quotation found. | Pending attribution; do not treat personal anecdote as scientific proof. |
| P08-C03 | Partial support. S08 | Online-network concern supported; definitive cause and cross-platform predator details not all established. | Proposed partial coverage, final attribution verdict pending complete component review. |
| P08-C04 | Pending passage. None approved | No inspected over-20/mobile-platform/migration passage found. | Pending speaker-specific evidence. |
| P08-C05 | Background only. S08 | Game rating and suspect age are reported, but this does not show Samaniego made the enforcement argument. | Pending attribution; do not verify this statement from topic overlap. |
| P08-C06 | Pending passage. None approved | No inspected MTRCB/Vivamax analogy found. | Pending attribution; no separate factual allegation about a child viewing a film. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P08-C01 | Not reviewed | To fill in |
| P08-C02 | Not reviewed | To fill in |
| P08-C03 | Not reviewed | To fill in |
| P08-C04 | Not reviewed | To fill in |
| P08-C05 | Not reviewed | To fill in |
| P08-C06 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 9 Peso dollar closing rate

Original TRACE ID: `75e31974eb424e2c98736c038ea4e051`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

Nananatili pa ring bagsak ang palitan ng piso kontra dolyar matapos magsara sa ₱62.513 = $1 ngayong Miyerkules, Setyembre 9.

### Expected extraction and routing

Proposed unit count: 1; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P09-C01 | The peso closed at PHP62.513 per USD1 on the date in the complete logged input; distinguish closing, intraday, official reference and retail rates. Treat bagsak as framing. | Verify factual assertion |

### What not to turn into a separate claim

Treat bagsak as framing, but preserve the number, currency direction and closing date. Input says September 9 and Wednesday; 2026 comes from run context and must be labeled as such.

### Search keyword guide

- "peso" "62.513" "September 9"

- "62.513" "closing" "2026"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P09-C01 | Candidate support only. S09; S10 | Number/date appears in indexed results, but a durable dated body was not inspected. | Pending reference inspection; never count search snippets or a live sidebar as approved gold evidence. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P09-C01 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Case 10 Ten National Artists announcement

Original TRACE ID: `c34abc3719374011959edd76752ad559`. Human approval: pending. Evidence access checks: 11 September 2026.

### Original input

Ten exemplary Filipinos from various fields of the arts will be proclaimed as National Artists, the country’s highest national recognition for distinct and significant contributions to the arts and letters.

### Expected extraction and routing

Proposed unit count: 1; agree before scoring. 

| ID | What IRIS should preserve | Route |
|---|---|---|
| P10-C01 | An announcement identified ten forthcoming National Artists; distinguish announced recognition from a ceremony already completed. Exclude exemplary as evaluation. | Verify factual assertion |

Proposed addition P10-C02: the Order is the country's highest national recognition for contributions to arts and letters. This factual award description was omitted from the earlier one-claim proposal. Keep it as a second target or an explicitly scored component by reviewer agreement; do not silently discard it. S12 supports it for current review, but was published after the historical run.

### What not to turn into a separate claim

Exclude exemplary as evaluation; preserve the announced honor and count. Do not invent the ten names in extracted text: the user did not supply them.

### Search keyword guide

- "ten" "National Artists" "September 9 2026"

- "Proclamation 1414" "National Artists"

These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.

### Claim by claim evidence assessment

The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.

| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |
|---|---|---|---|
| P10-C01 | Full support now, historical restriction. S12; S11 metadata | Later report confirms ten forthcoming honors; it was published after the test ran. | Proposed Verified for current replay; historical evidence verdict pending a source available before that run. |

### Expected pipeline behavior

| Stage | What a passing run should do |
|---|---|
| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. Return one combined skipped-content note where applicable. |
| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |
| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |
| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |
| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |
| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |



### My decision log

My name or initials: __________. Review date: __________. Evaluation cutoff: __________. Reference version: Solo Draft 0.2 until approved.

| Claim or component ID | Stage and my status | My correction or evidence and reason |
|---|---|---|
| P10-C01 | Not reviewed | To fill in |
| P10-C02 | Not reviewed | To fill in |

Status choices: Approve / Revise / Hold. Stage choices: extraction / routing / evidence / verdict. Approval of one stage does not approve the others.

Optional later self-check: date __________; IDs checked __________; changed decision and reason __________. If not done, write Not done, not Passed.

One next action for this case: __________. Blocker if held: __________.

### Retest record

New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.


## Source register

All access statuses below refer to this review on 11 September 2026, not a guarantee that your browser or IRIS can access the page. Short excerpts are quoted only where a body was inspected. Longer supporting context must be read at the linked location. A search-only result is not an approved reference.

### S01 ABS-CBN Padilla terrorism report

Source: [ABS-CBN Padilla terrorism report](https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501)

Publication: 2026-08-05. Access: Metadata only in this access attempt; body was not returned.

Policy: Within configured ABS-CBN /news search path.

Passage or limitation: No evidence passage approved. The title alone cannot confirm the seven exchanges.

Location and interpretation: Recover and read the body or inspect the original recording; do not promote the title to evidence.

My source check and date: pending. Record body access, passage location and any changed content.

### S02 DZRH Day 13 hearing coverage

Source: [DZRH Day 13 hearing coverage](https://www.dzrh.com.ph/post/day-13-of-vp-sara-duterte-impeachment-trial-or-august-5-2026)

Publication: 2026-08-05. Access: Body inspected.

Policy: Outside configured sources; human comparison only.

Passage or limitation: Hindi po siya imbestigasyon. Evaluation po,

Location and interpretation: Under Padilla questions Wamil on BARMM and confidential fund audits: supports the BARMM/terrorism exchange, correction and agent-identity discussion. Does not establish all medicine/personal-background details.

My source check and date: pending. Record body access, passage location and any changed content.

### S03 Philstar universities and Carpenter tributes

Source: [Philstar universities and Carpenter tributes](https://www.philstar.com/headlines/2026/07/15/2542349/universities-green-groups-demand-justice-slain-marine-biologist-kent-carpenter)

Publication: 2026-07-15. Access: Body inspected.

Policy: Within configured Philstar search domain.

Passage or limitation: He began studying the Verde Island Passage in 1975

Location and interpretation: See Witness for the West Philippine Sea, Fifty years in Philippine waters, and institutional statements. Covers research, advocacy and testimony; exact dates and incident details still need separate checks.

My source check and date: pending. Record body access, passage location and any changed content.

### S04 Philstar robbery investigation update

Source: [Philstar robbery investigation update](https://www.philstar.com/headlines/2026/07/15/2542350/robbery-eyed-american-scientists-killing-after-home-ransacked)

Publication: 2026-07-15. Access: Body inspected.

Policy: Within configured Philstar search domain.

Passage or limitation: Sa ocular inspection po wala po kaming nakikitang forcible entry sa bahay

Location and interpretation: Under Partner's account under scrutiny, police dispute forced entry and describe the partner as unharmed. Treat this as later reported evidence, not proof of every allegation or an adjudicated criminal finding.

My source check and date: pending. Record body access, passage location and any changed content.

### S05 GMA Bea and Meray reunion coverage

Source: [GMA Bea and Meray reunion coverage](https://www.gmanetwork.com/entertainment/showbiznews/bea-borres-reacts-to-criticism-over-video-reunion-with-ex-boyfriend-meray-yamada/138114/)

Publication: 2026-09-08. Access: Body inspected.

Policy: GMA /entertainment is outside the configured /news search path. Runtime acceptance not tested.

Passage or limitation: she and Meray will not be co-parenting as a couple.

Location and interpretation: Opening paragraphs report the reunion; the paragraph after the second embedded video reports Bea's clarification. Confirm exact scope of co-parenting wording with the original vlog before final sign-off.

My source check and date: pending. Record body access, passage location and any changed content.

### S06 DZRH Padilla Senate position report

Source: [DZRH Padilla Senate position report](https://www.dzrh.com.ph/post/padilla-questions-senate-stance-on-grave-threats-case-against-vp-duterte)

Publication: 2026-09-07. Access: Body inspected.

Policy: Outside configured sources; human comparison only.

Passage or limitation: Ginoong Pangulo, ang minorya ay nagtatanong, ano po ba ang posisyon ng Senado?

Location and interpretation: Reports the constitutional citation, request for Senate clarification, and bail amount/count/named complainants. Does not by itself establish the named addressee Gatchalian or Saturday timing.

My source check and date: pending. Record body access, passage location and any changed content.

### S07 Daily Tribune EDSA potholes report

Source: [Daily Tribune EDSA potholes report](https://tribune.net.ph/2026/08/10/p6-b-edsa-rehab-marred-by-potholes)

Publication: Page displays 2026-08-11; URL contains 2026-08-10. Access: Body inspected.

Policy: Outside configured sources; human comparison only.

Passage or limitation: Work began on 24 December 2025

Location and interpretation: Reports potholes and a Dizon response, and distinguishes a broader PHP6 billion project. Resolve phase scope before comparing with PHP1.2 billion; resolve original publication date before judging no-response wording.

My source check and date: pending. Record body access, passage location and any changed content.

### S08 Philstar Samaniego and GoreBox report

Source: [Philstar Samaniego and GoreBox report](https://www.philstar.com/headlines/2026/06/26/2537982/gorebox-developer-rejects-senate-invitation-tacloban-school-shooting-probe)

Publication: 2026-06-26. Access: Body inspected.

Policy: Within configured Philstar search domain.

Passage or limitation: in an interview with dzMM on Wednesday, June 24

Location and interpretation: Under Violent games, violent gamers: similar scientific argument and online-community concern attributed to Samaniego. This is not the claimed July 4 DZRH interview. Age-rating facts elsewhere are not proof he said them.

My source check and date: pending. Record body access, passage location and any changed content.

### S09 Philstar forex record

Source: [Philstar forex record](https://qa.philstar.com/other-sections/forex-stocks/2026/09/09/2555147/162513)

Publication: 2026-09-09 17:30 shown in search result. Access: Search result only; opening failed. Main-host counterpart also failed.

Policy: QA subdomain needs canonical-link and runtime policy review.

Passage or limitation: No independently inspected body passage. Search title displays 1$:62.513.

Location and interpretation: Do not use a changing sidebar as a historical market record. Locate a dated close report and confirm PHP per USD rather than another rate type.

My source check and date: pending. Record body access, passage location and any changed content.

### S10 Metrobank hosted BusinessWorld peso report

Source: [Metrobank hosted BusinessWorld peso report](https://wealthinsights.metrobank.com.ph/news/peso-rebounds-to-track-yens-climb)

Publication: 2026-09-10 shown in search result. Access: Search result only; opening failed.

Policy: Outside configured sources; candidate only.

Passage or limitation: No independently inspected passage.

Location and interpretation: Search result associates the number with a Wednesday close. Recover the complete dated article and BAP record before approval.

My source check and date: pending. Record body access, passage location and any changed content.

### S11 ABS-CBN National Artists announcement

Source: [ABS-CBN National Artists announcement](https://www.abs-cbn.com/lifestyle/people-culture-events/2026/9/9/ten-new-national-artists-named-2117)

Publication: 2026-09-09 21:17; updated 21:49. Access: Metadata only in this access attempt.

Policy: Outside configured ABS-CBN /news search path.

Passage or limitation: No evidence passage approved; title names ten new National Artists.

Location and interpretation: A title establishes a retrieval lead, not the full statement. This page predates the recorded case; the later Philstar report does not.

My source check and date: pending. Record body access, passage location and any changed content.

### S12 Philstar ten National Artists report

Source: [Philstar ten National Artists report](https://www.philstar.com/lifestyle/2026/09/10/2555313/bing-lao-nicanor-tiongson-among-10-new-national-artists/amp/)

Publication: 2026-09-10 09:46. Access: Body inspected.

Policy: Within configured Philstar domain; published AFTER the original case 10 run.

Passage or limitation: Ten individuals will be bestowed the Order of National Artists of the Philippines

Location and interpretation: Opening, award-description paragraph and ceremony paragraph support announcement and honor description. Suitable for current reference review, not evidence IRIS could retrieve at 00:04 that morning.

My source check and date: pending. Record body access, passage location and any changed content.

### S13 PNA Carpenter task group report

Source: [PNA Carpenter task group report](https://www.pna.gov.ph/articles/1279377)

Publication: 2026-07; exact publication date pending. Access: Opening blocked with HTTP403; indexed /index.php version also failed.

Policy: Within configured PNA domain.

Passage or limitation: No evidence passage approved.

Location and interpretation: Candidate for initial police account and date/time; reviewer must inspect the full source before using any details.

My source check and date: pending. Record body access, passage location and any changed content.

### S14 Inquirer August 5 trial highlights

Source: [Inquirer August 5 trial highlights](https://newsinfo.inquirer.net/2278335/highlights-day-13-of-sara-duterte-impeachment-trial-aug-5-2026)

Publication: 2026-08-05. Access: Opening blocked with HTTP403; search result only.

Policy: Within configured Inquirer domain.

Passage or limitation: No evidence passage approved.

Location and interpretation: Candidate for confidential-fund dates and claimed counter-insurgency rationale; not yet evidence of exact questions.

My source check and date: pending. Record body access, passage location and any changed content.



## Remaining review priorities

1. Case 3: resolve early versus later incident reporting before approving the injury, forced-entry and investigation labels. No blanket Verified target.

2. Cases 2 and 7: recover the ABS-CBN body and inspect exact speaker-linked passages. The browser tool saw metadata, not proof of the dialogue.

3. Cases 4 and 10: decide whether GMA entertainment and ABS-CBN lifestyle should be in scope. Keep source-policy changes separate from extraction fixes.

4. Cases 5, 6 and 8: locate missing specific statements and dates. Similar topics, speakers on different dates and different critics are not substitutes.

5. Case 9: inspect a dated market-close record. Do not make financial accuracy claims from a search result alone.

6. Case 1: approve an ambiguity/satire policy without giving the model context absent from the input.

7. Record your own name, decisions and dates. No second reviewer or outside sign-off is required for this solo development workflow; unresolved judgments stay on Hold.



## My release checklist
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
