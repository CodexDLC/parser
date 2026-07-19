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


class PublishingFailedError(Exception):
    """Публикация поста завершилась ошибкой внешнего сервиса."""
