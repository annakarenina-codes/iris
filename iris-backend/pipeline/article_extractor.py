"""
Article text extraction for IRIS.

This module downloads a news URL and extracts readable article text using
BeautifulSoup. It keeps the logic simple for Week 2: title, paragraphs, word
count, and paywall/short-content detection.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List

try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment setup
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - depends on local environment setup
    BeautifulSoup = None


REQUEST_TIMEOUT_SECONDS = 5
MIN_ARTICLE_WORDS = 100
MIN_METADATA_WORDS = 8


def _clean_text(text: str) -> str:
    """Removes extra spaces and blank lines from extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    """Counts normal words in article text."""
    return len(re.findall(r"\b\w+\b", text))


def normalize_article_url(url: str) -> str:
    """Removes common copy/paste punctuation from article URLs."""
    return (url or "").strip().rstrip(").,;]")


def _meta_content(soup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(tag["content"])

        tag = soup.find("meta", property=name)
        if tag and tag.get("content"):
            return _clean_text(tag["content"])

    return ""


def _json_values(payload, keys: set) -> List[str]:
    values = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, str):
                cleaned = _clean_text(value)
                if cleaned:
                    values.append(cleaned)
            elif isinstance(value, (dict, list)):
                values.extend(_json_values(value, keys))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_json_values(item, keys))

    return values


def _json_article_text(soup) -> str:
    """Extracts article text from structured data when paragraphs are absent."""
    text_keys = {"articleBody", "headline", "description"}
    values = []

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue

        try:
            payload = json.loads(raw)
        except ValueError:
            continue

        values.extend(_json_values(payload, text_keys))

    return _clean_text(" ".join(values))


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

    return _clean_text(" ".join(paragraphs))


def extract_article_text(url: str) -> Dict[str, object]:
    """
    Downloads and extracts readable text from a news article URL.

    Returns a dictionary with an extraction status instead of raising errors, so
    app.py can continue even if one article fails.
    """
    normalized_url = normalize_article_url(url)

    if requests is None:
        return {
            "url": normalized_url,
            "status": "error",
            "error": "The requests package is not installed.",
            "title": None,
            "text": "",
            "word_count": 0,
        }

    if BeautifulSoup is None:
        return {
            "url": normalized_url,
            "status": "error",
            "error": "The beautifulsoup4 package is not installed.",
            "title": None,
            "text": "",
            "word_count": 0,
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(normalized_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        return {
            "url": normalized_url,
            "status": "error",
            "error": f"Could not download article: {error}",
            "title": None,
            "text": "",
            "word_count": 0,
        }

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    og_title = _meta_content(soup, "og:title", "twitter:title")
    description = _meta_content(soup, "description", "og:description", "twitter:description")
    title = _clean_text(og_title or title or "")
    paragraph_text = _paragraph_text(soup)
    json_text = _json_article_text(soup)
    text = paragraph_text if _word_count(paragraph_text) >= _word_count(json_text) else json_text
    extraction_method = "paragraphs" if text == paragraph_text and text else "structured_data"

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
        }

    return {
        "url": normalized_url,
        "status": "extracted",
        "error": None,
        "title": title,
        "description": description,
        "text": text,
        "word_count": words,
        "extraction_method": extraction_method,
    }
