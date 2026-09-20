"""
IRIS held-out batch: validate posts, run IRIS, write the review sheet, score judgments.

    python evaluation/heldout-batch-1/heldout.py validate
    python evaluation/heldout-batch-1/heldout.py run [--posts H01 H02]
    python evaluation/heldout-batch-1/heldout.py review
    python evaluation/heldout-batch-1/heldout.py score

See README.md in this folder for the procedure.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import logging
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# Every verdict IRIS can answer with, including the ones it gives without checking a claim.
OVERALL = ['Verified', 'Partially Verified', 'Not Found', 'Refuted', 'No Checkable Claims',
           'Opinion Detected', 'Outside Philippine Coverage']
CLAIM_VERDICTS = OVERALL[:4]
NO_CLAIM_VERDICTS = {'No Checkable Claims', 'Opinion Detected', 'Outside Philippine Coverage'}
# Matches pipeline/ocr.py, so a file this runner accepts is a file IRIS can read.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
CATEGORIES = ['news', 'filipino', 'quote', 'false_claim', 'opinion_satire', 'other']
CATEGORY_ALIASES = {'opinion_satire_non_news': 'opinion_satire', 'non_news': 'opinion_satire',
                    'opinion': 'opinion_satire', 'satire': 'opinion_satire',
                    'false': 'false_claim', 'fact_checked': 'false_claim'}


def category_of(value):
    named = re.sub(r'[\s-]+', '_', str(value or '').strip().lower())
    return CATEGORY_ALIASES.get(named, named)


def expected_verdicts(value):
    """One verdict, or the few a post could fairly get: "Opinion Detected or No Checkable Claims"."""
    return [part.strip() for part in re.split(r'\s+or\s+', str(value or '').strip()) if part.strip()]
JUDGMENTS = {
    'correct': 'the verdict and its evidence are right',
    'false_positive': 'Verified/Partially Verified, but the claim is false or the evidence does not support it',
    'false_negative': 'Not Found, but an approved source supports it',
    'wrong_level': 'Verified vs Partially Verified is wrong, otherwise sound',
    'technical': 'Review Failed or another technical failure',
    'ocr_error': 'an image post where OCR misread the text, so IRIS checked the wrong words',
    'cannot_judge': 'you cannot tell what the right answer is',
}
POSITIVE = {'Verified', 'Partially Verified'}
BLOCK_FIELDS = {'text': 'text_lines', 'image text': 'image_text_lines'}
SLOW_SECONDS = 120


# ---------------------------------------------------------------- posts.txt

def parse_posts(path):
    posts, current, mode = [], None, None
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.rstrip()
        if line.startswith('### POST '):
            current = {'id': line[len('### POST '):].strip(), 'fields': {}, 'text_lines': [],
                       'image_text_lines': [], 'claims': [], 'references': []}
            posts.append(current)
            mode = block = None
            continue
        if current is None:
            continue
        if mode == 'block':
            if line.strip() == '>>>':
                mode = None
            else:
                current[block or 'text_lines'].append(raw)
            continue
        if line.startswith('#'):
            continue
        if line.strip() == '<<<':
            # The block belongs to whichever field opened it: TEXT, or IMAGE TEXT.
            mode = 'block'
            continue
        if line.lstrip().startswith('-'):
            item = line.lstrip()[1:].strip()
            if item and mode in ('claims', 'references'):
                current[mode].append(item)
            continue
        match = re.match(r'^([A-Za-z][A-Za-z ]*):\s*(.*)$', line)
        if match:
            key, value = match.group(1).strip().lower(), match.group(2).strip()
            mode = {'expected claims': 'claims', 'references': 'references'}.get(key)
            if key in BLOCK_FIELDS:
                block = BLOCK_FIELDS[key]
            elif mode is None:
                current['fields'][key] = value
    return [finish_post(post) for post in posts]


def finish_post(post):
    fields = post['fields']
    claims = []
    for item in post['claims']:
        text, _, verdict = item.rpartition('=>')
        claims.append({'text': text.strip() if _ else item.strip(), 'verdict': verdict.strip() if _ else ''})
    expected = {'overall': fields.get('expected overall', ''), 'claims': claims,
                'references': post['references']}
    return {
        'id': post['id'], 'page': fields.get('page', ''), 'url': fields.get('post url', ''),
        'date': fields.get('date posted', ''), 'category': category_of(fields.get('category', '')),
        'notes': fields.get('notes', ''), 'text': '\n'.join(post['text_lines']).strip(),
        'image': fields.get('image', ''),
        'image_text': '\n'.join(post['image_text_lines']).strip(),
        'expected': expected,
        'expected_fingerprint': hashlib.sha256(json.dumps(expected, sort_keys=True).encode('utf-8')).hexdigest(),
    }


def runnable(posts):
    # An image post carries its words in the picture, so it needs no TEXT block.
    return [p for p in posts if not p['id'].startswith('EXAMPLE') and (p['text'] or p['image'])]


def ocr_fidelity(post, body):
    """
    How much of the statement recorded for a picture survived OCR, as a 0-1 ratio.

    IMAGE TEXT holds the words that should be checked, not everything printed on the image,
    so this measures whether that statement came through. Branding, hashtags and captions that
    OCR also reads do not count against it.
    """
    from difflib import SequenceMatcher
    words = lambda value: re.findall(r"[^\W_]+", str(value or '').lower())
    wanted, read = words(post.get('image_text')), words((body or {}).get('ocr_text'))
    if not wanted or not read:
        return None
    survived = sum(block.size for block in SequenceMatcher(None, wanted, read).get_matching_blocks())
    return round(survived / len(wanted), 3)


def image_path(folder, post):
    return (folder / post['image']).resolve() if post.get('image') else None


def check_post(post, folder=HERE):
    errors, warnings = [], []
    expected = post['expected']
    wanted = expected_verdicts(expected['overall'])
    picture = image_path(folder, post)
    if picture is not None:
        if not picture.is_file():
            errors.append(f'IMAGE not found: {post["image"]}')
        elif picture.suffix.lower() not in IMAGE_SUFFIXES:
            errors.append(f'IMAGE must be one of {", ".join(sorted(IMAGE_SUFFIXES))}: {post["image"]}')
        elif picture.stat().st_size > MAX_IMAGE_BYTES:
            errors.append(f'IMAGE is larger than the {MAX_IMAGE_BYTES} byte OCR limit: {post["image"]}')
        if not post.get('image_text'):
            warnings.append('no IMAGE TEXT: without the words the picture shows, a verdict on a '
                            'misread claim cannot be told from a verdict on the right one')
    if not wanted or any(verdict not in OVERALL for verdict in wanted):
        errors.append(f"EXPECTED OVERALL must be one of: {', '.join(OVERALL)}"
                      + ' (or two of them written as "A or B" when either would be fair)')
    if not set(wanted) & NO_CLAIM_VERDICTS:
        if not expected['claims'] and not post.get('image_text'):
            # Optional: EXPECTED OVERALL and REFERENCES still record a judgment made before the
            # run. Per-claim expectations are what back the "claims IRIS missed" count, so the
            # runner asks for them without refusing a post that has none. An image post that
            # records what the picture says can be compared without them.
            warnings.append('no EXPECTED CLAIMS: the missed-claim count for this post rests on '
                            'your memory of the post rather than on what you wrote beforehand')
        for claim in expected['claims']:
            if claim['verdict'] not in CLAIM_VERDICTS:
                errors.append('claim needs "=> " and one of ' + ', '.join(CLAIM_VERDICTS)
                              + f": {claim['text'][:60]}")
        if not expected['references']:
            warnings.append('no REFERENCES listed')
    if post['category'] not in CATEGORIES:
        warnings.append(f"Category should be one of: {', '.join(CATEGORIES)}")
    return errors, warnings


def validate(folder, quiet=False):
    posts = runnable(parse_posts(folder / 'posts.txt'))
    ok = True
    for post in posts:
        errors, warnings = check_post(post, folder)
        ok = ok and not errors
        if not quiet or errors:
            status = 'ERROR' if errors else 'ok'
            shown = post['image'] if post['image'] else ' '.join(post['text'].split())[:60]
            print(f"{post['id']:6s} {status:5s} {'image' if post['image'] else 'text':5s} "
                  f"{post['category'] or '-':15s} {post['expected']['overall'] or '-':20s} "
                  f"{len(post['expected']['claims'])} claim(s) | {shown}")
            for message in errors:
                print('        error:', message)
            for message in warnings:
                print('        warning:', message)
    if not posts:
        print('No posts with text yet. Paste posts into posts.txt first.')
    return posts, ok and bool(posts)


# ---------------------------------------------------------------- run

def run(folder, only=None):
    posts, ok = validate(folder, quiet=True)
    if not ok:
        print('Fix the errors above before running. Expected results must be written first.')
        return 1
    results = folder / 'results'
    results.mkdir(exist_ok=True)
    sys.path.insert(0, str(ROOT / 'iris-backend'))
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'iris-backend' / '.env')
    import app

    logging.basicConfig(filename=folder / 'services.log', level=logging.INFO, force=True)
    app.app.config.update(IRIS_TRACE_ENABLED=True, IRIS_TRACE_ARTIFACTS=True,
                          IRIS_TRACE_PATH=str(folder / 'traces.sqlite3'))
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    with patch.object(app, 'get_cached_verdict', return_value=None), \
         patch.object(app, 'save_cached_verdict', return_value=None):
        for post in posts:
            if only and post['id'] not in only:
                continue
            target = results / f"{post['id']}.json"
            if target.exists():
                print('KEPT   ' + post['id'] + ' (delete its result file to rerun)', flush=True)
                continue
            started = datetime.now(timezone.utc).isoformat()
            before = time.monotonic()
            picture = image_path(folder, post)
            try:
                with app.app.test_client() as client:
                    if picture is not None:
                        # The image IS the post: IRIS reads it exactly as the phone app would.
                        payload = {'image_base64': base64.b64encode(picture.read_bytes()).decode('ascii'),
                                   'debug': True, 'platform': 'heldout-batch-1'}
                        response = client.post('/verify-image', json=payload)
                    else:
                        response = client.post('/verify', json={'text': post['text'], 'debug': True,
                                                                'platform': 'heldout-batch-1'})
                result = {'http_status': response.status_code, 'trace_id': response.headers.get('X-IRIS-Trace-ID'),
                          'response': response.get_json()}
            except Exception as error:
                result = {'http_status': None, 'harness_error': f'{type(error).__name__}: {error}', 'response': None}
            finally:
                store = app.app.extensions.get('iris_trace_store')
                if store:
                    store.flush()
            result.update(post_id=post['id'], started_utc=started, seconds=round(time.monotonic() - before, 3),
                          git_commit=commit, cache_version=app.RESULT_CACHE_VERSION,
                          cache_policy='reads and writes bypassed', post=post,
                          input_type='image' if picture is not None else 'text')
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            body = result.get('response') or {}
            line = {'post': post['id'], 'http': result['http_status'], 'seconds': result['seconds'],
                    'verdicts': [c.get('verdict') for c in body.get('claims', [])] or [body.get('verdict')]}
            if result['input_type'] == 'image':
                line['ocr'] = {'status': body.get('ocr_status'), 'words': body.get('ocr_word_count'),
                               'confidence': body.get('ocr_confidence'), 'low': body.get('ocr_low_confidence')}
            print(json.dumps(line, ensure_ascii=False), flush=True)
            time.sleep(3)
    store = app.app.extensions.get('iris_trace_store')
    if store:
        store.close()
    print('RUN FINISHED')
    return 0


# ---------------------------------------------------------------- review

def load_results(folder):
    results = {}
    for path in sorted((folder / 'results').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        results[data['post_id']] = data
    return results


def parse_review(path):
    """{post_id: {'routing': str, 'missed': str, 'claims': {n: judgment}, 'comment': str}}."""
    review, current = {}, None
    if not path.exists():
        return review
    for line in path.read_text(encoding='utf-8').splitlines():
        header = re.match(r'^### POST (\S+)', line)
        if header:
            current = review.setdefault(header.group(1), {'routing': '', 'missed': '', 'claims': {}, 'comment': ''})
            continue
        if current is None:
            continue
        for key, name in (('Routing:', 'routing'), ('Missed claims:', 'missed'), ('Comment:', 'comment')):
            if line.strip().startswith(key):
                current[name] = line.strip()[len(key):].strip()
        judged = re.match(r'^\s*Judgment \(claim (\d+)\):\s*(.*)$', line)
        if judged:
            current['claims'][int(judged.group(1))] = judged.group(2).strip()
    return review


def claims_of(result):
    body = result.get('response') or {}
    return body.get('claims') or []


def write_review(folder):
    posts = {p['id']: p for p in runnable(parse_posts(folder / 'posts.txt'))}
    results = load_results(folder)
    previous = parse_review(folder / 'review.txt')
    lines = ['# IRIS held-out batch 1: your judgment sheet',
             '#',
             '# For each post fill in Routing, Missed claims and one Judgment per claim. Existing entries are',
             '# kept when this sheet is regenerated.',
             '# Routing:       correct | wrong   (did IRIS rightly check, or rightly decline to check, this post?)',
             '# Missed claims: number of checkable statements IRIS did not extract (0 if none)',
             '# Judgment:',
             *[f'#   {name:15s} {meaning}' for name, meaning in JUDGMENTS.items()],
             '']
    for post_id, result in results.items():
        post = posts.get(post_id) or result['post']
        body = result.get('response') or {}
        old = previous.get(post_id, {'routing': '', 'missed': '', 'claims': {}, 'comment': ''})
        changed = post.get('expected_fingerprint') != result['post'].get('expected_fingerprint')
        lines.append(f"### POST {post_id}   IRIS: {body.get('verdict') or body.get('error') or result.get('harness_error')}"
                     f" | {len(claims_of(result))} claim(s) | {result.get('seconds', 0):.0f}s")
        lines.append(f"Category: {post.get('category')} | You expected: {post['expected']['overall']}"
                     + ('   (!) expected results edited after this run' if changed else ''))
        for claim in post['expected']['claims']:
            lines.append(f"  expected: {claim['text'][:150]} => {claim['verdict']}")
        lines.append(f"Routing: {old['routing']}")
        lines.append(f"Missed claims: {old['missed']}")
        for n, claim in enumerate(claims_of(result), 1):
            sources = ', '.join(s['url'] for s in claim.get('evidence_sources') or []) or 'none'
            lines.append(f"CLAIM {n}: {' '.join(str(claim.get('claim_text')).split())[:220]}")
            lines.append(f"  IRIS: {claim.get('verdict')} | evidence: {sources}")
            lines.append(f"  Judgment (claim {n}): {old['claims'].get(n, '')}")
        lines.append(f"Comment: {old['comment']}")
        lines.append('')
    (folder / 'review.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    write_report(folder, posts, results)
    print(f'review.txt and REPORT.md written for {len(results)} post(s)')


def write_report(folder, posts, results):
    report_dir = ROOT / 'evaluation' / 'rerun-20260919'
    sys.path.insert(0, str(report_dir))
    spec = importlib.util.spec_from_file_location('iris_build_report', report_dir / 'build_report.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    lines = ['# IRIS held-out batch 1: results', '']
    for post_id, result in results.items():
        post = posts.get(post_id) or result['post']
        body = result.get('response') or {}
        lines += [f'## {post_id}', '',
                  f"{post.get('page') or ''} · {post.get('date') or ''} · category `{post.get('category')}` · "
                  f"{post.get('url') or ''}", '',
                  f"- **You expected:** {post['expected']['overall']}"]
        lines += [f"  - {c['text']} => {c['verdict']}" for c in post['expected']['claims']]
        lines += [f"  - reference: <{r}>" for r in post['expected']['references']]
        lines += ['', '<details><summary>Post text</summary>', '',
                  '> ' + (post['text'] or '(the post is the image)').replace('\n', '\n> '),
                  '', '</details>', '']
        if result.get('input_type') == 'image':
            # An image result cannot be judged without seeing the words OCR actually produced.
            fidelity = ocr_fidelity(post, body)
            lines += [f"**Image:** `{post.get('image')}` · OCR {body.get('ocr_status')} · "
                      f"{body.get('ocr_word_count')} words · confidence {body.get('ocr_confidence')}"
                      + (f" · {fidelity:.0%} of the statement's words survived" if fidelity is not None else '')
                      + (' · **low confidence**' if body.get('ocr_low_confidence') else ''), '']
            if post.get('image_text'):
                lines += ['<details><summary>What the picture says (you)</summary>', '',
                          '> ' + post['image_text'].replace('\n', '\n> '), '', '</details>', '']
            lines += ['<details><summary>What OCR read</summary>', '',
                      '> ' + str(body.get('ocr_text') or '').replace('\n', '\n> '), '', '</details>', '']
        lines += [f"HTTP {result.get('http_status')} · {result.get('seconds')}s · TRACE `{result.get('trace_id')}` · "
                  f"overall **{body.get('verdict')}** · commit `{str(result.get('git_commit'))[:7]}`", '']
        ignored = body.get('ignored_segments') or []
        if ignored:
            lines += ['**Not checked:**', ''] + [f"- _{s.get('segment_type')}_: {builder.cell(s.get('text'), 300)}"
                                                 for s in ignored] + ['']
        for claim in claims_of(result):
            builder.render_claim(lines, claim)
    (folder / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- score

def score(folder):
    posts = {p['id']: p for p in runnable(parse_posts(folder / 'posts.txt'))}
    results = load_results(folder)
    review = parse_review(folder / 'review.txt')
    problems, counts, by_category, by_input = [], {name: 0 for name in JUDGMENTS}, {}, {}
    routing = {'correct': 0, 'wrong': 0}
    missed, positives_judged, false_claim_posts, false_claim_fp = 0, 0, 0, 0
    for post_id, result in results.items():
        post = posts.get(post_id) or result['post']
        entry = review.get(post_id, {'routing': '', 'missed': '', 'claims': {}})
        category = post.get('category') or 'other'
        bucket = by_category.setdefault(category, {'posts': 0, 'correct': 0, 'judged': 0, 'false_positive': 0})
        bucket['posts'] += 1
        kind = result.get('input_type') or 'text'
        input_bucket = by_input.setdefault(kind, {'posts': 0, 'correct': 0, 'judged': 0, 'false_positive': 0})
        input_bucket['posts'] += 1
        if post.get('expected_fingerprint') != result['post'].get('expected_fingerprint'):
            problems.append(f'{post_id}: expected results were edited after IRIS ran (evaluation is no longer blind)')
        if entry['routing'] in routing:
            routing[entry['routing']] += 1
        else:
            problems.append(f'{post_id}: Routing not filled in (correct | wrong)')
        if entry['missed'].isdigit():
            missed += int(entry['missed'])
        else:
            problems.append(f'{post_id}: Missed claims not filled in (a number)')
        post_fp = False
        for n, claim in enumerate(claims_of(result), 1):
            judgment = entry['claims'].get(n, '')
            if judgment not in JUDGMENTS:
                problems.append(f'{post_id} claim {n}: Judgment missing or not one of {", ".join(JUDGMENTS)}')
                continue
            counts[judgment] += 1
            if judgment != 'cannot_judge':
                bucket['judged'] += 1
                bucket['correct'] += judgment == 'correct'
                input_bucket['judged'] += 1
                input_bucket['correct'] += judgment == 'correct'
            if claim.get('verdict') in POSITIVE and judgment != 'cannot_judge':
                positives_judged += 1
            if judgment == 'false_positive':
                bucket['false_positive'] += 1
                input_bucket['false_positive'] += 1
                post_fp = True
        if category == 'false_claim':
            false_claim_posts += 1
            false_claim_fp += post_fp

    judged = sum(counts.values()) - counts['cannot_judge']
    times = [r.get('seconds') or 0 for r in results.values()]
    technical_posts = sum(1 for r in results.values() if r.get('http_status') != 200)
    pct = lambda part, whole: f'{part}/{whole} ({100 * part / whole:.0f}%)' if whole else f'{part}/0'
    lines = ['# IRIS held-out batch 1: scores', '',
             f'Posts run: {len(results)} · commit(s): '
             + ', '.join(sorted({str(r.get("git_commit"))[:7] for r in results.values()})), '']
    if problems:
        lines += ['**Incomplete or flagged, fix these for a final score:**', ''] + [f'- {p}' for p in problems] + ['']
    lines += ['| Measure | Result |', '|---|---|',
              f'| Claim accuracy (correct / judged) | {pct(counts["correct"], judged)} |',
              f'| False positives (of judged claims) | {pct(counts["false_positive"], judged)} |',
              f'| False positives among Verified/Partially Verified verdicts | {pct(counts["false_positive"], positives_judged)} |',
              f'| False negatives (of judged claims) | {pct(counts["false_negative"], judged)} |',
              f'| Wrong verification level | {pct(counts["wrong_level"], judged)} |',
              f'| Technical failures (claims) | {pct(counts["technical"], judged)} |',
              f'| OCR misreads (claims) | {pct(counts["ocr_error"], judged)} |',
              f'| Cannot judge (excluded above) | {counts["cannot_judge"]} |',
              f'| Routing correct (posts) | {pct(routing["correct"], routing["correct"] + routing["wrong"])} |',
              f'| Checkable statements IRIS missed | {missed} |',
              f'| False-claim posts with any false positive | {pct(false_claim_fp, false_claim_posts)} |',
              f'| Requests that failed (HTTP not 200) | {technical_posts} |',
              f'| Response time median / max | {statistics.median(times):.0f}s / {max(times):.0f}s |' if times else '| Response time | - |',
              f'| Requests over {SLOW_SECONDS}s (Android limit) | {sum(t > SLOW_SECONDS for t in times)} |', '',
              '## By category', '', '| Category | Posts | Claim accuracy | False positives |', '|---|---|---|---|']
    for category, bucket in sorted(by_category.items()):
        lines.append(f"| {category} | {bucket['posts']} | {pct(bucket['correct'], bucket['judged'])} | {bucket['false_positive']} |")
    fidelities = [f for f in (ocr_fidelity(posts.get(pid) or r['post'], r.get('response') or {})
                              for pid, r in results.items()) if f is not None]
    if fidelities:
        lines += ['', '## Reading the pictures', '',
                  f'| Image posts compared | {len(fidelities)} |', '|---|---|',
                  f'| Words of the recorded statement that survived OCR, median | {statistics.median(fidelities):.0%} |',
                  f'| Worst | {min(fidelities):.0%} |']
    lines += ['', '## By input', '', '| Input | Posts | Claim accuracy | False positives |', '|---|---|---|---|']
    for kind, bucket in sorted(by_input.items()):
        lines.append(f"| {kind} | {bucket['posts']} | {pct(bucket['correct'], bucket['judged'])} | {bucket['false_positive']} |")
    lines += ['', 'Development cases are excluded by design. Scores describe this batch only, on the commits listed, '
              'with the verdict cache bypassed.']
    (folder / 'SCORES.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['validate', 'run', 'review', 'score'])
    parser.add_argument('--posts', nargs='*', help='only these post IDs (run)')
    parser.add_argument('--dir', default=str(HERE), help=argparse.SUPPRESS)
    args = parser.parse_args()
    folder = Path(args.dir)
    if args.command == 'validate':
        _, ok = validate(folder)
        return 0 if ok else 1
    if args.command == 'run':
        return run(folder, args.posts)
    if args.command == 'review':
        write_review(folder)
        return 0
    return score(folder)


if __name__ == '__main__':
    sys.exit(main())
