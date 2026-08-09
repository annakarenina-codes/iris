"""
Simple Week 4 helper checks.

Run from the iris-backend folder:
    python tests/test_week4_helpers.py
"""

from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.cache import get_cached_verdict, hash_claim, save_cached_verdict
from pipeline.claim_extractor import (
    _fallback_extract_claims,
    _fallback_ignored_segments,
    _parse_claim_response,
)
from pipeline.content_profiler import profile_content
from pipeline.keyword_fallback import keyword_overlap_verdict
from pipeline.openai_fallback import _parse_response
from pipeline.political_checker import flag_political


def run_checks() -> None:
    opinion_profile = profile_content(
        "Sa tingin ko, masama ang bagong policy.",
        use_ai=False,
    )
    assert opinion_profile["eligible_for_verification"] is False
    assert opinion_profile["recommended_route"] == "stop_opinion_detected"
    assert opinion_profile["post_type"] == "opinion_only"

    mixed_profile = profile_content(
        "The Department of Health reported 1,000 dengue cases. "
        "This administration is useless.",
        use_ai=False,
    )
    assert mixed_profile["eligible_for_verification"] is True
    assert mixed_profile["recommended_route"] == "verify_factual_claims_only"
    assert mixed_profile["post_type"] == "mixed_content"
    assert mixed_profile["contains_opinion"] is True
    assert "Department of Health reported" in mixed_profile["verification_text"]
    assert any(
        segment["segment_type"] == "opinion"
        for segment in mixed_profile["ignored_segments"]
    )

    forecast_profile = profile_content(
        "The economy will collapse next year.",
        use_ai=False,
    )
    assert forecast_profile["eligible_for_verification"] is False
    assert forecast_profile["recommended_route"] == "stop_forecast_projection"
    assert forecast_profile["contains_forecast_or_projection"] is True

    claims = _fallback_extract_claims(
        "DOH reported new dengue cases. The mayor announced flood aid."
    )
    assert len(claims) == 2
    assert claims[0]["claim_id"] == 1
    assert "dengue" in claims[0]["normalized_claim"].lower()

    messy_post = (
        "Fugitive Bato Dela Rosa has a whopping 118 licensed firearms. "
        "Some pistols. Some shotguns. And a lot of rifles. Delikado! "
        "As a fugitive from justice, the PNP should REVOKE all of his licenses."
    )
    messy_claims = _fallback_extract_claims(messy_post)
    messy_ignored = _fallback_ignored_segments(messy_post)

    assert len(messy_claims) == 2
    assert messy_claims[0]["normalized_claim"] == "Bato Dela Rosa has a whopping 118 licensed firearms."
    assert "weapons_claim" in messy_claims[0]["risk_tags"]
    assert "criminal_allegation" in messy_claims[1]["risk_tags"]
    assert any(segment["segment_type"] == "opinion" for segment in messy_ignored)
    assert any(segment["segment_type"] == "recommendation" for segment in messy_ignored)

    non_factual = _fallback_extract_claims(
        "Mulat na mga Pilipino sa fake news ng kadiliman. We support and protect BBM."
    )
    assert non_factual == []

    attributed_post = (
        "The rush to blame video games for school violence is not supported by science, "
        "a cybersecurity and technology expert said Saturday. Cybersecurity and "
        "technology expert Art Samaniego Jr. made the argument in an interview on "
        "DZRH News program \"Special on Saturday\" on July 4, citing research by "
        "the Oxford Internet Institute showing no direct link between violent "
        "video games and real-world crime or violence. "
        "He said the real cause of the Tacloban school shooting was not GoreBox, but "
        "the people the child was communicating with online. He warned that banning "
        "GoreBox specifically is futile since more than 20 similar games exist."
    )
    attributed_claims = _fallback_extract_claims(attributed_post)

    assert attributed_claims
    assert attributed_claims[0]["claim_type"] == "attributed_statement"
    assert attributed_claims[0]["verification_focus"] == "speaker_attribution"
    assert attributed_claims[0]["attribution"]["speaker"] == "Art Samaniego Jr."
    assert attributed_claims[0]["attribution"]["role"] == "Cybersecurity and technology expert"
    assert attributed_claims[0]["attribution"]["source"] == "DZRH News"
    assert attributed_claims[0]["attribution"]["program"] == "Special on Saturday"
    assert attributed_claims[0]["attribution"]["date"] == "July 4"
    assert attributed_claims[0]["claim_text"].startswith(
        "Cybersecurity and technology expert Art Samaniego Jr. made the argument"
    )
    assert "Oxford Internet Institute" in attributed_claims[0]["claim_text"]
    assert attributed_claims[0]["normalized_claim"].startswith(
        "Cybersecurity and technology expert Art Samaniego Jr. said in an interview on DZRH News"
    )
    assert "Oxford Internet Institute" in attributed_claims[0]["normalized_claim"]
    assert "Art Samaniego Jr." in attributed_claims[0]["search_query"]
    assert "Oxford" in attributed_claims[0]["search_query"]
    assert any(
        "GoreBox" in claim["normalized_claim"]
        and claim["normalized_claim"].startswith("Cybersecurity and technology expert Art Samaniego Jr. said")
        for claim in attributed_claims
    )

    carpenter_post = (
        "His work helped defend the Philippines. "
        "American marine biologist Dr. Kent Carpenter, whose scientific testimony "
        "supported the Philippines in its landmark 2016 South China Sea arbitration "
        "case against China, was shot and killed during a home invasion in Negros "
        "Oriental province in the Central Visayas region of the Philippines. "
        "Police said three unidentified men forcibly entered Carpenter's home in "
        "Barangay Ajong, Sibulan, on the night of July 12. One of the intruders "
        "allegedly shot the 73-year-old scientist in the head, killing him. His "
        "34-year-old companion was also injured. The suspects remain at large, and "
        "investigators are reviewing CCTV footage, interviewing witnesses, and "
        "pursuing leads. Police Brigadier General Romano Cardi\u00f1o condemned the "
        "killing as a \"senseless act of violence\" and vowed to bring those "
        "responsible to justice. Carpenter was widely respected in the scientific "
        "community for his decades of work in the Philippines. He first began "
        "studying the country's marine ecosystems in 1975 and became one of the "
        "world's leading experts on Philippine marine biodiversity. Beyond his "
        "scientific achievements, Carpenter also played a significant role in one "
        "of the Philippines' biggest international legal victories. During the "
        "South China Sea arbitration initiated by the Philippines in 2013, he "
        "submitted expert written evidence documenting the environmental damage "
        "caused by China's island reclamation and destructive fishing practices in "
        "the West Philippine Sea. He also delivered oral testimony during the 2015 "
        "merits hearing. The tribunal's 2016 ruling overwhelmingly favored the "
        "Philippines and found no legal basis for China's sweeping \"nine-dash "
        "line\" claims. Carpenter also conducted extensive research in the Verde "
        "Island Passage, often called the \"center of the center\" of global marine "
        "shore fish biodiversity, and was a strong advocate for having the area "
        "recognized as a UNESCO World Heritage Site. His death has prompted "
        "tributes from Silliman University, the University of the Philippines "
        "Marine Science Institute, conservation groups, and fellow scientists. "
        "Many remembered him not only as a world-class researcher, but also as a "
        "generous mentor who spent five decades helping Filipinos better understand "
        "and protect their country's extraordinary marine ecosystems. His life "
        "reminds us that science can shape history just as much as politics or "
        "diplomacy."
    )
    carpenter_profile = profile_content(carpenter_post, use_ai=False)
    carpenter_claims = _fallback_extract_claims(carpenter_profile["verification_text"])
    carpenter_text = " ".join(claim["normalized_claim"] for claim in carpenter_claims)

    assert len(carpenter_claims) == 10
    assert "provided expert testimony or evidence" in carpenter_claims[0]["normalized_claim"]
    assert "submitted expert written evidence" in carpenter_claims[0]["normalized_claim"]
    assert "delivered oral testimony during the 2015 merits hearing" in carpenter_claims[0]["normalized_claim"]
    assert "shot and killed during a home invasion" in carpenter_claims[1]["normalized_claim"]
    assert "Barangay Ajong, Sibulan" in carpenter_claims[1]["normalized_claim"]
    assert "34-year-old companion was injured" in carpenter_claims[2]["normalized_claim"]
    assert "suspects remain at large" in carpenter_claims[3]["normalized_claim"]
    assert carpenter_claims[4]["claim_type"] == "attributed_statement"
    assert carpenter_claims[4]["attribution"]["speaker"] == "Romano Cardi\u00f1o"
    assert "senseless act of violence" in carpenter_claims[4]["normalized_claim"]
    assert "began studying the Philippines' marine ecosystems in 1975" in carpenter_text
    assert "2016 ruling favored the Philippines" in carpenter_text
    assert "Verde Island Passage" in carpenter_text
    assert "UNESCO World Heritage Site" in carpenter_text
    assert "issued tributes following Kent Carpenter's death" in carpenter_text
    assert "His work helped defend" not in carpenter_text
    assert "widely respected" not in carpenter_text
    assert "leading experts" not in carpenter_text
    assert "world-class" not in carpenter_text
    assert "generous mentor" not in carpenter_text
    assert "reminds us" not in carpenter_text

    padilla_post = (
        "'HAVE YOU ALREADY VISITED BARMM?' "
        "Senator-judge Robinhood Padilla asked former state auditor Roderick Wamil "
        "if he had ever visited the Bangsamoro Autonomous Region in Muslim Mindanao "
        "(BARMM) and whether he was aware of the country's ongoing terrorism threats. "
        "During his interjection, Padilla raised preliminary questions about the "
        "Audit Observation Memorandum, trying to establish ties to the confidential "
        "funds used by Vice President Sara Duterte for surveillance on potential "
        "New People's Army (NPA) recruitment. "
        "\"But you are the ones in charge of the investigation regarding the "
        "confidential funds, is that correct?\" Padilla asked Wamil. "
        "\"It is not an investigation. It is an evaluation,\" the witness answered. "
        "\"Do you believe that confidential agents should be identified? State "
        "their real names,\" the senator furthered. "
        "\"There are no provisions for that in the joint circular,\" Wamil said. "
        "Padilla then asked Wamil to define \"confidential,\" to which the auditor "
        "replied, \"classified.\""
    )
    padilla_profile = profile_content(padilla_post, use_ai=False)
    padilla_claims = _fallback_extract_claims(padilla_profile["verification_text"])

    assert "HAVE YOU ALREADY VISITED BARMM" not in padilla_profile["verification_text"]
    assert padilla_claims[0]["search_query"] == (
        "Robinhood Padilla Roderick Wamil auditor BARMM terrorism threats security threats"
    )
    assert any(
        "Audit Observation Memorandum" in claim["normalized_claim"]
        and "confidential funds" in claim["search_query"]
        for claim in padilla_claims
    )
    assert any(
        "joint circular" in claim["normalized_claim"]
        for claim in padilla_claims
    )

    parsed_claims = _parse_claim_response(
        """
        {
            "claims": [
                {
                    "claim_text": "Samaniego said GoreBox was not the real cause.",
                    "normalized_claim": "Art Samaniego Jr. said GoreBox was not the real cause.",
                    "claim_type": "attributed_statement",
                    "verification_focus": "speaker_attribution",
                    "attribution": {
                        "speaker": "Art Samaniego Jr.",
                        "statement": "GoreBox was not the real cause.",
                        "source": "DZRH News",
                        "program": "Special on Saturday",
                        "date": "July 4"
                    },
                    "search_query": "Art Samaniego Jr DZRH News GoreBox real cause"
                }
            ],
            "ignored_segments": []
        }
        """
    )
    assert parsed_claims[0]["claim_type"] == "attributed_statement"
    assert parsed_claims[0]["search_query"].startswith("Art Samaniego Jr")

    assert flag_political("BBM has control of the Senate.")["politically_sensitive"]
    assert flag_political("Senator Robin Padilla attended the wake.")["politically_sensitive"]

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        cache_path = Path(temp_dir) / "iris_test_cache.sqlite3"
        claim_hash = hash_claim("The mayor announced flood aid.")
        result = {
            "claim_id": 1,
            "verdict": "Partially Verified",
            "message": "Cached test result.",
        }

        save_cached_verdict(
            claim_hash,
            "The mayor announced flood aid.",
            result,
            cache_path=cache_path,
        )
        cached = get_cached_verdict(claim_hash, cache_path=cache_path)
        assert cached["verdict"] == "Partially Verified"

    keyword_result = keyword_overlap_verdict(
        "The Department of Health reported new dengue cases.",
        [
            {
                "source": "GMA News",
                "title": "DOH reports dengue cases",
                "url": "https://example.com/dengue",
                "description": "Health officials report dengue cases.",
                "status": "extracted",
                "text": "The Department of Health reported new dengue cases.",
            }
        ],
    )
    assert keyword_result["verdict"] == "Partially Verified"
    assert keyword_result["keyword_overlap"] > 0

    parsed = _parse_response(
        """
        {
            "verdict": "Not Found",
            "reason": "The evidence discusses flood control projects in Quezon City, but it does not directly confirm flood aid, assistance, relief, or distribution to residents.",
            "supporting_urls": []
        }
        """
    )
    assert parsed["verdict"] == "Not Found"
    assert len(parsed["reason"]) <= 180
    assert parsed["supporting_urls"] == []

    print("All Week 4 helper checks passed.")


if __name__ == "__main__":
    run_checks()
