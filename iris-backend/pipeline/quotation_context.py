"""Explicit speech framing, shared by screening and extraction (not truth checks)."""

import re
from copy import deepcopy

from iris_trace.core import event
from pipeline.text_boundaries import quote_spans, split_statement_segments


class QuotationExtractionError(RuntimeError):
    """A reported quotation could not be extracted safely; never a factual verdict."""


SPEECH_RULES = (
    'These speech rules supplement ordinary factual extraction; they do NOT restrict '
    'the task to speech. Retain independent event/factual assertions as usual. '
    'Distinguish a REPORTED speech act from IMAGINED, anticipated, scripted or satirical '
    'speech. Reporting that a person asked a question, expressed an opinion, made a '
    'recommendation, or used a hypothetical comparison is checkable as ATTRIBUTION; '
    'do not discard it because the words inside the quote are not factual assertions. '
    'Check whether the speaker said/asked it, not whether the quoted opinion is true. '
    'Indirect reports also count: "She noted that X" or "He asked about Y" are '
    'reported speech acts without quotation marks. Do not discard indirect reports '
    'as evaluative merely because they are paraphrased. Repeated narrative versions '
    'link to the SAME enriched claim; genuinely different statements stay separate. '
    'But an author waiting for, imagining, predicting or scripting someone asking '
    'a question is NOT reporting that they actually asked it. Preserve that framing '
    'across all consecutive quotations. Never rewrite expected speech as actually said. '
    'A hypothetical INSIDE an actual reported quotation remains part of what was said. '
    'A report that someone said they planned to ask something verifies that stated plan, '
    'not that they already asked it. Preserve denial/negation in the reporting frame too. '
    'A satirical speaker can actually make a statement; satire inside a reported '
    'utterance is different from a fabricated attribution. Unattributed quotation marks '
    'alone do not establish a speaker. Resolve a pronoun only from supplied context. '
)

_REPORT = re.compile(
    r'\b(?:asked|answered|replied|said|stated|furthered|told|responded|warned|'
    r'pointed out|noted|sought clarification|sinabi|aniya|ayon|sagot|tanong)\b', re.I)
_IMAGINED = re.compile(
    r'\b(?:waiting\s+for|wait\s+for|hinihintay|inaabangan)\b.{0,180}'
    r'\b(?:question|questions|ask|asking|say|saying|tanong|sasabihin|itatanong)\b|'
    r'\b(?:imagine|imagining|imagined)\b.{0,140}\b(?:ask\w*|say\w*|said|speech|question\w*)\b|'
    r'\b(?:would|might|could|will)\s+(?:probably\s+)?(?:ask|say|reply)\b|'
    r'\b(?:expected|expect|expecting)\b.{0,100}\b(?:to\s+)?(?:ask|say|question\w*)\b|'
    r'\b(?:fictional|imaginary|fabricated|satirical)\s+(?:speech|quote|quotation|dialogue|script|interview)\b|'
    r'\b(?:if|suppose)\b.{0,100}\b(?:asked|said|asks|says)\b', re.I)


def utterances(text):
    spans = quote_spans(text)
    return [text[a:b] for a, b in spans
            if not any(c < a and b < d for c, d in spans)
            and not re.search(r'\b(?:dubbed|named|titled|known as|program|show)\s+(?:the\s+)?$',
                              text[:a], re.I)]


def speech_scopes(segments):
    """Inherit framing only for quote-only continuations, never unrelated prose."""
    result = []
    previous = 'none'
    for text in segments:
        spans = quote_spans(text)
        direct = bool(utterances(text))
        outside = ''.join(' ' if any(a <= i < b for a, b in spans) else ch
                          for i, ch in enumerate(text))
        continuation = direct and not re.search(r'\w', outside)
        anticipated = _IMAGINED.search(outside)
        reported = _REPORT.search(outside)
        fictional_frame = re.search(r'\b(?:fictional|imaginary|fabricated|satirical)\s+'
                                    r'(?:speech|quote|quotation|dialogue|script|interview)\b', outside, re.I)
        if continuation and previous in {'reported', 'imagined'}:
            scope = previous
        elif anticipated and not (direct and reported and reported.start() < anticipated.start()
                                  and not fictional_frame):
            scope = 'imagined'
        elif direct and reported:
            scope = 'reported'
        elif reported and not re.fullmatch(r'(?:that|with that|as|it is)',
                                          outside[:reported.start()].strip(), re.I):
            scope = 'reported_indirect'
        else:
            scope = 'unattributed' if spans else 'none'
        result.append(scope)
        previous = scope
    return result


