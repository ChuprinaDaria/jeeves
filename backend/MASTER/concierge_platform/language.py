from lingua import Language, LanguageDetectorBuilder

_CODE_TO_LINGUA = {
    'en': Language.ENGLISH,
    'de': Language.GERMAN,
    'fr': Language.FRENCH,
    'es': Language.SPANISH,
    'it': Language.ITALIAN,
    'nl': Language.DUTCH,
    'da': Language.DANISH,
}

_LINGUA_TO_CODE = {v: k for k, v in _CODE_TO_LINGUA.items()}

_detector = None


def get_detector():
    """Build detector lazily from PlatformDefaults.supported_languages."""
    global _detector
    if _detector is None:
        from MASTER.concierge_platform.models import PlatformDefaults
        defaults = PlatformDefaults.get()
        languages = []
        for code in (defaults.supported_languages or list(_CODE_TO_LINGUA.keys())):
            lang = _CODE_TO_LINGUA.get(code)
            if lang:
                languages.append(lang)
        if not languages:
            languages = list(_CODE_TO_LINGUA.values())
        _detector = LanguageDetectorBuilder.from_languages(*languages).build()
    return _detector


def detect_language(text: str, fallback: str = 'en') -> str:
    """Detect language from text. Returns ISO 639-1 code.
    Short text (<4 chars) or undetectable -> fallback."""
    if not text or len(text.strip()) < 4:
        return fallback
    detector = get_detector()
    result = detector.detect_language_of(text.strip())
    if result is None:
        return fallback
    return _LINGUA_TO_CODE.get(result, fallback)
