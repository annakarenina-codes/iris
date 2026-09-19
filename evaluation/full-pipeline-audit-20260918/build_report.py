"""Assemble one evidence-linked assessment from saved runs and human review notes."""
import hashlib
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit

from collect import HERE, ROOT, read, write


def canonical(url):
    parts = urlsplit(url or '')
    return parts.netloc.lower().removeprefix('www.') + parts.path.rstrip('/')


def main():
    cases = read(HERE / 'cases.json')
    expected = {c['id']: c for c in read(HERE / 'expectations.json')}
    observations = {c['id']: c for c in read(HERE / 'observations.json')}
    notes = read(HERE / 'review_notes.json')
    manifest = read(HERE / 'baseline-manifest.json')
    changed = [path for path, digest in manifest['production_hashes'].items()
               if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest]
    assert not changed, f'Production changed during baseline: {changed}'
    for case in cases:
        runpath = HERE / 'current-baseline' / (case['id'] + '.json')
        if runpath.exists():
            assert read(runpath)['input_sha256'] == case['input_sha256']
    refs = {}
    for path in (HERE / 'reference-controls').glob('*.json'):
        value = read(path)
        if 'extraction' in value:
            refs[path.stem] = value
    matrix = []
    for case in cases:
        ident = case['id']
        obs = observations.get(ident)
        if not obs:
            continue
        used = {canonical(cit['url']) for c in obs['claims']
                for part in c['review'].get('components', [])
                for cit in part.get('citations', [])}
        discovered = {canonical(u) for u in obs['search_urls']}
        extracted = {canonical(a['url']) for a in obs['article_extraction'] if a['status'] == 'extracted'}
        known = []
        for key in expected[ident]['reference_ids']:
            ref = refs.get(key)
            if not ref:
                continue
            u = canonical(ref['url'])
            known.append({'reference': key, 'url': ref['url'],
                          'in_recorded_search': u in discovered,
                          'extracted_in_run': u in extracted, 'credited': u in used,
                          'direct_status': ref['extraction'].get('status'),
                          'direct_words': ref['extraction'].get('word_count'),
                          'direct_error': ref['extraction'].get('error')})
        matrix.append({**expected[ident], **notes[ident], 'http': obs['http'],
                       'seconds': obs['seconds'], 'trace_id': obs['trace_id'],
                       'capture': obs['capture'], 'known_references': known,
                       'observed_verdicts': [c['verdict'] for c in obs['claims']] or [obs['top_verdict']]})
    write(HERE / 'assessment-matrix.json', matrix)
    counts = Counter(x['result'] for x in matrix)
    first = Counter(x['stage'] for x in matrix if x['stage'])
    affected = Counter(stage for x in matrix for stage in set([x['stage']] + x['contributors']) if stage)
    summary = {'created_utc': datetime.now(timezone.utc).isoformat(), 'cases_expected': len(cases),
               'cases_completed': len(matrix), 'assessment_counts': dict(counts),
               'first_failure_counts': dict(first), 'http_counts': dict(Counter(x['http'] for x in matrix)),
               'affected_stage_counts': dict(affected),
               'production_hashes_unchanged': True,
               'interpretation': 'Development-set behavioral audit, not an unbiased real-world accuracy estimate.'}
    write(HERE / 'summary.json', summary)
    lines = ['# IRIS: Consolidated Pipeline Assessment', '',
             'Audit date: 18 September 2026. This is a development-set diagnosis, not a production accuracy claim.', '',
             '## Start Here', '',
             f"Fresh runs saved: **{len(matrix)} of {len(cases)}**. "
             f"**{counts['Passed']} passed; {counts['Failed']} failed; {counts['Cannot yet judge']} cannot yet judge.**", '',
             'A pass means the specified behavior and cited support were checked in this run. A failure means at least one concrete defect or technical failure was found. Cannot yet judge means the remaining reference evidence is insufficient; it does not mean the post is false.', '',
             'The strongest recurring safety issue is loss of context between a whole assertion and its smaller components. Search also has gaps, but not every Not Found result is a search failure.', '',
             '## What Was Tested', '',
             '- Original ten requests (A01-A10), second batch of sixteen (B01-B16), and eight saved recent text inputs (C01-C08).',
             '- Current backend source files were hashed and frozen. Existing source changes were preserved. No production code was changed for this audit.',
             '- Each request used the configured live services through the Flask verification route with debug capture; verdict-cache reads and writes were bypassed.',
             '- Recorded models: gpt-4o-mini for the default model, gpt-4.1-2025-04-14 for claim coverage and evidence review. The high-stakes reviewer is already using the stronger configured model; these defects cannot be explained as mini-only verdicts.',
             '- Requests were sequential. These are current reruns, not reconstructed historical executions. New blind-test outcomes without TRACE remain user reports.',
             '- Known-URL controls bypass search deliberately. They test downloading/extraction and, separately, evidence review. They do not count as automatic retrieval success.',
             '- All cases were previously examined during development. They are not a held-out benchmark. OCR, Android and extension UI are not covered by these text runs.', '',
             '## Priority Order', '',
             '1. Preserve subject, event, time and qualifiers in every evidence component. A detached arrested or causes fragment must not receive its own verdict credit.',
             '2. Make attribution matching recognize supported name variants and resolve court/institution references from context, without inventing a speaker or accepting topic overlap.',
             '3. Reconcile evidence selections: an exact date passage already accepted for event identity must be available to the final qualifier check.',
             '   Also distinguish omission from contradiction: one article not repeating a quote does not invalidate another article that directly contains it.',
             '4. Repair targeted retrieval/extraction failures using the known-reference controls, with bounded alternative queries and publisher-page handling.',
             '5. Repair screening/coverage errors, then rerun these exact regressions and a genuinely new held-out batch.',
             '6. Handle rate limits with measured request/token scheduling. A larger model alone does not fix deterministic gates, absent evidence or discarded context.', '',
             '## First Confirmed Failure', '',
             'One primary stage per failed case is counted below. Contributors may overlap. This is not a count of every error and is not a universal ranking for all possible news.', '',
             '| Stage | Cases |', '|---|---:|']
    lines += [f'| {stage} | {count} |' for stage, count in first.most_common()]
    lines += ['', 'Including contributing defects (overlapping cases): ' + '; '.join(f'{k}: {v}' for k, v in affected.most_common()) + '.',
              'Technical failures are counted separately from incorrect factual judgments. A03 has both a demonstrated extraction omission and a later rate-limit failure; A05 has no completed verdict to grade.', '',
              '## Compared With Earlier Records', '',
              '- Previously blocked translation/screening inputs now reach verification in several cases, including Bea Borres, EDSA, the peso and National Artists. This is progress, not proof their final results all pass.',
              '- Malacanang attribution now works in B02/B03. The different Robinhood/Robin and null judges failures remain, so attribution is not completely solved.',
              '- A05 now extracts the quoted statements and bail fact, but the live run fails at evidence review due to a rate limit.',
              '- The exact fan-meeting, Eala and Rene articles are now retrieved. Fan-meeting and Eala still suffer downstream rejection; Rene succeeds.',
              '- DepEd remains a known-article retrieval gap. Other reference gaps are not automatically counted as search misses.',
              '- Historical snippets, prior versions and fresh runs are not directly interchangeable. This comparison is qualitative; it is not an old-versus-new accuracy percentage.']
    lines += ['', '## Case Summary', '', '| ID | Topic | Assessment | First failure | Reason |', '|---|---|---|---|---|']
    lines += [f"| {x['id']} | {x['topic']} | {x['result']} | {x['stage'] or '-'} | {x['reason']} |" for x in matrix]
    lines += ['', '## Stage Reach and Limits', '',
              'Counts below use saved spans or dependency artifacts. Missing capture is unknown, not proof a stage did not run. Later stages may be undercounted. Aggregate call durations are not wall-clock stage durations because article work is parallel.', '',
              '| Stage | Runs with execution evidence | Baseline runs |', '|---|---:|---:|']
    for stage in ['translation','screening','claim_extraction','retrieval','article_extraction','attribution','evidence_review','delivery']:
        n = sum(o['stages'][stage]['reached'] for o in observations.values())
        lines.append(f'| {stage} | {n} | {len(observations)} |')
    lines += ['', 'TRACE has bounded event capture (1 MiB per request and 64 KiB per event). Many traces are marked partial. Full saved response files and dependency artifacts help, but cannot recover information that was never captured. Partial capture is not the same as a failed verification.', '',
              '## Known Article Checks', '',
              'Yes means the exact normalized URL was recorded. Credited means at least one component used it, not that every claim admitted it (A02 is an important example). No means it was not observed in that saved collection; with partial capture, absence alone is not definitive proof it was never seen. Direct word count does not by itself prove relevant or correct extraction.', '',
              '| Case | Reference | In search | Extracted in run | Credited | Direct extraction |', '|---|---|---|---|---|---|']
    for row in matrix:
        for ref in row['known_references']:
            flags = ['Yes' if ref[k] else 'No' for k in ['in_recorded_search','extracted_in_run','credited']]
            lines.append(f"| {row['id']} | [{ref['reference']}]({ref['url']}) | {' | '.join(flags)} | {ref['direct_status']}, {ref['direct_words']} words |")
    lines += ['', '## Controlled Evidence Reviews', '',
              'The following runs were given a known article. They are diagnostic model outputs, not independent truth labels and not retrieval passes. Full-input controls may include editorial wording that would normally be screened out.', '']
    for path in sorted((HERE / 'reference-controls').glob('*-review.json')):
        control = read(path)
        review = control.get('review', {})
        lines.append(f"- {control['case_id']}: {review.get('verdict') or control.get('reason') or review.get('error_code')}; status {review.get('status', control.get('status'))}. [Saved control](reference-controls/{path.name}).")
    lines += ['', 'What these controls mean:', '',
              '- C04 is the clearest retrieval isolation: supplying the exact GMA article changes the evidence review to Verified for the substantive statements. It does not prove the normal search can find it or repair the per-claim speaker gate.',
              '- C08 still misses the meaning of This is fake after VERA is supplied. Retrieval is therefore not its only defect.',
              '- A07 remains Partially Verified, but its supported components change: the control rejects personal background and accepts the funds rationale, opposite to parts of the baseline. The label alone hides unstable reasoning. These runs differ in evidence pools and are not a pure repeatability experiment.',
              '- B15 uses the June reference, which lacks the explicit year in its body. The baseline also found an August article containing 2026. The control therefore cannot be compared as an identical-evidence test; it illustrates how passage availability changes the result.',
              '- C07 correctly receives no support from the supplied Spotify article for the September 17 event. Related celebrity coverage is not a substitute for that specific appearance.', '',
              '## Search Findings in Plain Language', '',
              'There are two clear failed cases with known, readable target articles absent from recorded retrieval: **C04 (DepEd)** and **C08 (VERA/Poquiz)**. This is a lower bound from checked references, not an estimate that only two of all 34 inputs had imperfect search. A09 also has a missing exact-rate reference and a thin direct extraction, so its search-versus-extraction contribution is not isolated.', '',
              'A02, B15, C02 and C03 demonstrate the opposite situation: relevant articles reached the system, but later matching or selection failed. Searching more would not by itself repair these specific defects.', '',
              'Current search code requests five candidates per publisher and extracts the first two. The language backup triggers on fewer than two total results, not on whether usable evidence was found. Therefore unrelated hits can suppress backup search, and a relevant lower-ranked result can be left unread. These are verified code risks, not proof that either caused every missed article.', '',
              '## Next Fix Acceptance Tests', '',
              '| Fix | Must improve | Must not regress |', '|---|---|---|',
              '| Context-preserving components and evidence decisions | B05 must not credit a different arrest; B12 must not split causes; C02/C03 must accept direct support without requiring every passage to repeat it | Keep genuine partial support when a real factual component is unsupported |',
              '| Attribution resolution | A02 Robinhood/Robin with supporting identity context; B04 judges/ICC context; C06 explicit named speaker retained | B01 must not borrow Matibag statements from another investigation |',
              '| Citation selection and qualifiers | B15 retain the explicit 2026 passage through the final check | A09 must not substitute another trading session; C07 must not substitute a 2022 interview |',
              '| Targeted search recovery | Retrieve the known C04 and C08 target URLs automatically, then extract their relevant passages | Do not count manual URL injection as a retrieval pass or broaden the approved publisher policy silently |',
              '| Coverage and routing | Retain A03 advocacy and C08 denial context; stop B07/B16 appropriately | Keep A05 quotations/bail and the passing B06/B09/B13 exclusions |',
              '| Reliability | A03/A05 complete or return an explicit technical error with reproducible service diagnostics | Never turn a rate limit into a factual Not Found verdict |']
    lines += ['', '## Evidence and Reproduction', '',
              '- [Case inputs](cases.json), [expected behavior](expectations.json), [machine-readable assessment](assessment-matrix.json), [source/config baseline](baseline-manifest.json).',
              '- [Observed stage data](observations.json). Each case below links its raw result and TRACE ID; historical captures are preserved separately.',
              '- No percentage here should be described as real-world IRIS accuracy. Reference gaps, previously tuned cases, partial captures and rate-limited requests prevent that conclusion.', '',
              '## Per-Case Record', '']
    for row in matrix:
        obs = observations[row['id']]
        lines += [f"### {row['id']}: {row['topic']}", '', f"**{row['result']}**. {row['reason']}", '',
                  f"Expected: {row['expected_behavior']}", '',
                  f"Observed: HTTP {row['http']}; {row['seconds']} seconds; TRACE `{row['trace_id']}`; capture {row['capture']}.",
                  f"[Saved response](current-baseline/{row['id']}.json) | [TRACE snapshot](current-trace-snapshots/{row['id']}.json)", '']
        for claim in obs['claims']:
            lines.append(f"- **{claim['verdict']}**: {claim['text']}")
        if not obs['claims']:
            lines.append(f"- No delivered claims. Result/error: {obs['top_verdict'] or obs['error']}.")
        lines.append('')
    lines += ['## Beginner-Friendly Terms', '',
              '- **Retrieval:** searching for candidate articles. Finding the same topic is not proof.',
              '- **Extraction:** reading article text, or separating a post into claims. These are different steps.',
              '- **Attribution:** checking who said something, where and when. Confirming a quote does not prove its underlying opinion.',
              '- **Component:** a smaller factual part of a claim. It must keep enough context to identify the same event.',
              '- **Entailment/evidence matching:** whether a passage actually supports that particular assertion.',
              '- **False positive:** accepting evidence that does not justify a positive verdict.',
              '- **False negative:** rejecting available evidence that does support the assertion.',
              '- **Reference control:** a test where we supply an article on purpose to isolate later stages.',
              '- **Rate limit:** a service refusing more work temporarily. It is a technical failure, not Not Found.',
              '- **Held-out:** new cases not used while designing or fixing the system.', '',
              '## Remaining User Decisions', '',
              'No new broad policy decision is needed to fix the confirmed defects above. Keep the already approved nickname limitation, publisher sections and strict evidence requirements. Exact-event evidence is still needed for unresolved Samaniego and Matibag attributions and any uncaptured blind tests not represented by the saved inputs. Do not guess their labels.']
    (HERE / 'IRIS-Pipeline-Assessment.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(summary)


if __name__ == '__main__':
    main()
