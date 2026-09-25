"""Read-only TRACE evaluation export. Does not run IRIS or change its databases."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evaluation' / 'trace-ten-cases'
OUT.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect((ROOT / 'iris-backend/.iris-trace/traces.sqlite3').as_uri() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row
ids = ['1853a5aa61fe4badb1de3fbf18c581d6','fa41f52087f34af4a04dcff78f387a36','f73f6e000e924afe9d21ba4b47e2aa3b','214b112b076e42c6a7645335108d3c0c','ca9ac265af86450fa09a84ffec43755e','48f717ee56b3485a837bd63cb054d10d','9fe83e8c73cc45bd8c39589f619b7f38','1a0a6ff587e14e95a2a421032d4845ff','75e31974eb424e2c98736c038ea4e051','c34abc3719374011959edd76752ad559']
expected = [
 [('Review ambiguity','Determine whether the imaginary nine-dash-line ownership assertion is satire or a literal assertion; do not infer intent from absurdity alone.')],
 [('Verify attribution',x) for x in ['Padilla asked Wamil about visiting BARMM and terrorism awareness; preserve both components.', 'Padilla raised the Audit Observation Memorandum and linked confidential funds to alleged NPA recruitment surveillance.', 'Padilla asked whether Wamil handled an investigation concerning confidential funds.', 'Wamil answered that it was an evaluation, not an investigation; retain the denial and the question context.', 'Padilla asked whether confidential agents must identify themselves and state their real names.', 'Wamil said the joint circular had no such provisions; resolve what such provisions refers to.', 'Padilla asked for the definition of confidential and Wamil answered classified.']],
 [('Verify factual assertion',x) for x in ['Carpenter supplied written evidence and oral testimony supporting the Philippine arbitration case; preserve 2013 initiation, 2015 hearing and 2016 ruling as different dates.', 'Carpenter was killed in a home invasion in Ajong, Sibulan, Negros Oriental on July 12; retain alleged perpetrator details as allegations.', 'His 34-year-old companion was injured.', 'The suspects and investigation had the reported status at the time of publication.', 'Carpenter began studying Philippine marine ecosystems in 1975.', 'The 2016 tribunal ruling rejected the nine-dash-line legal claim.', 'Carpenter researched the Verde Island Passage.', 'Carpenter advocated UNESCO recognition for that area.', 'Named institutions and groups issued tributes.']] + [('Verify attribution','Cardino condemned the killing and promised accountability.')],
 [('Verify factual assertion','Bea Borres and Meray Yamada appeared together again; establish what reunion refers to.'),('Verify attribution','Bea stated the reunion did not mean they were co-parenting Victoria Hope; do not infer actual parenting arrangements from the denial alone.')],
 [('Verify attribution','Padilla said the sitting Vice President is an impeachable officer, citing the constitutional provision; merge repeated direct quote/paraphrase.'),('Verify attribution','Padilla described impeachment as a mechanism for accountability and removal.'),('Verify attribution','Padilla asked Gatchalian/the Senate to clarify its position; preserve named recipient.'),('Verify factual assertion','Duterte posted PHP360,000 bail on Saturday for three grave-threat counts involving the three named people.')],
 [('Verify factual assertion','Recently reblocked EDSA sections developed potholes and surface damage.'),('Verify attribution','24 Oras reported affected EDSA Busway/Phase 1 locations and the Christmas Eve project start.'),('Verify factual assertion','The project estimated cost was PHP1.2 billion; preserve estimate, not actual expenditure.'),('Verify attribution','Jay Sonza criticized DPWH under Dizon and questioned rapid road damage despite funding; merge repeated description.'),('Verify factual assertion','No response from Dizon had been issued as of the report; time-bound absence claim requires cautious evidence review.')],
 [('Verify attribution',x) for x in ['Padilla questioned Wamil about his personal background.', 'The questioning included the need for medicines in remote areas.', 'The questioning included terrorism threats.', 'These issues were cited as reasons for confidential-fund use; do not convert a cited rationale into proof of actual fund use.']],
 [('Verify attribution',x) for x in ['Samaniego made the science/video-game argument during the stated DZRH program and date; verify attribution independently of scientific truth.', 'He used his own Call of Duty experience as an example; do not present anecdote as causal evidence.', 'He attributed the shooting to online contacts rather than GoreBox and warned about predators across platforms.', 'He said over 20 similar mobile games existed and warned that bans would prompt migration.', 'He described the failure to enforce age ratings, including the reported age mismatch.', 'He made the MTRCB/Vivamax analogy; preserve it as a hypothetical argument, not an actual incident.']],
 [('Verify factual assertion','The peso closed at PHP62.513 per USD1 on the date in the complete logged input; distinguish closing, intraday, official reference and retail rates. Treat bagsak as framing.')],
 [('Verify factual assertion','An announcement identified ten forthcoming National Artists; distinguish announced recognition from a ceremony already completed. Exclude exemplary as evaluation.')]
]
notes = [
 'Ambiguity review required before assigning a single gold route. Related background is not automatically supporting or contradicting evidence.',
 'Audit flags truncated quotations and lost exchange context. A fragment cannot receive full extraction credit merely because a few original words remain.',
 'HTTP503 is a processing failure. Zero final claims is not evidence that zero claims were extracted before the error. Ignore evaluative tribute language as separate factual claims.',
 'No Checkable Claims conflicts with the proposed eligibility labels. Confirm scope policy before adjudicating celebrity-news examples.',
 'Two outputs do not cover all four proposed assertions. Bail is a separate factual claim; quoted restatements should not inflate the denominator. Emotional framing need not become another claim.',
 'Quotation/abbreviation boundaries and original-to-translated alignment need review. Empty usable extraction is not proof the input contains no facts.',
 'Four components may remain one displayed compound claim; evaluate component coverage separately from the number of UI cards. Processing error is not Not Found.',
 'Six outputs are not proof of six correct extractions or verdicts. Attribution-source availability must be checked; evidence outside the allowlist cannot count as a missed approved-source retrieval.',
 'The full logged input controls the date and currency denominator, not the truncated heading in the audit document. Profiler exclusion blocks retrieval.',
 'Announcement eligibility and source-path coverage are separate. A /news search restriction may miss /lifestyle, but cannot explain a profiler stop before search.'
]

def cell(value):
    return str(value if value is not None else 'Not recorded').replace('|','\\|').replace('\n',' ')

lines = ['# IRIS Ten-Case TRACE Evaluation', '',
 'Prepared 2026-09-11. Retrospective pilot evaluation, not a certified accuracy score.', '',
 '## Scope and labeling status',
 'Observed data come from the local TRACE database and the ten-case audit_logs.docx mapping. Expected labels below are analyst proposals prepared AFTER observing failures. They need independent reviewer adjudication; this is a development set, not a held-out benchmark. No live verification or source re-fetch was performed. Backend code and databases were not modified.',
 'There are 11 recorded runs for 10 cases. Case 8 uses its first chronological run; its repeat is reported separately, not substituted for a better result. HTTP completion is not semantic correctness. Partial capture limits per-stage conclusions. Cached outputs are explicitly labeled.', '',
 '## Batch results',
 '| Case | TRACE ID | Recorded time (Philippines) | HTTP | Status | Capture | Final claim count | Seconds |',
 '|---|---|---|---|---|---|---:|---:|']
records=[]
for i,id in enumerate(ids,1):
    row=dict(db.execute('SELECT * FROM traces WHERE id=?',(id,)).fetchone())
    events=[json.loads(r[0]) for r in db.execute('SELECT data FROM events WHERE trace_id=? ORDER BY seq',(id,))]
    response=next((e['data'] for e in reversed(events) if e.get('kind') in ('request.result','request.output')), {})
    inp=next((e['data'] for e in events if e.get('kind')=='request.input' and e.get('data',{}).get('text')), {})
    artifact=db.execute("SELECT data FROM artifacts WHERE trace_id=? AND kind='request_input' LIMIT 1",(id,)).fetchone()
    if artifact:
        candidate=json.loads(artifact[0])
        if isinstance(candidate,dict) and isinstance(candidate.get('text'),str):
            inp=candidate
    config=next((e['data'] for e in events if e.get('kind')=='runtime.configuration'),{})
    summary=json.loads(row['summary']);row['summary']=summary
    record=dict(case=i,trace=row,input=inp,response=response,configuration=config,events=events)
    records.append(record)
    stamp=datetime.fromtimestamp(row['created'],timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    lines.append(f"| {i} | {id} | {stamp} | {row['http_status']} | {row['status']} | {row['capture_status']} | {row['claim_count']} | {summary['duration_ms']/1000:.2f} |")

completed=sum(r['trace']['status']=='completed' for r in records)
capture=sum(r['trace']['capture_status']=='complete' for r in records)
lines += ['',f'Operational completion: **{completed}/10 ({completed*10}%)**. Complete trace capture: **{capture}/10 ({capture*10}%)**.',
 'These are operational measurements, NOT verdict accuracy. HTTP200 No Checkable Claims counts as operational completion but may fail eligibility evaluation.', '',
 '| Accuracy metric | Result | Why |','|---|---|---|',
 '| Extraction precision / recall / F1 | Pending adjudication | Match original spans to proposed labels; cached and failed runs need separate treatment. |',
 '| Routing accuracy | Pending adjudication | Label all eligible and intentionally excluded segments; do not use model confidence as ground truth. |',
 '| Retrieval success | Not yet measurable | Requires independently inspected known admissible sources per claim. |',
 '| Article extraction success | Not yet measurable | Extraction counts do not establish that required passages survived. |',
 '| Evidence precision | Not yet measurable | Recorded quotations/URLs are system outputs, not independently validated reference evidence. |',
 '| Verdict agreement | Not yet measurable | Final reference verdicts remain unadjudicated. |', '',
 '## Scoring rules',
 'One-to-one semantic matching preserves speaker, recipient, action, negation, amount and date. Duplicate outputs are extra predictions. Optional granularity splits must be agreed before scoring; Case 7 components are not automatically four extraction targets. A failed request stays in completion statistics; downstream metrics are not reached rather than zero-valued successful judgments.',
 'Precision = correct matched outputs / all outputs. Recall = matched expected claims / expected claims. F1 = 2PR/(P+R). Report numerator/denominator and N/A for empty denominators. Evidence precision uses claim-source pairs. Never infer falsehood from Not Found. Technical failure is not a factual verdict.', '',
 '## Configuration limits',
 'Per-run snapshots are preserved in observed_trace_records.json. The recorded commit identifies a checkout, not necessarily all uncommitted changes. TRACE snapshots say first use in process: restart after edits. OPENAI_MODEL=null is an unset environment setting, not proof no model ran. Cache policy was not controlled for these historical runs; do not claim a frozen fresh-run benchmark.', '']

for r in records:
    i=r['case'];res=r['response'] or {};claims=res.get('claims',[])
    original=r['input'].get('text','Input not captured.')
    if isinstance(original,dict):
        original='TRACE input is truncated; this is only the captured preview, not the complete original: '+str(original.get('preview',original))
    lines += [f'## Case {i}', '',f"TRACE: `{r['trace']['id']}`", '', '### Original input',original,'',
              '### Expected extraction and routing (proposed)', '| Label ID | Expected route | Assertion / required context |', '|---|---|---|']
    for j,(route,assertion) in enumerate(expected[i-1],1):lines.append(f'| P{i:02}-C{j:02} | {route} | {cell(assertion)} |')
    lines += ['', 'Expected verdict: **pending source adjudication**, not preset to Verified. Supporting evidence must establish the particular assertion; partial coverage must identify unsupported components. Source unavailable/outside policy is distinct from contradiction.',
              '', '### Observed behavior', f"Result: {res.get('verdict',r['trace']['summary'].get('verdict'))}. Message: {res.get('message',r['trace']['summary'].get('message'))}",
              f"Profiler route: {res.get('content_profile_route','not recorded')}; extraction status: {res.get('claim_extraction_status','not recorded')}; language: {res.get('detected_language','not recorded')}.",
              '| Output ID | Extracted claim | Verdict | Cache hit | Evidence links |', '|---|---|---|---|---:|']
    for c in claims:lines.append(f"| {c.get('claim_id')} | {cell(c.get('claim_text'))} | {cell(c.get('verdict'))} | {cell(c.get('cache_hit'))} | {len(c.get('evidence_sources',[]))} |")
    if not claims:lines.append('| - | No final claim list captured; inspect stage outputs for pre-error extraction. | - | - | - |')
    if i==8:
        lines += ['', 'Audit-document observation: all six final claims were reported as Not Found. The first TRACE run has partial capture and no complete final claim payload; do not substitute an intermediate semantic or fallback verdict for the final result.']
    lines += ['', '### Recorded stages', '| Stage | Execution | Duration ms | Domain outcome |','|---|---|---:|---|']
    for e in r['events']:
        if e.get('kind') in ('span.end','span.error'):
            lines.append(f"| {cell(e.get('stage_id'))} | {cell(e.get('status',e.get('kind')))} | {cell(e.get('duration_ms'))} | {cell(e.get('domain_outcome'))} |")
    lines += ['', '### Evidence review worksheet',
              'System-recorded URLs and quotations below are candidates for human inspection, NOT gold references. Missing fields must not be invented.',
              '| Claim | Candidate URL | Recorded passage | Human relationship / policy / access-date review |', '|---|---|---|---|']
    for c in claims:
        components=(c.get('component_review') or {}).get('components',[])
        citations=[q for comp in components for q in comp.get('citations',[])]
        for a in c.get('evidence_sources',[]):
            quotes=[q['quote'] for q in citations if q.get('url')==a.get('url')]
            lines.append(f"| {c.get('claim_id')} | {cell(a.get('url'))} | {cell(' / '.join(quotes) or 'No component passage recorded')} | Pending independent inspection |")
    lines += ['| All remaining expected labels | Pending reference URL | Pending inspected verbatim passage | Pending |','',
              '### Diagnosis and next regression',notes[i-1],
              'Reviewer sign-off: pending. Matched expected IDs: pending. Correct / extra / missed outputs: pending. Final reference verdict and disagreement resolution: pending.',
              'Retest the exact input after a scoped change; preserve the new TRACE ID, configuration and cache-hit flags. Require appropriate routing, preserved context, auditable evidence and no technical-failure verdict.', '']
    if res.get('ignored_segments'):
        lines += ['### Recorded excluded segments','| Text | Type | Reason |','|---|---|---|']
        for s in res['ignored_segments']:lines.append(f"| {cell(s.get('text'))} | {cell(s.get('segment_type'))} | {cell(s.get('reason_codes',s.get('reason')))} |")
    lines.append('')

repeat=dict(db.execute('SELECT * FROM traces WHERE id=?',('2871b496bb5a4b5bbe7835cd1a1cfe44',)).fetchone())
lines += ['## Repeat run and interpretation',
          f"Case 8 repeat: `{repeat['id']}`; {repeat['status']}; capture {repeat['capture_status']}; HTTP {repeat['http_status']}; {repeat['claim_count']} final claims; {json.loads(repeat['summary'])['duration_ms']/1000:.2f} seconds. It is excluded from the ten-case denominator. Do not interpret faster repetition as optimization without accounting for cache use.", '',
          '## Next evaluation batch',
          '1. Have two reviewers adjudicate the proposed labels and granularity, resolving disagreements.',
          '2. Inspect and timestamp reference sources; classify support, partial support, contradiction and background separately.',
          '3. Freeze commit plus dirty-worktree snapshot, source paths, model settings and cache policy.',
          '4. Rerun these ten as development regressions; keep 20-30 independently selected unseen examples separate for pilot generalization.',
          '5. Report stage-specific fractions, a verdict confusion matrix, completion rate, capture rate and regressions. Do not average stage percentages into a single accuracy score.', '']
(OUT/'IRIS_TRACE_Accuracy_Evaluation.md').write_text('\n'.join(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False) for v in lines),encoding='utf-8')
(OUT/'observed_trace_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(records),'completed':completed,'complete_capture':capture,'output':str(OUT),'response_claim_counts':[len((r['response'] or {}).get('claims',[])) for r in records]}))
