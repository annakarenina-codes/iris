"""
Article text extraction for IRIS.

This module downloads a news URL and extracts readable article text using
BeautifulSoup. It keeps the logic simple for Week 2: title, paragraphs, word
count, and paywall/short-content detection.
"""

from __future__ import annotations

import re
from typing import Dict

import requests
from bs4 import BeautifulSoup


REQUEST_TIMEOUT_SECONDS = 5
MIN_ARTICLE_WORDS = 100


def _clean_text(text: str) -> str:
    """Removes extra spaces and blank lines from extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    """Counts normal words in article text."""
    return len(re.findall(r"\b\w+\b", text))


def extract_article_text(url: str) -> Dict[str, object]:
    """
    Downloads and extracts readable text from a news article URL.

    Returns a dictionary with an extraction status instead of raising errors, so
    app.py can continue even if one article fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        return {
            "url": url,
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

    containers = soup.find_all(["article", "main"])
    if not containers:
        containers = [soup]

    paragraphs = []
    for container in containers:
        for paragraph in container.find_all("p"):
            cleaned = _clean_text(paragraph.get_text(" ", strip=True))
            if cleaned and len(cleaned.split()) >= 5:
                paragraphs.append(cleaned)

    text = _clean_text(" ".join(paragraphs))
    words = _word_count(text)

    if words < MIN_ARTICLE_WORDS:
        return {
            "url": url,
            "status": "skipped",
            "error": "Extracted article text is too short or possibly paywalled.",
            "title": title,
            "text": text,
            "word_count": words,
        }

    return {
        "url": url,
        "status": "extracted",
        "error": None,
        "title": title,
        "text": text,
        "word_count": words,
    }
