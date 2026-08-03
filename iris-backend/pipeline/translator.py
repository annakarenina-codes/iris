try:
    from deep_translator import GoogleTranslator
except ImportError:  # pragma: no cover - depends on local environment setup
    GoogleTranslator = None

def translate_to_english(text: str, language: str) -> str:
    """
    Translates Tagalog or Taglish text to English for searching.
    If text is already English, returns it unchanged.
    """
    if language == "english":
        return text  # No translation needed

    if GoogleTranslator is None:
        print("Translation unavailable: deep-translator is not installed.")
        return text

    try:
        translated = GoogleTranslator(
            source='auto',
            target='english'
        ).translate(text)

        print(f"[Translator] Original: {text}")
        print(f"[Translator] Translated: {translated}")

        return translated

    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original if translation fails
