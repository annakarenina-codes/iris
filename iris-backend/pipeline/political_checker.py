"""
Political sensitivity checker for IRIS.

This does not decide whether a claim is true or false. It only adds a warning
flag when the topic involves elections, public officials, political
institutions, government controversy, or policy-sensitive issues.
"""

from __future__ import annotations

import re
from typing import Dict, List


ELECTION_KEYWORDS = [
    "election",
    "campaign",
    "vote",
    "voter",
    "ballot",
    "comelec",
    "halalan",
    "botante",
    "boto",
    "eleksyon",
]

PUBLIC_OFFICIAL_KEYWORDS = [
    "president",
    "vice president",
    "senator",
    "congressman",
    "congresswoman",
    "councilor",
    "mayor",
    "governor",
    "barangay official",
    "barangay officials",
    "barangay captain",
    "public official",
    "bato dela rosa",
    "robin padilla",
    "ferdinand marcos",
    "marcos jr",
    "bbm",
    "pangulo",
    "pangulong",
    "bise presidente",
    "senador",
    "alkalde",
    "gobernador",
    "konsehal",
]

POLITICAL_INSTITUTION_KEYWORDS = [
    "senate",
    "senate of the philippines",
    "house of representatives",
    "congress",
    "malacanang",
    "comelec",
    "senado",
    "kongreso",
    "political party",
    "party-list",
    "administration",
    "opposition",
    "philippine government",
]

GOVERNMENT_CONTROVERSY_KEYWORDS = [
    "corruption",
    "graft",
    "bribery",
    "plunder",
    "impeachment",
    "red-tagging",
    "confidential funds",
    "pork barrel",
    "public funds",
    "abuse of power",
    "check and balance",
    "scandal",
    "anomalous",
    "senate probe",
    "house probe",
    "congressional hearing",
]

POLICY_SENSITIVE_KEYWORDS = [
    "new law",
    "bill",
    "tax",
    "license revocation",
    "revoke license",
    "revoke licenses",
    "budget",
    "subsidy",
    "fare hike",
    "price cap",
    "minimum wage",
    "wage hike",
    "contribution policy",
    "mandatory contribution",
    "mandatory vaccination",
    "vaccine mandate",
    "charter change",
    "martial law",
    "anti-terror",
    "sovereignty",
    "territorial dispute",
]

POLITICAL_CATEGORIES = {
    "elections": ELECTION_KEYWORDS,
    "public_officials": PUBLIC_OFFICIAL_KEYWORDS,
    "political_institutions": POLITICAL_INSTITUTION_KEYWORDS,
    "government_controversy": GOVERNMENT_CONTROVERSY_KEYWORDS,
    "policy_sensitive": POLICY_SENSITIVE_KEYWORDS,
}

GOVERNMENT_AGENCY_KEYWORDS = [
    "department of health",
    "doh",
    "department of education",
    "deped",
    "department of justice",
    "doj",
    "dilg",
    "pnp",
    "philhealth",
]


def _normalize(text: str) -> str:
    """Lowercase text and make spacing predictable for keyword matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has_term(text: str, term: str) -> bool:
    """Matches terms as words or phrases instead of loose substrings."""
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text))


def _matched_terms(text: str, terms: List[str]) -> List[str]:
    """Returns the configured terms found in the normalized text."""
    return [term for term in terms if _has_term(text, term)]


def flag_political(text: str) -> Dict[str, object]:
    """
    Checks whether text should receive the Politically Sensitive overlay.

    The returned flag can attach to any final verdict later, such as Verified or
    Not Found.
    """
    normalized = _normalize(text)
    matched_categories = {
        category: _matched_terms(normalized, keywords)
        for category, keywords in POLITICAL_CATEGORIES.items()
    }
    matched_keywords: List[str] = [
        keyword
        for keywords in matched_categories.values()
        for keyword in keywords
    ]

    matched_agencies = _matched_terms(normalized, GOVERNMENT_AGENCY_KEYWORDS)

    return {
        "politically_sensitive": bool(matched_keywords),
        "matched_keywords": matched_keywords,
        "matched_agencies": matched_agencies,
        "matched_categories": matched_categories,
    }
