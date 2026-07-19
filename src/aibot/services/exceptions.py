"""Исключения сервисного слоя приложения."""


class EntityNotFoundError(Exception):
    """Запрошенная сущность не найдена."""


class EntityAlreadyExistsError(Exception):
    """Создание сущности нарушает правило уникальности."""


class UnsupportedSourceTypeError(Exception):
    """Источник пока не поддерживается текущим прототипом."""


class InvalidPostStateError(Exception):
    """Пост находится в состоянии, которое не позволяет выполнить операцию."""


class InvalidNewsStateError(Exception):
    """Новость находится в состоянии, которое не позволяет выполнить операцию."""


class ConcurrentGenerationError(Exception):
    """Другой worker уже генерирует пост для этой новости."""


class ConcurrentPublicationError(Exception):
    """Другой worker уже публикует этот пост."""


class PublishingFailedError(Exception):
    """Публикация поста завершилась ошибкой внешнего сервиса."""
