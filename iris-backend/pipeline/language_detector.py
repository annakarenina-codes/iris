from lingua import Language, LanguageDetectorBuilder

# Build detector supporting English and Tagalog
detector = LanguageDetectorBuilder.from_languages(
    Language.ENGLISH,
    Language.TAGALOG
).build()

def detect_language(text: str) -> str:
    """
    Detects whether the input text is English, Tagalog, or Taglish.
    Taglish is identified when confidence for both languages is significant.
    """
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