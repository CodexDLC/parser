"""Детерминированная компоновка готового Telegram-поста."""

from urllib.parse import urlsplit


class TelegramPostComposer:
    """Добавлять сохранённую ссылку источника к проверенному AI-тексту."""

    def compose(self, ai_body: str, *, source_url: str | None) -> str:
        """Вернуть финальный preview, не позволяя AI изменять ссылку."""

        body = ai_body.strip()
        safe_source_url = self._safe_source_url(source_url)
        if safe_source_url is None:
            return body
        return f"{body}\n\n🔗 Источник:\n{safe_source_url}"

    @staticmethod
    def _safe_source_url(source_url: str | None) -> str | None:
        """Пропускать только абсолютные HTTP(S)-ссылки из NewsItem."""

        normalized = (source_url or "").strip()
        if not normalized:
            return None
        try:
            parsed = urlsplit(normalized)
        except ValueError:
            return None
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        return normalized
