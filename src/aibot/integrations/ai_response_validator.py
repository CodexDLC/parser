"""Проверка готовности AI-ответа к сохранению и Telegram-публикации."""

import re
from dataclasses import dataclass


class AIResponseValidationError(ValueError):
    """AI вернул текст, который нельзя безопасно считать готовым постом."""


@dataclass(frozen=True)
class PlainTextTelegramPostValidator:
    """Пропускать только законченный plain-text пост разумной длины."""

    min_characters: int = 180
    max_characters: int = 900

    def validate(self, text: str | None) -> str:
        """Нормализовать края и отклонить пустой, оборванный или размеченный ответ."""

        normalized = (text or "").strip()
        if not normalized:
            raise AIResponseValidationError("AI response is empty")
        if len(normalized) < self.min_characters:
            raise AIResponseValidationError("AI response is incomplete: text is too short")
        if len(normalized) > self.max_characters:
            raise AIResponseValidationError("AI response exceeds Telegram post length policy")
        if self._contains_markup(normalized):
            raise AIResponseValidationError("AI response contains forbidden markup")
        if re.search(r'[.!?…](?:["»”)\]])?$', normalized) is None:
            raise AIResponseValidationError(
                "AI response is incomplete: final sentence is not finished"
            )
        return normalized

    @staticmethod
    def _contains_markup(text: str) -> bool:
        """Найти Markdown/HTML, запрещённые plain-text контрактом публикации."""

        return any(marker in text for marker in ("**", "__", "`")) or bool(
            re.search(r"</?[a-z][^>]*>", text, flags=re.IGNORECASE)
        )
