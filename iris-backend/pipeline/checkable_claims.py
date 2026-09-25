"""
Whether the claims extracted from a post name anything a source could confirm.

Saved case B07 is an advocacy post about voting. IRIS extracted five statements from it -
"one vote can influence the quality of education your children receive" and four like it -
searched eleven publishers for each, and answered Not Found five times. Nothing in those
sentences names a person, an institution, a number or a date, so no source could ever confirm
or refute them, and the honest answer is that the post contains nothing to check.

The rule is deliberately narrow, because its failure would be silent: a post routed here is
never searched, and the reader is told there was nothing to check. It applies only when EVERY
extracted claim is a general statement AND the profiler saw opinion or advocacy in the post.
One named party, number or date anywhere in one claim is enough to check the post as usual.
"""

from __future__ import annotations

from iris_trace.core import event

import re
from typing import Dict, List

ATTRIBUTED_CLAIM_TYPE = "attributed_statement"
MIN_GENERAL_CLAIMS = 2
MONTHS_AND_DAYS = {
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
    'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sept',
    'sep', 'oct', 'nov', 'dec', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'saturday', 'sunday', 'enero', 'pebrero', 'marso', 'abril', 'mayo', 'hunyo', 'hulyo',
    'agosto', 'setyembre', 'oktubre', 'nobyembre', 'disyembre', 'lunes', 'martes', 'miyerkules',
    'huwebes', 'biyernes', 'sabado', 'linggo',
}
# Capitalised words that name nobody and nothing, wherever they appear. Everything else that
# is capitalised is treated as a name, because the safe mistake is to check a post anyway.
NAMES_NOTHING = {
    'a', 'an', 'the', 'this', 'that', 'these', 'those', 'there', 'here', 'it', 'its', 'they',
    'their', 'them', 'we', 'our', 'us', 'you', 'your', 'he', 'she', 'his', 'her', 'him', 'i',
    'many', 'most', 'some', 'few', 'all', 'every', 'each', 'one', 'two', 'three', 'no', 'not',
    'but', 'and', 'or', 'if', 'when', 'while', 'because', 'since', 'yet', 'so', 'in', 'on', 'at',
    'for', 'with', 'without', 'people', 'imagine', 'sometimes', 'often', 'usually', 'always',
    'never', 'today', 'tomorrow', 'yesterday', 'now', 'then', 'still', 'even', 'also', 'after',
    'before', 'during', 'unfortunately', 'sadly', 'remember', 'let', 'do', 'don', 'please',
    'what', 'why', 'how', 'who', 'whose', 'which', 'nobody', 'everyone', 'someone', 'anyone',
    'ang', 'mga', 'ito', 'iyon', 'sila', 'kami', 'tayo', 'ikaw', 'kung', 'ngunit', 'dahil',
    'hindi', 'walang', 'bawat', 'marami', 'kapag', 'sana', 'kaya', 'pero', 'talaga',
}


def verifiable_handles(text: str) -> List[str]:
    """What in this sentence a source could be checked against."""
    sentence = str(text or '')
    found = []
    if re.search(r'\d', sentence):
        found.append('number')
    words = re.findall(r"[^\W\d_]+", sentence)
    if any(word.lower() in MONTHS_AND_DAYS for word in words):
        found.append('date')
    for match in re.finditer(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", sentence):
        word = match.group()
        if not word[:1].isupper() or word.split("'")[0].lower() in NAMES_NOTHING:
            continue
        # A name opening a sentence is still a name: "Padilla said he will not run again."
        found.append('name')
        break
    return sorted(set(found))


def is_general_statement(claim: Dict[str, object]) -> bool:
    """True when nothing in the claim can be looked up in a news article."""
    if claim.get('claim_type') == ATTRIBUTED_CLAIM_TYPE:
        return False
    written = [claim.get('claim_text'), claim.get('normalized_claim')]
    return not any(verifiable_handles(text) for text in written if text)


def only_general_statements(claims: List[Dict[str, object]], content_profile: Dict[str, object]) -> bool:
    """
    True when a post's every claim is a general statement and the post reads as advocacy.

    Both conditions are required. A news post that happens to phrase one claim vaguely keeps
    its check; an advocacy post with one named party or figure keeps its check as well.
    """
    # A single vague claim is usually a terse news headline, not advocacy: saved case B05,
    # "Man who shot ex's new partner after online taunts arrested", names nobody and is still
    # a report IRIS should check.
    if len(claims) < MIN_GENERAL_CLAIMS:
        return False
    advocacy = bool(content_profile.get('contains_opinion') or content_profile.get('contains_recommendation'))
    if not advocacy or not all(is_general_statement(claim) for claim in claims):
        return False
    event('claims.general_statements_only',
          claims=[str(claim.get('claim_text'))[:160] for claim in claims])
    return True
