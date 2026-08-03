try:
    from lingua import Language, LanguageDetectorBuilder
except ImportError:  # pragma: no cover - depends on local environment setup
    Language = None
    LanguageDetectorBuilder = None

# Build detector supporting English and Tagalog
detector = None
if LanguageDetectorBuilder is not None:
    detector = LanguageDetectorBuilder.from_languages(
        Language.ENGLISH,
        Language.TAGALOG
    ).build()

TAGALOG_MARKERS = {
    "ang",
    "mga",
    "ng",
    "sa",
    "si",
    "nila",
    "tayo",
    "dapat",
    "ayon",
    "sinabi",
    "panalo",
    "parin",
}


def _fallback_detect_language(text: str) -> str:
    words = {
        word.strip(".,!?;:()[]{}\"'`").lower()
        for word in text.split()
    }
    tagalog_hits = words.intersection(TAGALOG_MARKERS)

    if tagalog_hits and len(tagalog_hits) >= 2:
        return "taglish"

    if tagalog_hits:
        return "tagalog"

    return "english"

def detect_language(text: str) -> str:
    """
    Detects whether the input text is English, Tagalog, or Taglish.
    Taglish is identified when confidence for both languages is significant.
    """
    if detector is None:
        return _fallback_detect_language(text)

    try:
        results = detector.compute_language_confidence_values(text)

        english_conf = 0.0
        tagalog_conf = 0.0

        for result in results:
            if result.language == Language.ENGLISH:
                english_conf = result.value
            elif result.language == Language.TAGALOG:
                tagalog_conf = result.value

        # If both languages have meaningful confidence, classify as Taglish
        if english_conf > 0.2 and tagalog_conf > 0.2:
            return "taglish"
        elif tagalog_conf > english_conf:
            return "tagalog"
        else:
            return "english"

    except Exception as e:
        print(f"Language detection error: {e}")
        return "english"  # Default to English if detection fails
