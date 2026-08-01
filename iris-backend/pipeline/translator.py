from deep_translator import GoogleTranslator

def translate_to_english(text: str, language: str) -> str:
    """
    Translates Tagalog or Taglish text to English for searching.
    If text is already English, returns it unchanged.
    """
    if language == "english":
        return text  # No translation needed

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