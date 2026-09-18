# Phrase locale codes → TokenHub language names (used in prompts)
# TokenHub HY-MT2 supports 33 languages
# Map top-level codes only — Phrase interprets e.g. "en" as covering "en_gb", "en_us", etc.

PHRASE_TO_TOKENHUB_NAME = {
    "en": "English",
    "zh": "Chinese",
    "zh_tw": "Traditional Chinese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ar": "Arabic",
    "th": "Thai",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "ms": "Malay",
    "id": "Indonesian",
    "fil": "Filipino",
    "hi": "Hindi",
    "pl": "Polish",
    "cs": "Czech",
    "nl": "Dutch",
    "km": "Khmer",
    "my": "Burmese",
    "fa": "Persian",
    "gu": "Gujarati",
    "ur": "Urdu",
    "te": "Telugu",
    "mr": "Marathi",
    "he": "Hebrew",
    "bn": "Bengali",
    "ta": "Tamil",
    "uk": "Ukrainian",
    "bo": "Tibetan",
    "kk": "Kazakh",
    "mn": "Mongolian",
    "ug": "Uyghur",
    "yue": "Cantonese",
}

# Reverse map for /languages response — only top-level codes
SUPPORTED_CODES = list(PHRASE_TO_TOKENHUB_NAME.keys())


def get_tokenhub_language_name(phrase_code: str) -> str:
    """Convert Phrase locale code to TokenHub language name for prompts."""
    return PHRASE_TO_TOKENHUB_NAME.get(phrase_code, phrase_code)