"""OpenAI RAG fallback for low-confidence IRIS verdicts."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

from pipeline.verdict_generator import VERIFIED_THRESHOLD


load_dotenv()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ALLOWED_VERDICTS = {"Verified", "Partially Verified", "Not Found"}
MAX_REASON_CHARS = 180

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on local environment setup
    OpenAI = None


def _get_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def needs_openai_fallback(verdict_result: Dict[str, object]) -> bool:
    primary_evidence = verdict_result.get("primary_evidence") or {}
    best_score = float(primary_evidence.get("similarity_score") or 0.0)
    return best_score < VERIFIED_THRESHOLD


def _evidence_items(articles: List[Dict[str, object]]) -> List[Dict[str, object]]:
    extracted_articles = [
        article
        for article in articles
        if article.get("status") == "extracted" and article.get("text")
    ]

    items = []
    for article in extracted_articles[:5]:
        text = str(article.get("text") or "")
        items.append({
            "source": article.get("source"),
            "title": article.get("title"),
            "url": article.get("url"),
            "snippet": text[:1200],
        })

    return items


def _parse_response(content: str) -> Dict[str, str]:
    payload = json.loads(content)
    verdict = payload.get("verdict")

    if verdict not in ALLOWED_VERDICTS:
        verdict = "Not Found"

    reason = str(payload.get("reason") or "OpenAI reviewed the retrieved evidence.")
    reason = " ".join(reason.split())

    if len(reason) > MAX_REASON_CHARS:
        reason = reason[:MAX_REASON_CHARS].rsplit(" ", 1)[0].rstrip(".,;:")
        reason = f"{reason}."

    return {
        "verdict": verdict,
        "reason": reason,
    }


def refine_with_openai_rag(
    claim: str,
    articles: List[Dict[str, object]],
    verdict_result: Dict[str, object],
) -> Dict[str, object]:
    """
    Uses OpenAI only when sentence-transformer similarity is low-confidence.

    The model must reason only over retrieved evidence snippets.
    """
    if not needs_openai_fallback(verdict_result):
        return {
            "used": False,
            "status": "not_needed",
            "error": None,
            "result": None,
        }

    evidence = _evidence_items(articles)
    if not evidence:
        return {
            "used": False,
            "status": "no_evidence",
            "error": "No readable evidence snippets were available.",
            "result": None,
        }

    if OpenAI is None:
        return {
            "used": False,
            "status": "missing_dependency",
            "error": "The openai package is not installed.",
            "result": None,
        }

    api_key = _get_api_key()
    if not api_key:
        return {
            "used": False,
            "status": "missing_api_key",
            "error": "Missing OPENAI_API_KEY in .env.",
            "result": None,
        }

    system_prompt = (
        "You are the IRIS evidence reviewer. Decide whether the claim is "
        "supported only by the provided retrieved evidence snippets. Do not use "
        "outside knowledge. Match the specific claim, not merely a related topic. "
        "For example, evidence about flood control projects does not verify a "
        "claim about flood aid unless the evidence explicitly mentions aid, "
        "assistance, relief, or distribution to residents. Use Not Found when "
        "the evidence is only related but does not confirm the specific claim. "
        "Return JSON only with keys verdict and reason. Allowed verdicts: "
        "Verified, Partially Verified, Not Found. Keep reason to one short "
        "sentence under 25 words."
    )
    user_prompt = json.dumps({
        "claim": claim,
        "current_similarity_verdict": verdict_result.get("verdict"),
        "current_primary_evidence": verdict_result.get("primary_evidence"),
        "evidence": evidence,
    })

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = _parse_response(content)
    except Exception as error:
        return {
            "used": False,
            "status": "error",
            "error": f"OpenAI RAG fallback failed: {error}",
            "result": None,
        }

    result["fallback_method"] = "openai_rag"
    return {
        "used": True,
        "status": "ok",
        "error": None,
        "result": result,
    }
