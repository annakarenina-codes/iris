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
