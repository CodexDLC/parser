"""CLI для локальной подготовки single-admin environment secrets."""

import argparse
import getpass
import secrets
from dataclasses import dataclass

from aibot.cabinet.passwords import hash_password


@dataclass(frozen=True)
class CabinetCredentials:
    """Сгенерированные значения без plaintext password."""

    username: str
    password_hash: str
    session_secret: str


def build_credentials(
    *,
    username: str,
    password: str,
    session_secret: str | None = None,
) -> CabinetCredentials:
    """Создать Argon2 hash и отдельный случайный session signing secret."""

    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Cabinet username must not be empty")
    if len(password) < 12:
        raise ValueError("Cabinet password must contain at least 12 characters")
    return CabinetCredentials(
        username=normalized_username,
        password_hash=hash_password(password),
        session_secret=session_secret or secrets.token_urlsafe(48),
    )


def render_env(credentials: CabinetCredentials) -> str:
    """Сформировать строки для ручного переноса в ignored env-файл."""

    return "\n".join(
        (
            f'CABINET_USERNAME="{credentials.username}"',
            f'CABINET_PASSWORD_HASH="{credentials.password_hash}"',
            f'CABINET_SESSION_SECRET="{credentials.session_secret}"',
        )
    )


def main() -> int:
    """Интерактивно запросить пароль и вывести готовые environment values."""

    parser = argparse.ArgumentParser(
        description="Generate Project M4 single-admin cabinet credentials.",
    )
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    password = getpass.getpass("Cabinet password: ")
    confirmation = getpass.getpass("Repeat cabinet password: ")
    if password != confirmation:
        parser.error("Passwords do not match")
    credentials = build_credentials(username=args.username, password=password)
    print(render_env(credentials))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