def comparable_utterance(text):
    # Formatting may change, but the utterance's words, numbers and negation may not.
    return ' '.join(re.findall(r"\w+(?:['\u2019]\w+)*", text.casefold()))


def validate_speech_coverage(payload, segments):
    scopes = speech_scopes(segments)
    for index, (segment, scope) in enumerate(zip(segments, scopes)):
        row = payload['coverage'][index]
        ids = row['claim_indexes']
        if scope == 'imagined' and ids:
            raise ValueError(f'imagined_speech_promoted:segment_{index}')
        if scope == 'reported_indirect' and not ids:
            raise ValueError(f'reported_speech_act_excluded:segment_{index}')
        if scope != 'reported':
            continue
        linked = [payload['claims'][i] for i in ids
                  if payload['claims'][i]['claim_type'] == 'attributed_statement']
        if not linked:
            raise ValueError(f'reported_utterance_excluded:segment_{index}')
        for quote in utterances(segment):
            words = comparable_utterance(quote)
            if words and not any(all(words in comparable_utterance(c.get(key, ''))
                                     for key in ('claim_text', 'normalized_claim')) for c in linked):
                raise ValueError(f'reported_utterance_shortened:segment_{index}')
    return payload


QUOTE_EDGES = " \t\n\"'\u201c\u201d\u2018\u2019,.;:!?"


def _inner(utterance):
    return utterance.strip(QUOTE_EDGES)


def translated_quotations(original_text, translated_text):
    """
    Pairs each quotation of the post with its translation: [(translated words, original words)].

    The translator works sentence by sentence and returns one line per sentence, so the Nth
    line holds the Nth sentence; the Nth quotation of a sentence is paired with the Nth
    quotation of its line. A quotation left as it was is not a pair.
    """
    original_text, translated_text = str(original_text or ''), str(translated_text or '')
    if not translated_text or translated_text == original_text:
        return []
    originals = split_statement_segments(original_text)
    translations = [line for line in translated_text.split('\n') if line.strip()]
    if len(translations) != len(originals):
        translations = split_statement_segments(translated_text)
    if len(translations) != len(originals):
        event('claims.quotation_restore_unaligned', originals=len(originals), translations=len(translations))
        return []
    pairs = []
    for original, translation in zip(originals, translations):
        said, rendered = utterances(original), utterances(translation)
        if len(said) != len(rendered):
            continue
        for spoken, english in zip(said, rendered):
            if comparable_utterance(spoken) != comparable_utterance(english) and _inner(spoken):
                pairs.append((_inner(english), _inner(spoken)))
    return pairs


def _replace_words(text, words, replacement):
    """Replaces the span of text holding these words in order, whatever lies between them."""
    tokens = re.findall(r"\w+(?:['\u2019]\w+)*", words)
    if not tokens:
        return text, False
    pattern = r"(?<!\w)" + r"\W+".join(re.escape(token) for token in tokens) + r"(?!\w)"
    match = re.search(pattern, text, re.I)
    if not match:
        return text, False
    return text[:match.start()] + replacement + text[match.end():], True


def restore_original_quotations(claim, original_text, translated_text):
    """
    Puts a quotation back in the words it was said in, keeping the English as a search aid.

    A post read as Tagalog is translated whole, so its claims carried quotations in English:
    "Para kasi sa administrasyong Marcos, mas madali ang maging inutil..." became "Because for the
    Marcos administration, it is easier to be useless..." (diagnosed 22 September). Reporting
    prints the words as said, so the claim now carries them; the English rendering of the whole
    claim is kept as quote_translation, for one extra search pass and as a note to the reviewer.
    """
    pairs = translated_quotations(original_text, translated_text)
    if not pairs:
        return claim
    restored = deepcopy(claim)
    before = str(claim.get('claim_text') or claim.get('normalized_claim') or '')
    applied = []
    # Longest first: a headline often repeats the opening of the full quotation (saved case
    # A08), and replacing the short one first would leave the long one half translated.
    for english, spoken in sorted(pairs, key=lambda pair: -len(pair[0])):
        changed = False
        for key in ('claim_text', 'normalized_claim'):
            if restored.get(key):
                restored[key], hit = _replace_words(restored[key], english, spoken)
                changed = changed or hit
        attribution = restored.get('attribution')
        if isinstance(attribution, dict) and attribution.get('statement'):
            attribution['statement'], _ = _replace_words(attribution['statement'], english, spoken)
        if changed:
            applied.append({'original': spoken, 'translation': english})
    if not applied:
        return claim
    restored['quote_translation'] = before
    restored['restored_quotations'] = applied
    event('claims.quotation_restored', claim_id=claim.get('claim_id'), restored=len(applied))
    return restored
