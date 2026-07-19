"""Argon2 password hashing boundary для single-admin кабинета."""

from pwdlib import PasswordHash

_PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Создать Argon2 hash для настройки CABINET_PASSWORD_HASH."""

    return _PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Безопасно проверить пароль без проброса деталей password backend."""

    try:
        return _PASSWORD_HASH.verify(password, password_hash)
    except Exception:
        return False
