"""Детерминированное определение языка нормализованной новости."""

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0


class LanguageDetector:
    """Определить ISO language code или вернуть None для нераспознаваемого текста."""

    def detect(self, text: str) -> str | None:
        """Определить язык непустого текста с буквенными символами."""

        compact_text = " ".join(text.split())
        if not compact_text or not any(character.isalpha() for character in compact_text):
            return None

        try:
            language = detect(compact_text)
        except LangDetectException:
            return None
        return language.strip().lower().replace("_", "-") or None
