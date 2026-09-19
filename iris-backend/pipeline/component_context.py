"""Ground component context in input spans; source context is never evidence."""
import re
from copy import deepcopy

FIELDS = ('subject', 'action', 'event', 'time', 'negation', 'speaker')
REFERENCE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'origin': {'type': 'string', 'enum': ['claim', 'source_context']},
                   'quote': {'type': 'string'}},
    'required': ['origin', 'quote'],
}
CONTEXT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {k: {'type': 'array', 'items': deepcopy(REFERENCE_SCHEMA)} for k in FIELDS},
    'required': list(FIELDS),
}


def compact(text):
    return ' '.join(text.split())


def ground_context(context, claim, source_context):
    if not isinstance(context, dict) or set(context) != set(FIELDS):
        raise ValueError('invalid_component_context')
    result = {}
    for field in FIELDS:
        refs = context[field]
        if not isinstance(refs, list):
            raise ValueError('invalid_context_references')
        result[field] = []
        for ref in refs:
            if (not isinstance(ref, dict) or ref.get('origin') not in {'claim', 'source_context'}
                    or not isinstance(ref.get('quote'), str) or not ref['quote'].strip()):
                raise ValueError('invalid_context_reference')
            origin = ref['origin']
            text = claim if origin == 'claim' else source_context
            quote = ref['quote']
            start = text.find(quote)
            if start < 0:
                raise ValueError('ungrounded_component_context')
            entry = {'origin': origin, 'quote': quote, 'start': start, 'end': start + len(quote)}
            if entry not in result[field]:
                result[field].append(entry)
    return result


def local_assertion(part, context):
    # Both predicate and subject must be explicitly located in this fragment.
    # Shared-subject clauses are conservatively recombined instead of rewritten.
    if len(re.findall(r'\w+', part)) < 2:
        return False
    subjects = [r['quote'] for r in context['subject'] if r['quote'] in part]
    actions = [r['quote'] for r in context['action'] if r['quote'] in part]
    return any(s != a and s not in a and a not in s for s in subjects for a in actions)


def prepare_components(claim, parts, contexts, source_context=''):
    if not isinstance(contexts, list) or not contexts:
        raise ValueError('incomplete_component_contexts')
    grounded = [ground_context(c, claim, source_context) for c in contexts]
    repair = None
    if len(contexts) != len(parts):
        # Contexts cannot safely be assigned to fragments when counts disagree.
        # Preserve the complete assertion and only its validated references.
        merged = {k: [] for k in FIELDS}
        for ctx in grounded:
            for k in FIELDS:
                merged[k].extend(r for r in ctx[k] if r not in merged[k])
        parts, grounded = [claim], [merged]
        repair = 'context_count_mismatch_recombined_whole_claim'
    spans, cursor = [], 0
    for part in parts:
        start = claim.find(part, cursor)
        if start < 0:
            raise ValueError('component_span_not_in_claim')
        spans.append((start, start + len(part)))
        cursor = start + len(part)
    units = [{'start': start, 'end': end, 'anchors': ctx, 'proposed_ids': [i]}
             for i, ((start, end), ctx) in enumerate(zip(spans, grounded))]
    while len(units) > 1:
        bad = next((i for i, u in enumerate(units)
                    if not local_assertion(claim[u['start']:u['end']], u['anchors'])), None)
        if bad is None:
            break
        left = max(0, bad - 1)
        a, b = units[left:left + 2]
        anchors = {k: a['anchors'][k] + [r for r in b['anchors'][k] if r not in a['anchors'][k]] for k in FIELDS}
        units[left:left + 2] = [{'start': a['start'], 'end': b['end'], 'anchors': anchors,
                                'proposed_ids': a['proposed_ids'] + b['proposed_ids']}]
    for i, u in enumerate(units):
        u.update(component_id=i, assertion=claim[u['start']:u['end']],
                 source_reference={'origin': 'claim', 'start': u['start'], 'end': u['end']},
                 context_is_evidence=False)
        if repair:
            u['partition_repair'] = repair
        # Explicit dates in the assertion cannot disappear because an annotator omitted them.
        for match in DATE.finditer(u['assertion']):
            quote = match.group()
            if not any(quote in r['quote'] for r in u['anchors']['time']):
                start = u['start'] + match.start()
                u['anchors']['time'].append({'origin': 'claim', 'quote': quote, 'start': start,
                                             'end': start + len(quote)})
        # No inferred values: an unresolved role remains an empty list.
    if compact(' '.join(u['assertion'] for u in units)) != compact(claim):
        raise ValueError('component_context_changed_claim')
    return units


MONTHS = {name: i for i, names in enumerate([
    ('january', 'jan'), ('february', 'feb'), ('march', 'mar'), ('april', 'apr'),
    ('may',), ('june', 'jun'), ('july', 'jul'), ('august', 'aug'),
    ('september', 'sep', 'sept'), ('october', 'oct'), ('november', 'nov'),
    ('december', 'dec')], 1) for name in names}
DATE = re.compile(r'\b(' + '|'.join(sorted(MONTHS, key=len, reverse=True)) +
                  r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b', re.I)


def dates(text):
    return {(MONTHS[m.group(1).lower()], int(m.group(2))) for m in DATE.finditer(text)}


def temporal_context_decision(contexts, passages):
    """Only explicit event-time references; never infer time from a URL/publication date."""
    refs = [r for context in contexts for r in context['anchors']['time']]
    required = set().union(*(dates(r['quote']) for r in refs)) if refs else set()
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', ' '.join(r['quote'] for r in refs)))
    evidence = ' '.join(passages)
    observed = dates(evidence)
    observed_years = set(re.findall(r'\b(?:19|20)\d{2}\b', evidence))
    if not required and not years:
        return {'status': 'unresolved', 'enforced': False, 'reason': 'No explicit event-time anchor; semantic event review still required.'}
    missing = required - observed
    missing_years = years - observed_years
    if not missing and not missing_years:
        return {'status': 'matching', 'enforced': True, 'reason': 'Explicit event-time anchors appear in selected identity passages; relationship still requires review.'}
    conflict = bool((missing and observed) or (missing_years and observed_years))
    return {'status': 'conflicting' if conflict else 'unresolved', 'enforced': True,
            'reason': 'Selected identity passages do not establish the required event time.',
            'missing_month_days': sorted([list(x) for x in missing]), 'missing_years': sorted(missing_years)}


def attach_context(review, contexts, claim):
    review['original_claim'] = claim
    for part, context in zip(review['components'], contexts):
        part['context'] = deepcopy(context)
    return review


def needs_context_review(claim, source_context, contexts):
    """A surrounding dated event needs explicit reference resolution, not silent omission."""
    return bool(source_context and compact(source_context) != compact(claim)
                and dates(source_context) - dates(claim)
                and not any(r['origin'] == 'source_context' for c in contexts
                            for r in c['anchors']['time']))


def merge_context_review(contexts, reviewed, claim, source_context):
    if not isinstance(reviewed, list) or len(reviewed) != len(contexts):
        raise ValueError('incomplete_context_review')
    for component, correction in zip(contexts, reviewed):
        grounded = ground_context(correction, claim, source_context)
        # An independent context pass may add missing antecedents, never erase
        # explicit qualifiers already grounded in the assertion.
        for field in FIELDS:
            refs = component['anchors'][field]
            refs.extend(r for r in grounded[field] if r not in refs)
        component['context_reviewed'] = True
    return contexts
