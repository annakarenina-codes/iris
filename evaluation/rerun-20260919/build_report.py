"""
Builds REPORT.md for manual validation of the priority rerun.

For every case: expected behavior, the 18 September assessment, the full input,
what was not checked, and each extracted claim with its verdict, search query,
component decisions, cited passages and evidence links, next to the baseline.
Offline: reads saved JSON only.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / 'full-pipeline-audit-20260918'
from run_priority import PRIORITY, PASSED_ON_0918, STEP3_TARGETS, RETRIEVAL_TARGETS  # noqa: E402

GROUP = {**{i: 'Passed on 18 Sept (regression check)' for i in PASSED_ON_0918},
         **{i: 'Step 3 target' for i in STEP3_TARGETS},
         **{i: 'Retrieval target' for i in RETRIEVAL_TARGETS}}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cell(text, limit=None):
    text = ' '.join(str(text or '').split()).replace('|', '\\|')
    return text if not limit or len(text) <= limit else text[:limit - 1] + '…'


def claim_verdicts(run):
    body = (run or {}).get('response') or {}
    claims = body.get('claims') or []
    if claims:
        return [(c.get('claim_text'), c.get('verdict')) for c in claims]
    return [(None, body.get('verdict') or body.get('error') or (run or {}).get('harness_error'))]


def render_claim(lines, claim):
    lines.append(f"#### Claim {claim.get('claim_id')}: **{claim.get('verdict')}**")
    lines.append('')
    lines.append(f"> {cell(claim.get('claim_text'))}")
    lines.append('')
    lines.append(f"- **Message:** {cell(claim.get('message'))}")
    lines.append(f"- **Type:** {claim.get('claim_type')} · **Search query:** `{cell(claim.get('search_query'))}`")
    attribution = claim.get('attribution') or {}
    if attribution.get('speaker') or claim.get('claim_type') == 'attributed_statement':
        lines.append(f"- **Speaker:** {attribution.get('speaker') or '(none)'}"
                     f"{' (' + attribution['role'] + ')' if attribution.get('role') else ''}")
    if claim.get('politically_sensitive'):
        lines.append('- **Politically sensitive:** yes')
    if claim.get('review_error'):
        lines.append(f"- **Review error:** `{claim['review_error'].get('reason_code')}` at "
                     f"`{claim['review_error'].get('failed_stage')}`")
    lines.append(f"- **Search:** {claim.get('total_search_results', 0)} results, "
                 f"{claim.get('extracted_articles', 0)} of {claim.get('searched_articles', 0)} articles readable")

    review = claim.get('component_review') or {}
    components = review.get('components') or []
    if components:
        lines.append('')
        lines.append('| # | Component | Decision | Reviewer reason |')
        lines.append('|---|---|---|---|')
        for index, part in enumerate(components):
            decision = part.get('status', '')
            if part.get('evidence_relation') == 'contradicted':
                decision = 'contradicted'
            reason = part.get('review_reason') or ''
            rejections = part.get('event_rejections') or []
            if rejections:
                reason = (reason + ' ' if reason else '') + ' '.join(
                    f"[identity {r.get('status')}: {r.get('reason')}]" for r in rejections)
            lines.append(f"| {index} | {cell(part.get('component'), 160)} | {decision} | {cell(reason, 420)} |")
        cited = [(index, c) for index, part in enumerate(components) for c in part.get('citations') or []]
        if cited:
            lines.append('')
            lines.append('<details><summary>Cited passages</summary>')
            lines.append('')
            for index, citation in cited:
                lines.append(f"- Component {index}: “{cell(citation.get('quote'), 600)}”  ")
                lines.append(f"  <{citation.get('url')}>")
            lines.append('')
            lines.append('</details>')

    sources = claim.get('evidence_sources') or []
    lines.append('')
    if sources:
        lines.append('**Evidence shown to the user:**')
        lines.append('')
        for source in sources:
            label = 'search excerpt' if source.get('evidence_type') == 'search_excerpt' else 'full text'
            lines.append(f"- {source.get('source')} ({label}): [{cell(source.get('title'), 120)}]({source.get('url')})")
    else:
        lines.append('**Evidence shown to the user:** none')
    lines.append('')


def load_runs(folder):
    return {i: read(folder / f'{i}.json') for i in PRIORITY if (folder / f'{i}.json').exists()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', default='results', help='result folder to report')
    parser.add_argument('--previous', help='earlier result folder shown for comparison')
    parser.add_argument('--output', default='REPORT.md')
    parser.add_argument('--findings', default='FINDINGS.md')
    parser.add_argument('--title', default='IRIS priority rerun, 19 September 2026')
    parser.add_argument('--note', default='Step 3 changes are **not** included in this run.')
    args = parser.parse_args()

    cases = {c['id']: c for c in read(AUDIT / 'cases.json')}
    assessments = {a['id']: a for a in read(AUDIT / 'assessment-matrix.json')}
    results_dir = HERE / args.results
    config_path = HERE / 'configuration.json' if args.results == 'results' else results_dir / 'configuration.json'
    config = read(config_path) if config_path.exists() else {}
    runs = load_runs(results_dir)
    previous = load_runs(HERE / args.previous) if args.previous else {}
    review_path = HERE / 'user-review.json'
    review = read(review_path)['cases'] if args.previous == 'results' and review_path.exists() else {}
    baseline = {i: read(AUDIT / 'current-baseline' / f'{i}.json') for i in PRIORITY}

    lines = [f'# {args.title}', '']
    lines.append(f"Code: `{config.get('git_commit', '?')[:7]}` · cache version "
                 f"`{config.get('cache_version', '?')}` · verdict cache bypassed · {len(runs)} of "
                 f"{len(PRIORITY)} cases captured. {args.note}")
    lines.append('')
    if (HERE / args.findings).exists():
        lines.append((HERE / args.findings).read_text(encoding='utf-8').strip())
        lines.append('')
        lines.append('## Case-by-case results')
        lines.append('')
    lines.append('Fill in the **Your assessment** column after checking each case below. Verdicts are '
                 'compared claim by claim with the 18 September baseline; claim extraction can differ between runs, '
                 'so compare the claim text too.')
    lines.append('')
    earlier = ' | Earlier run | Your review of earlier run' if previous else ''
    lines.append(f'| Case | Group | Topic | 18 Sept | 18 Sept verdicts{earlier} | Now | Time | Your assessment |')
    lines.append('|---|---|---|---|---' + ('|---|---' if previous else '') + '|---|---|---|')
    for ident in PRIORITY:
        run = runs.get(ident)
        old = ', '.join(str(v) for _, v in claim_verdicts(baseline[ident]))
        new = ', '.join(str(v) for _, v in claim_verdicts(run)) if run else 'not run'
        seconds = f"{run.get('seconds', 0):.0f}s" if run else ''
        middle = ''
        if previous:
            before = ', '.join(str(v) for _, v in claim_verdicts(previous.get(ident))) if previous.get(ident) else ''
            middle = f" | {before} | {review.get(ident, {}).get('assessment', '')}"
        lines.append(f"| [{ident}](#{ident.lower()}) | {GROUP[ident]} | {cell(assessments[ident]['topic'])} | "
                     f"{assessments[ident]['result']} | {old}{middle} | {new} | {seconds} | |")
    lines.append('')

    for ident in PRIORITY:
        case, assessment, run = cases[ident], assessments[ident], runs.get(ident)
        lines.append(f'## {ident}')
        lines.append('')
        lines.append(f"**{assessment['topic']}** · {GROUP[ident]} · 18 Sept: **{assessment['result']}**")
        lines.append('')
        lines.append(f"- **Expected behavior:** {cell(assessment['expected_behavior'])}")
        lines.append(f"- **18 Sept reason:** {cell(assessment['reason'])}")
        if review.get(ident):
            lines.append(f"- **Your review of the earlier run ({review[ident]['assessment']}):** {cell(review[ident]['note'])}")
        lines.append('')
        lines.append('<details><summary>Full input text</summary>')
        lines.append('')
        lines.append('> ' + case['text'].replace('\n', '\n> '))
        lines.append('')
        lines.append('</details>')
        lines.append('')
        if not run:
            lines.append('_Not captured._')
            lines.append('')
            continue
        body = run.get('response') or {}
        lines.append(f"HTTP {run.get('http_status')} · {run.get('seconds')}s · TRACE `{run.get('trace_id')}` · "
                     f"overall **{body.get('verdict')}** · route `{body.get('content_profile_route')}` · "
                     f"language {body.get('detected_language')}")
        lines.append('')
        if body.get('translated_text') and body.get('translated_text') != body.get('original_text'):
            lines.append('<details><summary>Translation used</summary>')
            lines.append('')
            lines.append('> ' + str(body['translated_text']).replace('\n', '\n> '))
            lines.append('')
            lines.append('</details>')
            lines.append('')
        if body.get('status') == 'processing_error' or run.get('harness_error'):
            lines.append(f"**Technical failure:** `{body.get('reason_code') or run.get('harness_error')}` "
                         f"at `{body.get('failed_stage')}`. {cell(body.get('message'))}")
            lines.append('')
        ignored = body.get('ignored_segments') or []
        if ignored:
            lines.append('**Not checked:**')
            lines.append('')
            for segment in ignored:
                lines.append(f"- _{segment.get('segment_type')}_: {cell(segment.get('text'), 300)}")
            lines.append('')
        claims = body.get('claims') or []
        if not claims and not body.get('status') == 'processing_error':
            lines.append(f"No claims extracted. Message: {cell(body.get('message'))}")
            lines.append('')
        for claim in claims:
            render_claim(lines, claim)
        lines.append('<details><summary>18 Sept claims and verdicts</summary>')
        lines.append('')
        for text, verdict in claim_verdicts(baseline[ident]):
            lines.append(f"- **{verdict}**: {cell(text) if text else '(no claims)'}")
        lines.append('')
        lines.append('</details>')
        lines.append('')
    (HERE / args.output).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{args.output} written for {len(runs)} cases')


if __name__ == '__main__':
    main()
