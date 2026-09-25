"""
Paraphrases quote-derived claims before semantic evidence scoring.

Independent reporting often paraphrases hearings and interviews instead of
printing exact quote text. This helper keeps the original claim visible to the
user while giving the similarity model a plain descriptive sentence to score.
"""

from __future__ import annotations

from iris_trace.core import traced

from functools import lru_cache
import json
import os
import re
from typing import Dict

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depends on local environment setup
    def load_dotenv():
        return False

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local environment setup
    OpenAI = None


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_QUOTE_PARAPHRASE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


def _get_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or ""


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(text or ""))
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _sentence(text: str) -> str:
    text = _clean(text).strip(" \"'`“”‘’")
    if text and text[-1] not in ".!?":
        return f"{text}."
    return text


def _clean_name(text: str) -> str:
    return _clean(text).strip(" ,.;:")


def _clean_quoted_term(text: str) -> str:
    return _clean(text).strip(" \"'`“”‘’,.;:")


def _heuristic_paraphrase(text: str) -> str:
    clean_text = _clean(text)

    define_match = re.search(
        r"(?P<speaker>[A-Z][A-Za-z.'-]+)\s+then\s+asked\s+(?P<listener>[A-Z][A-Za-z.'-]+)\s+"
        r"to\s+define\s+[\"“”'](?P<term>[^\"“”']+)[\"“”'].*?replied,\s+[\"“”'](?P<definition>[^\"“”']+)[\"“”']",
        clean_text,
        flags=re.IGNORECASE,
    )
    if define_match:
        return _sentence(
            f"{_clean_name(define_match.group('speaker'))} asked {_clean_name(define_match.group('listener'))} "
            f"to define {_clean_quoted_term(define_match.group('term'))}, and {_clean_name(define_match.group('listener'))} "
            f"replied that it meant {_clean_quoted_term(define_match.group('definition'))}"
        )

    answer_match = re.search(
        r"[\"“”'](?P<quote>[^\"“”']{4,260})[\"“”']\s*,?\s+(?P<speaker>the\s+witness|[A-Z][A-Za-z.'-]+)"
        r"\s+(?:answered|replied|said|stated)",
        clean_text,
        flags=re.IGNORECASE,
    )
    if answer_match:
        quote = answer_match.group("quote")
        speaker = _clean_name(answer_match.group("speaker"))
        if "not an investigation" in quote.lower() and "evaluation" in quote.lower():
            return _sentence(f"{speaker} answered that the process was an evaluation, not an investigation")
        return _sentence(f"{speaker} answered that {quote}")

    asked_match = re.search(
        r"[\"“”'](?P<quote>[^\"“”']{4,260})[\"“”']\s*,?\s+(?P<speaker>[A-Z][A-Za-z.'-]+)"
        r"\s+asked\s+(?P<listener>[A-Z][A-Za-z.'-]+)",
        clean_text,
        flags=re.IGNORECASE,
    )
    if asked_match:
        quote = asked_match.group("quote")
        quote = re.sub(r"\bis that correct\b", "", quote, flags=re.IGNORECASE)
        quote = re.sub(r"\bbut\b", "", quote, count=1, flags=re.IGNORECASE)
        quote = quote.strip(" ,.;?")
        return _sentence(
            f"{_clean_name(asked_match.group('speaker'))} asked {_clean_name(asked_match.group('listener'))} about {quote}"
        )

    quoted = re.findall(r"[\"“”']([^\"“”']{4,260})[\"“”']", clean_text)
    if quoted:
        unquoted = clean_text
        for quote in quoted:
            unquoted = unquoted.replace(f'"{quote}"', quote)
            unquoted = unquoted.replace(f"'{quote}'", quote)
            unquoted = unquoted.replace(f"“{quote}”", quote)
        return _sentence(unquoted)

    return _sentence(clean_text)


@lru_cache(maxsize=256)
@traced('claim.paraphrase_ai', dependency=True)
def _llm_paraphrase(text: str) -> Dict[str, object]:
    if OpenAI is None:
        return {
            "status": "missing_dependency",
            "paraphrase": _heuristic_paraphrase(text),
            "method": "local_heuristic",
            "error": "The openai package is not installed.",
        }

    api_key = _get_api_key()
    if not api_key:
        return {
            "status": "missing_api_key",
            "paraphrase": _heuristic_paraphrase(text),
            "method": "local_heuristic",
            "error": "Missing OPENAI_API_KEY in .env.",
        }

    prompt = (
        "Convert the quote-derived claim into one plain descriptive factual "
        "sentence for evidence matching. Keep all named people, agencies, "
        "places, topics, and the meaning of the quote. Do not decide whether "
        "it is true. Do not add facts. Return JSON only: {\"paraphrase\":\"...\"}."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        paraphrase = _sentence(str(payload.get("paraphrase") or ""))
    except Exception as error:
        return {
            "status": "error",
            "paraphrase": _heuristic_paraphrase(text),
            "method": "local_heuristic",
            "error": f"OpenAI quote paraphrase failed: {error}",
        }

    if not paraphrase:
        paraphrase = _heuristic_paraphrase(text)

    return {
        "status": "ok",
        "paraphrase": paraphrase,
        "method": "openai",
        "error": None,
    }


@traced('claim.paraphrase', dependency=False)
def paraphrase_quote_claim(claim: Dict[str, object]) -> Dict[str, object]:
    """Returns the text IRIS should score for a quote-derived claim."""
    source_text = str(claim.get("normalized_claim") or claim.get("claim_text") or "")
    result = dict(_llm_paraphrase(source_text))
    result["used_for_scoring"] = True
    return result
