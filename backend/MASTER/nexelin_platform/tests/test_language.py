import pytest
from MASTER.nexelin_platform.language import detect_language


class TestLanguageDetection:
    def test_english(self):
        assert detect_language('Hello, how are you doing today?') == 'en'

    def test_german(self):
        assert detect_language('Guten Tag, wie geht es Ihnen?') == 'de'

    def test_french(self):
        assert detect_language("Bonjour, comment allez-vous aujourd'hui?") == 'fr'

    def test_short_text_returns_fallback(self):
        assert detect_language('hi', fallback='de') == 'de'

    def test_empty_returns_fallback(self):
        assert detect_language('', fallback='en') == 'en'

    def test_none_returns_fallback(self):
        assert detect_language(None, fallback='en') == 'en'
