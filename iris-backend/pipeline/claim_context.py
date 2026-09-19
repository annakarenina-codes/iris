"""Conservative identity anchors for referential incident assertions.

The submitted post resolves identity only; it never supplies evidence of truth.
Unresolved or multi-victim contexts remain for component review, without guessing.
"""

import re

REFERENTIAL_INCIDENT = re.compile(
    r'\b(?:the suspects|the killing|the incident|the attack|the investigation|'
    r'(?:his|her) (?:home|companion))\b', re.I)
VICTIM = re.compile(
    r'\b(?:Dr\.\s+)?(?P<name>[A-Z][a-zA-Z\u00c0-\u024f\'-]+'
    r'(?:\s+[A-Z][a-zA-Z\u00c0-\u024f\'-]+){1,3})'
    r'(?:,\s*[^.!?]{1,600}?,)?\s+was\s+(?:shot|killed|murdered)\b')


def incident_anchor(claim, source_context):
    if not REFERENTIAL_INCIDENT.search(claim):
        return {'subject': None, 'reason': 'not_referential_incident'}
    names = {match.group('name').strip() for match in VICTIM.finditer(source_context or '')}
    if len(names) != 1:
        return {'subject': None, 'reason': 'unresolved_or_ambiguous_incident_subject'}
    return {'subject': names.pop(), 'reason': 'named_victim_in_source_context'}


def contextual_search_query(query, anchor):
    subject = anchor.get('subject')
    if subject and subject.casefold() not in query.casefold():
        return f'{subject} {query}'
    return query


def incident_evidence_gate(article, anchor):
    subject = anchor.get('subject')
    if not subject:
        return {'matches': True, 'subject': None, 'reason': anchor['reason']}
    surname = subject.split()[-1]
    found = bool(re.search(r'(?<!\w)' + re.escape(surname) + r'(?!\w)',
                           article.get('text') or '', re.I))
    return {'matches': found, 'subject': subject,
            'reason': 'incident_subject_present' if found else 'incident_subject_absent'}
