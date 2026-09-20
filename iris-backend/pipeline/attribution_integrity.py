"""Keep attribution metadata grounded in submitted text, not model guesses."""

from iris_trace.core import traced
import re
import unicodedata


def attribution_tokens(value):
    """Normalize typography, not identity: no nicknames or fuzzy name expansion."""
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    # Dotted initialisms such as G.M.A. are spelling variants, not inferred aliases.
    value = re.sub(r"\b(?:[^\W\d_]\.){2,}", lambda m: m.group().replace(".", ""), value)
    return re.findall(r"[^\W_]+", value)


QUOTED_NICKNAME = re.compile(r"[\"\u201c\u2018\']\s*([^\W\d_]+)\s*[\"\u201d\u2019\']")


def without_quoted_nicknames(text):
    """Sen. Robinhood "Robin" Padilla also reads as Sen. Robinhood Padilla."""
    return QUOTED_NICKNAME.sub(' ', str(text or ''))


def _contains_tokens(required, text):
    available = attribution_tokens(text)
    return any(available[index:index + len(required)] == required
               for index in range(len(available) - len(required) + 1))


def attribution_phrase_match(phrase, text):
    required = attribution_tokens(phrase)
    if not required:
        return False
    # A nickname in quotes is dropped from the text, never added to the phrase: no alias guessing.
    return _contains_tokens(required, text) or _contains_tokens(required, without_quoted_nicknames(text))


# A date is written many ways in Philippine coverage: "Sept. 18", "September 18",
# "Setyembre 18", "18 September". Comparing the claim's spelling to the article's rejected
# the right article for its wording (saved case C06).
MONTH_ALIASES = {
    1: ['january', 'jan', 'enero'], 2: ['february', 'feb', 'pebrero'],
    3: ['march', 'mar', 'marso'], 4: ['april', 'apr', 'abril'],
    5: ['may', 'mayo'], 6: ['june', 'jun', 'hunyo'], 7: ['july', 'jul', 'hulyo'],
    8: ['august', 'aug', 'agosto'], 9: ['september', 'sept', 'sep', 'setyembre'],
    10: ['october', 'oct', 'oktubre'], 11: ['november', 'nov', 'nobyembre'],
    12: ['december', 'dec', 'disyembre'],
}
MONTHS = {alias: number for number, aliases in MONTH_ALIASES.items() for alias in aliases}


def _date_parts(phrase):
    words = re.findall(r"[^\W_]+", str(phrase or '').lower())
    month = next((MONTHS[word] for word in words if word in MONTHS), None)
    day = next((int(word) for word in words if word.isdigit() and 1 <= int(word) <= 31), None)
    return month, day


def date_phrase_match(phrase, text):
    """True when the text states the same calendar date, however it is written."""
    month, day = _date_parts(phrase)
    if month is None or day is None:
        return attribution_phrase_match(phrase, text)
    haystack = ' ' + ' '.join(re.findall(r"[^\W_]+", str(text or '').lower())) + ' '
    days = {str(day), f'{day:02d}'}
    return any(f' {alias} {written} ' in haystack or f' {written} {alias} ' in haystack
               for alias in MONTH_ALIASES[month] for written in days)


TITLES = {'sen', 'senator', 'sens', 'rep', 'reps', 'representative', 'cong', 'congressman', 'congresswoman',
          'sec', 'secretary', 'usec', 'undersecretary', 'gov', 'governor', 'mayor', 'vice', 'president',
          'vp', 'atty', 'attorney', 'dr', 'engr', 'gen', 'general', 'brig', 'maj', 'col', 'lt', 'police',
          'justice', 'judge', 'chief', 'former', 'ret', 'retired', 'hon', 'dir', 'director', 'spokesperson',
          'interior', 'education', 'senator-judge'}


NAME_WITH_NICKNAME = re.compile(
    r"([^\W\d_]+)\s*[\"\u201c\u2018\']\s*([^\W\d_]+)\s*[\"\u201d\u2019\']\s*([^\W\d_]+)")


