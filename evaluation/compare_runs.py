"""
Compares two runs of the same cases, claim by claim, and says what moved.

    python evaluation/compare_runs.py BEFORE_DIR AFTER_DIR [--ids A01 A02 ...]

Claims are paired by the similarity of their text, because extraction does not always word a
claim the same way twice; a claim with no counterpart is reported as added or dropped rather
than forced onto the nearest one. Offline: reads saved JSON only.
"""

import argparse
import difflib
import json
import statistics
from pathlib import Path

MATCH_THRESHOLD = 0.6
SLOW_SECONDS = 90


def load(folder):
    runs = {}
    for path in sorted(Path(folder).glob('*.json')):
        if path.name == 'configuration.json':
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        ident = data.get('case_id') or data.get('post_id') or path.stem
        runs[ident] = data
    return runs


def claims_of(run):
    return [claim for claim in ((run or {}).get('response') or {}).get('claims') or []]


def pair(before, after):
    """Greedy pairing by text similarity, best pairs first."""
    scored = sorted(
        ((difflib.SequenceMatcher(None, str(b.get('claim_text')), str(a.get('claim_text'))).ratio(), i, j)
         for i, b in enumerate(before) for j, a in enumerate(after)),
        reverse=True)
    used_b, used_a, pairs = set(), set(), []
    for ratio, i, j in scored:
        if ratio < MATCH_THRESHOLD or i in used_b or j in used_a:
            continue
        used_b.add(i)
        used_a.add(j)
        pairs.append((before[i], after[j]))
    dropped = [claim for i, claim in enumerate(before) if i not in used_b]
    added = [claim for j, claim in enumerate(after) if j not in used_a]
    return pairs, dropped, added


def seconds(runs):
    return [run.get('seconds') for run in runs.values() if isinstance(run.get('seconds'), (int, float))]


def timing(label, values):
    if not values:
        return f'{label}: no timings'
    return (f'{label}: median {statistics.median(values):.0f}s, max {max(values):.0f}s, '
            f'{sum(v > SLOW_SECONDS for v in values)} of {len(values)} over {SLOW_SECONDS}s')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('before')
    parser.add_argument('after')
    parser.add_argument('--ids', nargs='*')
    args = parser.parse_args()

    before, after = load(args.before), load(args.after)
    ids = args.ids or sorted(set(before) & set(after))
    unchanged = moved = added_total = dropped_total = 0
    strategies = {}

    for ident in ids:
        b_run, a_run = before.get(ident), after.get(ident)
        if a_run is None:
            print(f'{ident}: not in the new run')
            continue
        for claim in claims_of(a_run):
            strategy = claim.get('retrieval_strategy') or 'none'
            strategies[strategy] = strategies.get(strategy, 0) + 1
        if b_run is None:
            print(f'{ident}: NEW -> {[c.get("verdict") for c in claims_of(a_run)] or [(a_run.get("response") or {}).get("verdict")]}')
            continue

        b_body, a_body = b_run.get('response') or {}, a_run.get('response') or {}
        pairs, dropped, added = pair(claims_of(b_run), claims_of(a_run))
        changes = []
        for b, a in pairs:
            if b.get('verdict') == a.get('verdict'):
                unchanged += 1
            else:
                moved += 1
                changes.append(f'    MOVED  {b.get("verdict")} -> {a.get("verdict")} [{a.get("retrieval_strategy")}]'
                               f'  {str(a.get("claim_text"))[:95]}')
        for claim in dropped:
            dropped_total += 1
            changes.append(f'    DROPPED {claim.get("verdict")}  {str(claim.get("claim_text"))[:95]}')
        for claim in added:
            added_total += 1
            changes.append(f'    ADDED   {claim.get("verdict")} [{claim.get("retrieval_strategy")}]'
                           f'  {str(claim.get("claim_text"))[:95]}')
        overall = (f'{b_body.get("verdict")} -> {a_body.get("verdict")}'
                   if b_body.get('verdict') != a_body.get('verdict') else b_body.get('verdict'))
        marker = '*' if changes or b_body.get('verdict') != a_body.get('verdict') else ' '
        print(f'{marker} {ident}: {overall}  ({b_run.get("seconds", 0):.0f}s -> {a_run.get("seconds", 0):.0f}s)')
        for line in changes:
            print(line)

    print(f'\nclaims: {unchanged} unchanged, {moved} moved, {added_total} added, {dropped_total} dropped')
    print('retrieval paths in the new run:', dict(sorted(strategies.items())))
    print(timing('before', [before[i]['seconds'] for i in ids if i in before and isinstance(before[i].get('seconds'), (int, float))]))
    print(timing('after ', [after[i]['seconds'] for i in ids if i in after and isinstance(after[i].get('seconds'), (int, float))]))


if __name__ == '__main__':
    main()
