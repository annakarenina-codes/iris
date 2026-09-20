"""
Article text extraction for IRIS.

This module downloads a news URL and extracts readable article text using
BeautifulSoup. It keeps the logic simple for Week 2: title, paragraphs, word
count, and paywall/short-content detection.
"""

from __future__ import annotations

from iris_trace.core import traced, event

import json
import re
import threading
import time
from html import unescape
from typing import Dict, List
from urllib.parse import urlsplit
from pipeline.evidence_urls import article_url_rejection, clean_article_url

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - depends on local environment setup
    BeautifulSoup = None

try:
    import trafilatura
except ImportError:  # pragma: no cover - optional extraction fallback
    trafilatura = None


REQUEST_TIMEOUT_SECONDS = 5
MIN_ARTICLE_WORDS = 100
MIN_METADATA_WORDS = 8
THIN_ARTICLE_WORDS = 150


def _clean_text(text: str) -> str:
    """Removes extra spaces and blank lines from extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    """Counts normal words in article text."""
    return len(re.findall(r"\b\w+\b", text))


def normalize_article_url(url: str) -> str:
    """Removes common copy/paste punctuation from article URLs."""
    return clean_article_url(url)


def _meta_content(soup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(tag["content"])

        tag = soup.find("meta", property=name)
        if tag and tag.get("content"):
            return _clean_text(tag["content"])

    return ""


HTML_TEXT_KEYS = {"body_html", "bodyHtml", "bodyHTML"}
JSON_BODY_TEXT_KEYS = {"articleBody", *HTML_TEXT_KEYS}
JSON_METADATA_TEXT_KEYS = {"headline", "description"}


def _html_fragment_text(fragment: str) -> str:
    if BeautifulSoup is None:
        return _clean_text(unescape(fragment))

    soup = BeautifulSoup(unescape(fragment), "html.parser")
    return _clean_text(soup.get_text(" ", strip=True))


def _maybe_nested_json(value: str):
    value = value.strip()
    if not value or value[0] not in "[{":
        return None

    try:
        return json.loads(value)
    except ValueError:
        return None


def _dedupe_text_blocks(values: List[str]) -> List[str]:
    deduped = []
    seen = set()

    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue

        key = re.sub(r"\W+", " ", cleaned.lower())
        if key in seen:
            continue

        seen.add(key)
        deduped.append(cleaned)

    return deduped


def _json_values(payload, keys: set) -> List[str]:
    values = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, str):
                cleaned = (
                    _html_fragment_text(value)
                    if key in HTML_TEXT_KEYS
                    else _clean_text(unescape(value))
                )
                if cleaned:
                    values.append(cleaned)
            elif isinstance(value, str):
                nested = _maybe_nested_json(value)
                if nested is not None:
                    values.extend(_json_values(nested, keys))
            elif isinstance(value, (dict, list)):
                values.extend(_json_values(value, keys))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_json_values(item, keys))

    return values


def _json_article_text(soup) -> str:
    """Extracts article text from structured data when paragraphs are absent."""
    records = []

    def collect(payload):
        if isinstance(payload, dict):
            bodies = [payload[key] for key in JSON_BODY_TEXT_KEYS
                      if isinstance(payload.get(key), str) and payload[key].strip()]
            if bodies:
                records.append((payload.get('headline') or payload.get('title') or '',
                                _html_fragment_text(' '.join(bodies))))
                # An article's associations can contain complete bodies of other stories.
                return
            for key, value in payload.items():
                if key.casefold() not in {'relatedcontent', 'relatedarticles', 'recommendations'}:
                    collect(value)
        elif isinstance(payload, list):
            for value in payload:
                collect(value)
        elif isinstance(payload, str):
            nested = _maybe_nested_json(payload)
            if nested is not None:
                collect(nested)

    for script in soup.find_all("script", attrs={"type": re.compile(r"(?:ld\+json|application/json)", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue

        try:
            payload = json.loads(raw)
        except ValueError:
            continue

        collect(payload)
    title = _meta_content(soup, 'og:title', 'twitter:title')
    if not title and soup.h1:
        title = soup.h1.get_text(' ', strip=True)
    comparable = lambda value: re.sub(r'\W+', ' ', str(value).casefold()).strip()
    matched = [body for headline, body in records if title and comparable(headline) == comparable(title)]
    bodies = _dedupe_text_blocks(matched or [body for _, body in records])
    # Do not attribute a bundle of different stories to one article URL.
    return bodies[0] if len(bodies) == 1 else ''


def _paragraph_text(soup) -> str:
    containers = soup.find_all(["article", "main"])
    if not containers:
        containers = [soup]

    paragraphs = []
    for container in containers:
        for paragraph in container.find_all("p"):
            cleaned = _clean_text(paragraph.get_text(" ", strip=True))
            if cleaned and len(cleaned.split()) >= 5:
                paragraphs.append(cleaned)

    return _clean_text(" ".join(_dedupe_text_blocks(paragraphs)))


def _trafilatura_text(html: str, url: str) -> str:
    """Uses trafilatura as a second-pass extractor for thin article pages."""
    if trafilatura is None:
        return ""

    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
    )
    extracted_text = _clean_text(extracted or "")
    if _word_count(extracted_text) >= THIN_ARTICLE_WORDS:
        return extracted_text

    fetch_url = getattr(trafilatura, "fetch_url", None)
    if not fetch_url:
        return extracted_text

    try:
        downloaded = fetch_url(url)
    except Exception:
        return extracted_text

    if not downloaded:
        return extracted_text

    fetched_extracted = trafilatura.extract(
        downloaded,
        url=url,
        include_comments=False,
        include_tables=False,
    )
    fetched_text = _clean_text(fetched_extracted or "")
    if _word_count(fetched_text) > _word_count(extracted_text):
        return fetched_text

    return extracted_text


def _extraction_quality(word_count: int) -> str:
    return "full" if word_count >= THIN_ARTICLE_WORDS else "thin"


RATE_LIMITED_RETRIES = 1
RATE_LIMITED_WAIT_SECONDS = 2
HOST_REQUEST_INTERVAL_SECONDS = 1.0
# Two at a time per publisher, never one: a strict queue made every article of a slow
# publisher wait for the one before it, in this request and in every other request the
# server was serving, which turned a single image scan into minutes of waiting.
HOST_PARALLEL_REQUESTS = 2
# A publisher that answers 429 is left alone for a while instead of being retried article by
# article. Its search excerpts are still read, so the claim keeps its evidence.
HOST_COOLDOWN_SECONDS = 60
ARTICLE_CACHE_SECONDS = 900
ARTICLE_CACHE_MAX = 500
_host_slots = {}
_host_last_request = {}
_host_cooling_until = {}
_host_locks_guard = threading.Lock()
_article_cache = {}
_article_cache_guard = threading.Lock()


def _host_of(url):
    return urlsplit(url).netloc.lower()


def _host_slot(url):
    """A few requests at a time per publisher, so one slow page cannot block the rest."""
    with _host_locks_guard:
        return _host_slots.setdefault(_host_of(url), threading.Semaphore(HOST_PARALLEL_REQUESTS))


def _wait_for_host(url):
    """
    Leaves a gap between requests to the same publisher, which VERA Files requires.

    The waiting happens before a slot is taken, never while holding one.
    """
    host = _host_of(url)
    with _host_locks_guard:
        previous = _host_last_request.get(host)
        now = time.monotonic()
        delay = 0.0 if previous is None else HOST_REQUEST_INTERVAL_SECONDS - (now - previous)
        _host_last_request[host] = now + max(0.0, delay)
    if delay > 0:
        time.sleep(delay)


def host_is_cooling(url):
    """True while a publisher that answered 429 is being left alone."""
    with _host_locks_guard:
        until = _host_cooling_until.get(_host_of(url))
    return bool(until and time.monotonic() < until)


def cool_host(url):
    with _host_locks_guard:
        _host_cooling_until[_host_of(url)] = time.monotonic() + HOST_COOLDOWN_SECONDS
    event('retrieval.host_cooling', host=_host_of(url), seconds=HOST_COOLDOWN_SECONDS)


def cached_article(url):
    """A recently read article, so a post with many claims downloads each source once."""
    with _article_cache_guard:
        entry = _article_cache.get(url)
        if entry and time.monotonic() - entry['read'] < ARTICLE_CACHE_SECONDS:
            return dict(entry['article'])
    return None


def remember_article(url, article):
    if article.get('status') != 'extracted':
        return article
    with _article_cache_guard:
        if len(_article_cache) >= ARTICLE_CACHE_MAX:
            _article_cache.pop(next(iter(_article_cache)), None)
        _article_cache[url] = {'read': time.monotonic(), 'article': dict(article)}
    return article


@traced('retrieval.article_extract', dependency=True)
def extract_article_text(url: str) -> Dict[str, object]:
    """
    Downloads and extracts readable text from a news article URL.

    Returns a dictionary with an extraction status instead of raising errors, so
    app.py can continue even if one article fails.
    """
    normalized_url = normalize_article_url(url)
    rejection = article_url_rejection(normalized_url)
    if rejection:
        return {'url': normalized_url, 'status': 'skipped', 'error': rejection,
                'title': None, 'text': '', 'word_count': 0, 'extraction_quality': 'unavailable'}

    if requests is None:
        return {
            "url": normalized_url,
            "status": "error",
            "error": "The requests package is not installed.",
            "title": None,
            "text": "",
            "word_count": 0,
            "extraction_quality": "unavailable",
        }

    if BeautifulSoup is None:
        return {
            "url": normalized_url,
            "status": "error",
            "error": "The beautifulsoup4 package is not installed.",
            "title": None,
            "text": "",
            "word_count": 0,
            "extraction_quality": "unavailable",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    }

    reused = cached_article(normalized_url)
    if reused is not None:
        event('retrieval.article_cached', url=normalized_url)
        return reused

    if host_is_cooling(normalized_url):
        return {
            "url": normalized_url,
            "status": "error",
            "error": "Publisher is rate limiting requests; its search excerpts are used instead.",
            "title": None,
            "text": "",
            "word_count": 0,
            "extraction_quality": "unavailable",
        }

    try:
        _wait_for_host(normalized_url)
        with _host_slot(normalized_url):
            response = requests.get(normalized_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            for attempt in range(RATE_LIMITED_RETRIES):
                if getattr(response, "status_code", None) != 429:
                    break
                # One retry, then the publisher is left alone: retrying every article of a
                # publisher that is refusing them is what made a scan take minutes.
                time.sleep(RATE_LIMITED_WAIT_SECONDS)
                response = requests.get(normalized_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        if getattr(response, "status_code", None) == 429:
            cool_host(normalized_url)
        response.raise_for_status()
    except requests.RequestException as error:
        return {
            "url": normalized_url,
            "status": "error",
            "error": f"Could not download article: {error}",
            "title": None,
            "text": "",
            "word_count": 0,
            "extraction_quality": "unavailable",
        }

    soup = BeautifulSoup(response.text, "html.parser")
    final_url = getattr(response, 'url', normalized_url)
    if isinstance(final_url, str):
        normalized_url = normalize_article_url(final_url)
        rejection = article_url_rejection(normalized_url)
        if rejection:
            return {'url': normalized_url, 'status': 'skipped', 'error': 'redirect_' + rejection,
                    'title': None, 'text': '', 'word_count': 0, 'extraction_quality': 'unavailable'}
    json_text = _json_article_text(soup)

    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    og_title = _meta_content(soup, "og:title", "twitter:title")
    description = _meta_content(soup, "description", "og:description", "twitter:description")
    title = _clean_text(og_title or title or "")
    paragraph_text = _paragraph_text(soup)
    text = json_text or paragraph_text
    extraction_method = "paragraphs" if text == paragraph_text and text else "structured_data"

    if _word_count(text) < THIN_ARTICLE_WORDS:
        trafilatura_text = _trafilatura_text(response.text, normalized_url)
        if _word_count(trafilatura_text) > _word_count(text):
            text = trafilatura_text
            extraction_method = "trafilatura"

    if _word_count(text) < MIN_ARTICLE_WORDS:
        metadata_text = _clean_text(" ".join([title or "", description or "", json_text or ""]))
        if _word_count(metadata_text) > _word_count(text):
            text = metadata_text
            extraction_method = "metadata"

    words = _word_count(text)

    if words < MIN_METADATA_WORDS:
        return {
            "url": normalized_url,
            "status": "skipped",
            "error": "Extracted article text is too short or possibly paywalled.",
            "title": title,
            "description": description,
            "text": text,
            "word_count": words,
            "extraction_method": extraction_method,
            "extraction_quality": _extraction_quality(words),
        }

    return remember_article(normalized_url, {
        "url": normalized_url,
        "status": "extracted",
        "error": None,
        "title": title,
        "description": description,
        "text": text,
        "word_count": words,
        "extraction_method": extraction_method,
        "extraction_quality": _extraction_quality(words),
    })
