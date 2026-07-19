"""Контракт детерминированной компоновки Telegram-поста."""

from aibot.services.telegram_post_composer import TelegramPostComposer


def test_composer_appends_http_source_url_to_ai_body() -> None:
    composer = TelegramPostComposer()

    result = composer.compose(
        "Готовый текст новости.",
        source_url="https://habr.com/ru/articles/123/",
    )

    assert result == (
        "Готовый текст новости.\n\n"
        "🔗 Источник:\n"
        "https://habr.com/ru/articles/123/"
    )


def test_composer_preserves_body_when_source_url_is_missing() -> None:
    composer = TelegramPostComposer()

    assert composer.compose("Готовый текст новости.", source_url=None) == (
        "Готовый текст новости."
    )


def test_composer_does_not_publish_unsupported_source_scheme() -> None:
    composer = TelegramPostComposer()

    assert composer.compose(
        "Готовый текст новости.",
        source_url="javascript:alert(1)",
    ) == "Готовый текст новости."
