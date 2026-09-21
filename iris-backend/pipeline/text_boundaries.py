"""Conservative sentence boundaries that preserve reported utterances."""

import re

# Verbs that hand a quotation to someone. Philippine reporting closes quotes with "shared",
# "added" and "revealed" as often as with "said": a showbiz post ending in "she shared." was
# read as the page's own words, and its one opinion word filed the whole quote as opinion.
#
# is_attribution_tail keeps its shorter list on purpose. It also decides where sentences end,
# in the articles IRIS reads as well as in posts, and moving those boundaries is a separate
# change with its own risks.
REPORTED_SPEECH_VERBS = (
    r'asked|answered|replied|said|stated|furthered|told|responded|warned|'
    r'shared|added|explained|noted|revealed|recalled|admitted|recounted|remarked|stressed|'
    r'emphasized|emphasised|insisted|disclosed|expressed|claimed|wrote|posted|argued|'
    r'declared|quipped|'
    r'sinabi|aniya|ayon|sagot|tanong'
)


def quote_spans(text):
    pairs = {'"': '"', "'": "'", '\u201c': '\u201d', '\u2018': '\u2019'}
    stack, spans = [], []
    for index, char in enumerate(text):
        # A malformed quotation must not consume later paragraphs.
        if char == '\n' and text[max(0, index - 1):index] == '\n':
            stack.clear()
        if char in "'\u2019":
            before = text[index - 1:index] if index else ''
            after = text[index + 1:index + 2]
            if before.isalnum() and after.isalnum():
                continue
            if re.match(r"(?:yung|yun|yon|yan|yang|nung|wag|di|to)\b", text[index + 1:], re.I):
                continue
        if stack and char == stack[-1][1]:
            start, _ = stack.pop()
            spans.append((start, index + 1))
        elif char in pairs:
            stack.append((index, pairs[char]))
    return sorted(spans)


def has_reported_quote(text):
    spans = quote_spans(text)
    if not spans:
        return False
    # A reporting verb inside the quotation is not an attribution by the post.
    outside = ''.join(' ' if any(a <= i < b for a, b in spans) else char
                      for i, char in enumerate(text))
    return bool(re.search(r'\b(?:' + REPORTED_SPEECH_VERBS + r')\b', outside, re.I))


def is_attribution_tail(text):
    return bool(re.match(
        r'(?:(?:the\s+)?(?:witness|senator|auditor|expert)|he|she|'
        r'[A-Z][\w\u00c0-\u024f.-]*(?:\s+[A-Z][\w\u00c0-\u024f.-]*){0,4})'
        r'\s+(?:asked|answered|replied|said|stated|furthered|told|responded|warned)\b'
        r'(?:\s+(?:him|her|them|[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,3}))?'
        r'(?:[,.:!?](?:\s|$)|$)',
        text))


def split_statement_segments(text):
    spans = quote_spans(text)
    boundaries = [0]
    for gap in re.finditer(r'\s+|;\s*', text):
        start, end = gap.span()
        if any(a < start < b for a, b in spans):
            continue
        left, right = text[boundaries[-1]:start], text[end:]
        if not left or not right:
            continue
        closes_quote = any(b == start for _, b in spans)
        if closes_quote and is_attribution_tail(right):
            continue
        terminal = left.rstrip('"\u201d\u2019\'')
        punctuation = terminal.endswith(('.', '!', '?'))
        abbreviation = re.search(
            r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sec|Sen|Rep|Gov|Gen|Col|Lt|Capt|'
            r'Atty|Pres|Brgy|Jr|Sr|St|No|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.$',
            terminal, re.I)
        initial = re.search(r'\b[A-Z]\.$', terminal)
        if punctuation and (abbreviation or initial) and not closes_quote:
            continue
        headline = (closes_quote and len(left) <= 140 and left.upper() == left
                    and any(char.isalpha() for char in left))
        if ('\n' in gap.group() or gap.group().startswith(';') or headline
                or (punctuation and (not closes_quote or not right[0].islower()))):
            boundaries.append(end)
    boundaries.append(len(text))
    return [part for a, b in zip(boundaries, boundaries[1:])
            if (part := text[a:b].strip())]