def source_nickname_variants(tokens, source_text):
    """
    Name forms the post spells out: "Robinhood \u201cRobin\u201d Padilla" ties Robinhood to Robin.

    Only used when the post itself writes both forms next to the same family name, so the
    equivalence comes from the submitted text, never from outside knowledge.
    """
    variants = []
    for match in NAME_WITH_NICKNAME.finditer(str(source_text or '')):
        parts = [attribution_tokens(part) for part in match.groups()]
        if not all(len(part) == 1 for part in parts):
            continue
        given, nickname, family = (part[0] for part in parts)
        if given in tokens and family in tokens:
            for variant in ([nickname, family], [given, family]):
                if variant not in variants:
                    variants.append(variant)
    return variants


def speaker_variants(speaker, source_text=''):
    """
    Name forms the post itself supplies: with or without a quoted nickname, with or without titles.

    "Sen. Robinhood \u201cRobin\u201d Padilla" yields Robinhood Padilla and Robin Padilla, which is how
    articles write the same person. Nothing is invented: every variant comes from the submitted name.
    """
    speaker = str(speaker or '')
    given = attribution_tokens(speaker)
    plain = attribution_tokens(without_quoted_nicknames(speaker))
    untitled = [token for token in plain if token not in TITLES]
    forms = [given, plain, untitled]
    nickname = QUOTED_NICKNAME.search(speaker)
    if nickname and untitled:
        # The nickname stands in for the given name: Robinhood Padilla -> Robin Padilla.
        forms.append(attribution_tokens(nickname.group(1)) + untitled[1:])
    variants = []
    for form in forms + source_nickname_variants(plain, source_text):
        if len(form) >= min(2, len(given)) and form not in variants:
            variants.append(form)
    return variants


def speaker_phrase_match(speaker, text, source_text=''):
    """True when any name form of this speaker appears in the text as written."""
    texts = (text, without_quoted_nicknames(text))
    return any(_contains_tokens(variant, candidate)
               for variant in speaker_variants(speaker, source_text) for candidate in texts)


_CREDIT_LINE = re.compile(
    r"(?:^|[/|])[ \t]*(?:via|by|reported by|report by|photo by|image by|photo credit:?)"
    r"[ \t]+(?P<credit>[^\r\n]+)\r?$", re.IGNORECASE | re.MULTILINE,
)


def without_credit_lines(text):
    """Remove only explicitly delimited, name-like credit lines from grounding."""
    credits = []

    def replace(match):
        credit = match.group("credit").strip()
        tokens = attribution_tokens(credit)
        if (not 1 <= len(tokens) <= 10
                or not re.fullmatch(r"[^\W\d_][\w .,'’&-]*", credit)
                or set(tokens) & {"said", "says", "asked", "reported", "that", "according"}):
            return match.group()
        credits.append(credit)
        return " "

    return _CREDIT_LINE.sub(replace, str(text or "")), credits


def clean_attribution(value):
    value = str(value or "").strip()
    if value.lower() in {"", "not specified", "unspecified", "unknown", "n/a", "none", "null", "not provided", "speaker"}:
        return None
    return value


@traced('claims.attribution', dependency=False)
def ground_attribution(claim, source_text):
    if claim.get("claim_type") != "attributed_statement":
        return claim
    claim = dict(claim)
    attribution = dict(claim.get("attribution") or {})
    source, credits = without_credit_lines(source_text)
    removed = []
    field_checks = {}
    for key in ("speaker", "role", "source", "program", "date"):
        original = attribution.get(key)
        value = clean_attribution(original)
        reason = "absent" if not value else "grounded"
        if value and not attribution_phrase_match(value, source):
            reason = ("credit_only" if any(attribution_phrase_match(value, credit)
                                          for credit in credits) else "not_in_input")
            value = None
        if original and value != original:
            removed.append(key)
        attribution[key] = value
        field_checks[key] = reason
    # Use the submitted assertion rather than templating every report as an interview.
    assertion = claim.get("claim_text") or claim.get("normalized_claim", "")
    claim["normalized_claim"] = assertion
    attribution["statement"] = assertion
    claim["attribution"] = attribution
    claim["attribution_integrity"] = {
        "removed_unsupported_fields": removed,
        "field_checks": field_checks,
        "incidental_credits": credits,
    }
    claim["search_query"] = assertion
    return claim
