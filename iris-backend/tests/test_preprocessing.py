"""
Simple Week 1 preprocessing checks.

Run from the iris-backend folder:
    python tests/test_preprocessing.py

This file uses plain assert statements so beginners do not need pytest yet.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.opinion_filter import is_opinion
from pipeline.political_checker import flag_political


OPINION_SAMPLES = [
    "Sa tingin ko, masama ang bagong policy.",
    "I believe this is the worst decision.",
    "Para sa akin, dapat ayusin ito agad.",
    "Personally, this is better than the old system.",
    "Palagay ko hindi maganda ang serbisyo.",
    "In my opinion, the plan should be changed.",
    "I feel na pangit ang proposal.",
    "Opinyon ko lang, dapat mas simple ito.",
]

FACTUAL_SAMPLES = [
    "The Department of Health reported new dengue cases.",
    "GMA News published an article about the weather update.",
    "The Philippine Statistics Authority released inflation data.",
    "A fire occurred in Quezon City on Monday.",
]

POLITICAL_SAMPLES = [
    "The president signed a new law today.",
    "COMELEC announced rules for the election.",
    "The mayor gave a statement about the flood response.",
    "DILG released a memorandum for barangay officials.",
    "Senator Marcos filed a new bill.",
    "Maraming botante ang bumoto noong halalan.",
    "The Department of Justice investigated a corruption complaint.",
    "PhilHealth announced a new contribution policy.",
]

NON_POLITICAL_SAMPLES = [
    "The Department of Health reported new dengue cases.",
    "DOH reminded the public to remove mosquito breeding sites.",
    "A local school won a robotics competition.",
    "The weather bureau reported possible rainfall.",
    "A new restaurant opened in Cabanatuan City.",
    "The basketball team won the championship.",
]


def run_checks() -> None:
    for sample in OPINION_SAMPLES:
        result = is_opinion(sample)
        assert result["is_opinion"], f"Expected opinion: {sample}"

    for sample in FACTUAL_SAMPLES:
        result = is_opinion(sample)
        assert not result["is_opinion"], f"Expected factual/non-opinion: {sample}"

    for sample in POLITICAL_SAMPLES:
        result = flag_political(sample)
        assert result["politically_sensitive"], f"Expected political flag: {sample}"

    for sample in NON_POLITICAL_SAMPLES:
        result = flag_political(sample)
        assert not result["politically_sensitive"], f"Expected no political flag: {sample}"

    print("All Week 1 preprocessing checks passed.")
    print(f"Opinion samples tested: {len(OPINION_SAMPLES) + len(FACTUAL_SAMPLES)}")
    print(f"Political samples tested: {len(POLITICAL_SAMPLES) + len(NON_POLITICAL_SAMPLES)}")


if __name__ == "__main__":
    run_checks()
