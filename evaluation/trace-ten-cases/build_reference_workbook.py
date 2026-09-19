"""Build a human-review workbook without running IRIS or changing historical records."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
records = json.loads((ROOT / 'observed_trace_records.json').read_text(encoding='utf-8'))
old = (ROOT / 'IRIS_TRACE_Accuracy_Evaluation.md').read_text(encoding='utf-8')
sources = {
'S01': ('ABS-CBN Padilla terrorism report', 'https://www.abs-cbn.com/news/nation/2026/8/5/padilla-tests-auditor-on-knowledge-of-terrorism-security-threats-1501', '2026-08-05', 'Within configured ABS-CBN /news search path.', 'Metadata only in this access attempt; body was not returned.', 'No evidence passage approved. The title alone cannot confirm the seven exchanges.', 'Recover and read the body or inspect the original recording; do not promote the title to evidence.'),
'S02': ('DZRH Day 13 hearing coverage', 'https://www.dzrh.com.ph/post/day-13-of-vp-sara-duterte-impeachment-trial-or-august-5-2026', '2026-08-05', 'Outside configured sources; human comparison only.', 'Body inspected.', 'Hindi po siya imbestigasyon. Evaluation po,', 'Under Padilla questions Wamil on BARMM and confidential fund audits: supports the BARMM/terrorism exchange, correction and agent-identity discussion. Does not establish all medicine/personal-background details.'),
'S03': ('Philstar universities and Carpenter tributes', 'https://www.philstar.com/headlines/2026/07/15/2542349/universities-green-groups-demand-justice-slain-marine-biologist-kent-carpenter', '2026-07-15', 'Within configured Philstar search domain.', 'Body inspected.', 'He began studying the Verde Island Passage in 1975', 'See Witness for the West Philippine Sea, Fifty years in Philippine waters, and institutional statements. Covers research, advocacy and testimony; exact dates and incident details still need separate checks.'),
'S04': ('Philstar robbery investigation update', 'https://www.philstar.com/headlines/2026/07/15/2542350/robbery-eyed-american-scientists-killing-after-home-ransacked', '2026-07-15', 'Within configured Philstar search domain.', 'Body inspected.', 'Sa ocular inspection po wala po kaming nakikitang forcible entry sa bahay', 'Under Partner\'s account under scrutiny, police dispute forced entry and describe the partner as unharmed. Treat this as later reported evidence, not proof of every allegation or an adjudicated criminal finding.'),
'S05': ('GMA Bea and Meray reunion coverage', 'https://www.gmanetwork.com/entertainment/showbiznews/bea-borres-reacts-to-criticism-over-video-reunion-with-ex-boyfriend-meray-yamada/138114/', '2026-09-08', 'GMA /entertainment is outside the configured /news search path. Runtime acceptance not tested.', 'Body inspected.', 'she and Meray will not be co-parenting as a couple.', 'Opening paragraphs report the reunion; the paragraph after the second embedded video reports Bea\'s clarification. Confirm exact scope of co-parenting wording with the original vlog before final sign-off.'),
'S06': ('DZRH Padilla Senate position report', 'https://www.dzrh.com.ph/post/padilla-questions-senate-stance-on-grave-threats-case-against-vp-duterte', '2026-09-07', 'Outside configured sources; human comparison only.', 'Body inspected.', 'Ginoong Pangulo, ang minorya ay nagtatanong, ano po ba ang posisyon ng Senado?', 'Reports the constitutional citation, request for Senate clarification, and bail amount/count/named complainants. Does not by itself establish the named addressee Gatchalian or Saturday timing.'),
'S07': ('Daily Tribune EDSA potholes report', 'https://tribune.net.ph/2026/08/10/p6-b-edsa-rehab-marred-by-potholes', 'Page displays 2026-08-11; URL contains 2026-08-10', 'Outside configured sources; human comparison only.', 'Body inspected.', 'Work began on 24 December 2025', 'Reports potholes and a Dizon response, and distinguishes a broader PHP6 billion project. Resolve phase scope before comparing with PHP1.2 billion; resolve original publication date before judging no-response wording.'),
'S08': ('Philstar Samaniego and GoreBox report', 'https://www.philstar.com/headlines/2026/06/26/2537982/gorebox-developer-rejects-senate-invitation-tacloban-school-shooting-probe', '2026-06-26', 'Within configured Philstar search domain.', 'Body inspected.', 'in an interview with dzMM on Wednesday, June 24', 'Under Violent games, violent gamers: similar scientific argument and online-community concern attributed to Samaniego. This is not the claimed July 4 DZRH interview. Age-rating facts elsewhere are not proof he said them.'),
'S09': ('Philstar forex record', 'https://qa.philstar.com/other-sections/forex-stocks/2026/09/09/2555147/162513', '2026-09-09 17:30 shown in search result', 'QA subdomain needs canonical-link and runtime policy review.', 'Search result only; opening failed. Main-host counterpart also failed.', 'No independently inspected body passage. Search title displays 1$:62.513.', 'Do not use a changing sidebar as a historical market record. Locate a dated close report and confirm PHP per USD rather than another rate type.'),
'S10': ('Metrobank hosted BusinessWorld peso report', 'https://wealthinsights.metrobank.com.ph/news/peso-rebounds-to-track-yens-climb', '2026-09-10 shown in search result', 'Outside configured sources; candidate only.', 'Search result only; opening failed.', 'No independently inspected passage.', 'Search result associates the number with a Wednesday close. Recover the complete dated article and BAP record before approval.'),
'S11': ('ABS-CBN National Artists announcement', 'https://www.abs-cbn.com/lifestyle/people-culture-events/2026/9/9/ten-new-national-artists-named-2117', '2026-09-09 21:17; updated 21:49', 'Outside configured ABS-CBN /news search path.', 'Metadata only in this access attempt.', 'No evidence passage approved; title names ten new National Artists.', 'A title establishes a retrieval lead, not the full statement. This page predates the recorded case; the later Philstar report does not.'),
'S12': ('Philstar ten National Artists report', 'https://www.philstar.com/lifestyle/2026/09/10/2555313/bing-lao-nicanor-tiongson-among-10-new-national-artists/amp/', '2026-09-10 09:46', 'Within configured Philstar domain; published AFTER the original case 10 run.', 'Body inspected.', 'Ten individuals will be bestowed the Order of National Artists of the Philippines', 'Opening, award-description paragraph and ceremony paragraph support announcement and honor description. Suitable for current reference review, not evidence IRIS could retrieve at 00:04 that morning.'),
'S13': ('PNA Carpenter task group report', 'https://www.pna.gov.ph/articles/1279377', '2026-07; exact publication date pending', 'Within configured PNA domain.', 'Opening blocked with HTTP403; indexed /index.php version also failed.', 'No evidence passage approved.', 'Candidate for initial police account and date/time; reviewer must inspect the full source before using any details.'),
'S14': ('Inquirer August 5 trial highlights', 'https://newsinfo.inquirer.net/2278335/highlights-day-13-of-sara-duterte-impeachment-trial-aug-5-2026', '2026-08-05', 'Within configured Inquirer domain.', 'Opening blocked with HTTP403; search result only.', 'No evidence passage approved.', 'Candidate for confidential-fund dates and claimed counter-insurgency rationale; not yet evidence of exact questions.'),
}

titles = ['Imaginary nine dash line ownership','Padilla and Wamil hearing exchanges','Kent Carpenter biography and killing','Bea Borres and Meray Yamada reunion','Padilla Senate position and Duterte bail','EDSA repairs and criticism','Padilla medicines and terrorism question','Samaniego video game statements','Peso dollar closing rate','Ten National Artists announcement']
queries = [
 ['"Philippines now owns China" "Daily Tribune"', '"Daily Tribune" "imaginary" "nine dash line"'],
 ['"Padilla" "Wamil" "BARMM" site:abs-cbn.com/news','"Wamil" "evaluation" "investigation"','"Wamil" "classified" "joint circular"'],
 ['"Kent Carpenter" "July 12" "Ajong"','"Kent Carpenter" "1975" "UNESCO" site:philstar.com','"Kent Carpenter" "Cardino" "companion"'],
 ['"Bea Borres" "Meray Yamada" "reunion"','"Bea Borres" "co-parenting" "September"'],
 ['"Padilla" "Gatchalian" "grave threats" "September 7"','"Sara Duterte" "360000" "September 5"'],
 ['"EDSA" "24 Oras" "lubak"','"EDSA" "Jay Sonza" "Dizon"','"EDSA" "1.2 billion" "Phase 1"'],
 ['"Padilla" "Wamil" "medicines"','"Padilla" "Wamil" "far-flung"','"Padilla" "Wamil" "terrorism" site:abs-cbn.com/news'],
 ['"Art Samaniego" "Special on Saturday" "July 4"','"Samaniego" "Call of Duty"','"Samaniego" "20" "GoreBox"'],
 ['"peso" "62.513" "September 9"','"62.513" "closing" "2026"'],
 ['"ten" "National Artists" "September 9 2026"','"Proclamation 1414" "National Artists"'],
]
exclusions = [
 'Do not decide satire solely because the assertion is implausible. The logged text has no image or emoji; external context cannot be silently added to the input.',
 'Merge the opening BARMM headline with its detailed question. Keep complete questions and answers. Do not treat a question as a claim that its implied premise is true.',
 'Do not create separate claims for helped defend, widely respected, leading expert, significant role, world-class, generous mentor or the closing reflection. Keep factual years inside mixed evaluative sentences.',
 'Do not infer romance, reconciliation or actual parenting arrangements. There is no explicit publisher attribution in the input; leave publisher attribution empty.',
 'Merge repeated quotation and paraphrase. Emotional framing need not be separately verified. Do not infer immunity from being impeachable; reported legal arguments are not legal findings.',
 'Exclude ANG GALING NI SEC. VINCE as evaluative/sarcastic framing, not the whole post. Do not lose factual Filipino sentences after abbreviations such as Sec. or DPWH.',
 'Do not replace the claim with general confidential-fund news. No outlet is named in the input. A speaker/source supplied by retrieval must not become invented original attribution.',
 'Merge repeated headline and quotation. Treat the Vivamax example as hypothetical, not a real screening incident. Do not independently assert the shooting cause because Samaniego allegedly said it.',
 'Treat bagsak as framing, but preserve the number, currency direction and closing date. Input says September 9 and Wednesday; 2026 comes from run context and must be labeled as such.',
 'Exclude exemplary as evaluation; preserve the announced honor and count. Do not invent the ten names in extracted text: the user did not supply them.',
]

# Each record is an analyst relationship assessment, not a signed reference verdict.
reviews = [
 [('Pending context','None approved','Literal territorial ownership versus satirical media criticism remains ambiguous.','Original post/image and team satire policy. No final factual verdict yet.')],
 [('External full support','S02; S01 metadata','S02 describes both visiting BARMM and awareness of terrorism, naming speaker and witness.','Pending in-policy passage; do not mark Verified from ABS-CBN title.'),
 ('External partial support','S02; S14 candidate','Broad fund linkage appears; exact AOM/NPA recruitment-surveillance wording not fully established.','Pending exact passage; Partially Verified only after admissible partial coverage is demonstrated.'),
 ('External partial support','S02','The correction appears; verbatim wording of the preceding investigation question is not fully reproduced.','Pending question passage and approved-source evidence.'),
 ('External full support','S02','Correction is explicitly tied to Wamil and COA role.','Attribution support found outside policy; approved-source verdict remains pending.'),
 ('External full support','S02','Agent identity question is reported with Padilla as speaker.','Pending in-policy source and complete wording.'),
 ('External full support','S02','Joint circular response is tied to disclosure of identities.','Pending in-policy source; not an independent interpretation of the circular.'),
 ('External full support','S02','Question and classified answer are linked.','Pending in-policy source; keep exchange together.')],
 [('Partial support','S03','Scientific reports and hearing testimony supported; verify formal written submission and all chronology separately.','Proposed Partially Verified for enriched compound assertion; reviewer must inspect dated tribunal records.'),
 ('Mixed evidence','S03; S04; S13 candidate','Killing/home/date supported in reporting; later police account disputes forced entry.','No single final verdict until original publication time and event wording are resolved.'),
 ('Contradiction candidate','S04','Later police reporting describes partner as unharmed. Confirm same companion and alleged injury meaning.','Pending temporal and identity review; do not preset Verified or infer innocence/guilt.'),
 ('Partial support','S04','Police searching for men on CCTV supported as of July 15; all process details and original timestamp unresolved.','Pending as-of date; no timeless investigation-status verdict.'),
 ('Full support','S03','Study of a Philippine marine area in 1975 is explicit.','Proposed Verified, subject to reviewer approval.'),
 ('Pending passage','None approved','Need a direct passage on the tribunal ruling; avoid converting maritime entitlement findings into sovereignty over all disputed territory.','Pending authoritative record plus in-policy corroboration.'),
 ('Full support','S03','Verde Island Passage research is explicit.','Proposed Verified, subject to reviewer approval.'),
 ('Full support','S03','UNESCO advocacy is reported as distinct from completed UNESCO inscription.','Proposed Verified for advocacy only.'),
 ('Full support','S03','The story cites Silliman, UP MSI and conservation-group statements.','Proposed Verified for issuing tributes, not for evaluative praise.'),
 ('Pending passage','S13 candidate','No inspected exact Cardino statement found in this pass.','Pending attribution evidence; killing coverage alone is insufficient.')],
 [('External full support','S05','Reunion content is reported. GMA entertainment path differs from configured search path.','Human support found; in-policy expected verdict pending path-policy decision.'),
 ('External support with wording review','S05','Reported clarification includes as a couple; confirm whether this equals the broader denial in the input.','Pending original-vlog wording and path-policy decision; do not overextend denial.')],
 [('External full support','S06','Padilla\'s statement and constitutional citation are reported.','Pending approved-source attribution passage.'),
 ('External partial support','S06','Report discusses legal reasoning but does not reproduce this exact accountability/removal summary.','Pending statement passage; Constitution alone would not prove Padilla said it.'),
 ('External partial support','S06','Request to Senate supported; named addressee Gatchalian not established in inspected text.','Pending recipient evidence; do not drop recipient to obtain full support.'),
 ('External partial support','S06','Amount, counts and named people supported; Saturday not established by this report alone.','Pending approved-source and date evidence; posting bail does not establish guilt.')],
 [('External support','S07','Newly repaired busway damage reported; exact full set of sections unresolved.','Pending approved-source passage matching location and repair timing.'),
 ('External partial support','S07','Start date and Phase 1 background supported, not attribution to 24 Oras.','Pending original 24 Oras segment or approved report naming that broadcast.'),
 ('Scope conflict','S07','Broader project cost is PHP6 billion here; cannot compare it to PHP1.2 billion without phase scope.','Pending phase-level budget evidence; discrepancy is not automatically contradiction.'),
 ('Pending passage','None approved','No inspected Jay Sonza statement found. A different critic is not a substitute.','Pending speaker-matching evidence.'),
 ('Time conflict','S07','Dizon response is reported by August 11; original post publication time missing.','Pending original timestamp; absence cannot be inferred from silence in one article.')],
 [('Pending passage','S01 metadata; S02 background','Personal-background component not established by inspected material.','Parent verdict pending; no invented source attribution.'),
 ('Pending passage','S01 metadata; S02 background','Medicine discussion elsewhere involves other senators; do not transfer their words to Padilla.','Parent verdict pending; no cross-speaker evidence credit.'),
 ('External full support','S02','Padilla asking Wamil about terrorism awareness is explicit.','Partial parent coverage only; in-policy confirmation pending.'),
 ('External partial support','S02; S14 candidate','Counter-insurgency rationale appears, not the complete medicine-plus-terrorism linkage.','Do not verify actual spending or justify it; parent remains pending.')],
 [('Partial support with event mismatch','S08','Similar science argument attributed to same person; dzMM June 24 is a different event from DZRH July 4.','Not full support. Pending specific interview; Partially Verified only if policy permits explicit unsupported event details.'),
 ('Pending passage','None approved','No inspected Call of Duty quotation found.','Pending attribution; do not treat personal anecdote as scientific proof.'),
 ('Partial support','S08','Online-network concern supported; definitive cause and cross-platform predator details not all established.','Proposed partial coverage, final attribution verdict pending complete component review.'),
 ('Pending passage','None approved','No inspected over-20/mobile-platform/migration passage found.','Pending speaker-specific evidence.'),
 ('Background only','S08','Game rating and suspect age are reported, but this does not show Samaniego made the enforcement argument.','Pending attribution; do not verify this statement from topic overlap.'),
 ('Pending passage','None approved','No inspected MTRCB/Vivamax analogy found.','Pending attribution; no separate factual allegation about a child viewing a film.')],
 [('Candidate support only','S09; S10','Number/date appears in indexed results, but a durable dated body was not inspected.','Pending reference inspection; never count search snippets or a live sidebar as approved gold evidence.')],
 [('Full support now, historical restriction','S12; S11 metadata','Later report confirms ten forthcoming honors; it was published after the test ran.','Proposed Verified for current replay; historical evidence verdict pending a source available before that run.')],
]

intro = '''# IRIS Beginner Friendly Reference Review Workbook

## Purpose and current status
This workbook prepares the ten TRACE cases for human approval before further calibration. It contains proposed extraction targets, evidence checks, search keywords and reviewer forms. It is Reference Draft 0.1, prepared on 11 September 2026, not an approved answer key and not an accuracy certificate.

All ten cases have worksheets. Some sources have readable evidence, while others are blocked, metadata-only, outside configured search paths or still missing. Pending means we have not established the answer; it does not mean the claim is false or that IRIS must return Not Found. No backend code, cache or historical TRACE record was changed, and no fresh IRIS request was run.

## Start here
1. Read the original input and the expected claims before looking at IRIS results.
2. Reviewer A and Reviewer B independently check the same wording, route, dates and evidence. Do not copy each other\'s decisions.
3. Open each source ID in the source register. Short excerpts are navigation aids; read the surrounding paragraphs and check the speaker.
4. Mark each component Full, Partial, Contradicted, Background only, or Unresolved. Separately mark whether the source is in the configured search scope.
5. Resolve disagreements with a third reviewer or thesis adviser. Keep the reason for the final choice.
6. Freeze an approved version before retesting. Save the backend version, settings, cache policy and new TRACE IDs.

## People and reviewer responsibilities
| Role | Plain language responsibility | Assigned person |
|---|---|---|
| Preparer | Organizes the inputs and proposes labels. This draft was prepared with AI assistance and is not an independent human review. | Codex assisted draft |
| Reviewer A | Checks meaning, complete claims and what should be skipped; also reads evidence independently. | To be assigned |
| Reviewer B | Independently checks the same claims, evidence, dates and allowed sources. | To be assigned |
| Adjudicator | Resolves disagreements with written reasons; not a majority vote without evidence. | Team member or thesis adviser to be assigned |
| Test operator | Runs the unchanged inputs and records settings, cache use, errors and TRACE IDs after approval. | To be assigned |

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
| Gold / reference label | A reviewer-approved expected answer. | This draft is not gold until signed off. |
| Adjudication | Resolving reviewer disagreement with reasons and evidence. | Agree on whether one sentence has two independent claims. |
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

Use precision = matched claims / predicted claims; recall = matched claims / approved expected claims. Report F1 and raw counts, with N/A for empty denominators. Routing agreement uses approved segments, including excluded segments. Evidence precision uses accepted claim-source pairs checked by reviewers. Retrieval success uses only claims with a known accessible in-policy reference available at the evaluation cutoff. Report verdict agreement separately for factual and attribution claims. Never average these percentages into a single accuracy number.

Keep technical failures in operational completion statistics. Do not score unobserved downstream judgments as wrong verdicts or silently discard them. The historical batch had 8/10 completed requests and 5/10 complete captures; neither number measures factual accuracy. Final accuracy remains pending reviewer approval and complete retest records.
'''

lines=[intro]
for idx,r in enumerate(records):
    i=idx+1
    sec=old.split(f'## Case {i}\n',1)[1].split('\n## ',1)[0]
    extracted=[]
    for line in sec.splitlines():
        if re.match(r'\| P\d\d-C',line):
            cells=line.strip('|').split('|')
            extracted.append(tuple(c.strip() for c in cells))
    assert len(extracted)==len(reviews[idx]), (i,len(extracted),len(reviews[idx]))
    lines += [f'## Case {i} {titles[idx]}',f'Original TRACE ID: `{r["trace"]["id"]}`. Human approval: pending. Evidence access checks: 11 September 2026.',
              '### Original input',r['input']['text'],'### Expected extraction and routing',
              ('Proposed unit count: one parent claim with four separately reviewed components. P07-C01 to P07-C04 below are legacy component IDs, not four mandatory output claims.' if i==7 else f'Proposed unit count: {len(extracted)}; agree before scoring. '+('Case 1 remains unscored pending context review.' if i==1 else '')),
              '| ID | What IRIS should preserve | Route |','|---|---|---|']
    for ident,route,claim in extracted: lines.append(f'| {ident} | {claim} | {route} |')
    if i==10:
        lines += ['Proposed addition P10-C02: the Order is the country\'s highest national recognition for contributions to arts and letters. This factual award description was omitted from the earlier one-claim proposal. Keep it as a second target or an explicitly scored component by reviewer agreement; do not silently discard it. S12 supports it for current review, but was published after the historical run.']
    lines += ['### What not to turn into a separate claim',exclusions[idx], '### Search keyword guide']
    for q in queries[idx]: lines.append('- '+q)
    lines += ['These are starting search phrases, not proof or an exhaustive search history. Try full names, Filipino/English equivalents and date variants. Do not add names or dates to the extracted assertion merely because a search found them.',
              '### Claim by claim evidence assessment','The source register contains URLs, access status, short exact excerpts where available and passage locations. External means outside the configured search scope. Each row remains awaiting human sign-off.',
              '| ID | Evidence relationship and sources | Supported and missing details | Proposed outcome and next action |','|---|---|---|---|']
    for (ident,_,_), (rel,refs,coverage,decision) in zip(extracted,reviews[idx]):
        lines.append(f'| {ident} | {rel}. {refs} | {coverage} | {decision} |')
    lines += ['### Expected pipeline behavior',
              '| Stage | What a passing run should do |','|---|---|',
              f'| Screening and routing | Apply the routes above; retain factual content even when surrounding language is opinion. {"Resolve ambiguity rather than invent context." if i==1 else "Return one combined skipped-content note where applicable."} |',
              '| Claim extraction | Preserve speaker, recipient, negation, dates and quantities; resolve pronouns only from the supplied input; merge repetitions. |',
              '| Search | Search the event broadly and the particular assertion; record which sources and paths were attempted. Shared evidence must still match each claim. |',
              '| Article extraction | Preserve the actual relevant passage, not only a title or navigation. A long unrelated body does not satisfy this test. |',
              '| Evidence selection | Check each component and speaker. Reject background-only evidence as confirmation; keep reasons for rejection. |',
              '| Verdict and display | Distinguish full/partial support, uncertainty and errors. Positive verdicts need valid matching evidence links. Do not invent publisher attribution. |',
              '### Reviewer worksheet',
              '| Field | Reviewer A | Reviewer B | Agreed decision |','|---|---|---|---|',
              '| Name and review date | Pending | Pending | Adjudicator pending |',
              '| Accepted claim IDs and count | Pending | Pending | Pending |',
              '| Excluded text and reason | Pending | Pending | Pending |',
              '| Sources opened and passage location | Pending | Pending | Pending |',
              '| Source policy and publication cutoff | Pending | Pending | Pending |',
              '| Full / partial / contradicted / unresolved components | Pending | Pending | Pending |',
              '| Final expected verdict per ID | Pending | Pending | Pending |',
              '| Disagreement and resolution reason | Pending | Pending | Pending |',
              'For each ID with different judgments, add a separate review row rather than one combined verdict for the post.',
              '### Retest record',
              'New TRACE ID: pending. Backend version and settings: pending. Cache hit or fresh: pending. Run timestamp: pending. Matched IDs: pending. Extra outputs: pending. Missed IDs: pending. Evidence-pair decisions: pending. Final verdict agreement: pending. Technical error or incomplete capture: pending.']

lines += ['## Source register','All access statuses below refer to this review on 11 September 2026, not a guarantee that your browser or IRIS can access the page. Short excerpts are quoted only where a body was inspected. Longer supporting context must be read at the linked location. A search-only result is not an approved reference.']
for sid,(title,url,date,policy,access,quote,note) in sources.items():
    lines += [f'### {sid} {title}',f'Source: [{title}]({url})',f'Publication: {date}. Access: {access}',f'Policy: {policy}',f'Passage or limitation: {quote}',f'Location and interpretation: {note}','Reviewer confirmation and date: pending.']
lines += ['## Remaining review priorities',
'1. Case 3: resolve early versus later incident reporting before approving the injury, forced-entry and investigation labels. No blanket Verified target.',
'2. Cases 2 and 7: recover the ABS-CBN body and inspect exact speaker-linked passages. The browser tool saw metadata, not proof of the dialogue.',
'3. Cases 4 and 10: decide whether GMA entertainment and ABS-CBN lifestyle should be in scope. Keep source-policy changes separate from extraction fixes.',
'4. Cases 5, 6 and 8: locate missing specific statements and dates. Similar topics, speakers on different dates and different critics are not substitutes.',
'5. Case 9: inspect a dated market-close record. Do not make financial accuracy claims from a search result alone.',
'6. Case 1: approve an ambiguity/satire policy without giving the model context absent from the input.',
'7. Assign two human reviewers and an adjudicator. No names or approvals have been invented.',
'## Release checklist',
'Reference version: Draft 0.1. Approved version/date: pending. Reviewer signatures: pending. Historical source cutoff: per original request. Current replay cutoff: pending agreed run date. Known unresolved labels: retain explicitly. Backend commit plus uncommitted-change snapshot: pending. Source-path settings: record. Model/settings: record. Cache policy: record. Preserve all ten originals and the separate case 8 repeat. Keep new unseen cases outside this development set.',
'A completed worksheet means the case is documented. An approved reference means humans have settled its expected behavior. An accuracy measurement requires comparing a controlled run against that approved reference. These are three different milestones.']
out=ROOT/'IRIS_Beginner_Reference_Workbook.md'
out.write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
# Adjacent Markdown table rows must remain contiguous for GFM conversion.
text=out.read_text(encoding='utf-8')
text=re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)',r'\1\n',text)
out.write_text(text,encoding='utf-8')
print(f'Wrote {out}; ten cases; {len(sources)} source records; no live IRIS runs')
