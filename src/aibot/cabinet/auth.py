"""Application service single-admin authentication и session lifecycle."""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from aibot.cabinet.passwords import verify_password
from aibot.config import Settings

SESSION_COOKIE_NAME = "m4_cabinet_session"
LOGIN_CSRF_COOKIE_NAME = "m4_cabinet_login_csrf"
LOGIN_CSRF_TTL_SECONDS = 10 * 60


@dataclass(frozen=True)
class CabinetSession:
    """Opaque server-side admin session."""

    session_id: str
    username: str
    csrf_token: str


class CabinetSecurityStore(Protocol):
    """Port хранения sessions и login rate-limit counters."""

    async def save_session(
        self,
        session: CabinetSession,
        *,
        ttl_seconds: int,
    ) -> None: ...

    async def get_session(self, session_id: str) -> CabinetSession | None: ...

    async def delete_session(self, session_id: str) -> None: ...

    async def get_login_failures(self, key: str) -> int: ...

    async def record_login_failure(
        self,
        key: str,
        *,
        window_seconds: int,
    ) -> int: ...

    async def clear_login_failures(self, key: str) -> None: ...


class CabinetAuthenticationError(Exception):
    """Базовая безопасная ошибка cabinet authentication."""


class CabinetInvalidCredentialsError(CabinetAuthenticationError):
    """Login credentials не прошли проверку."""


class CabinetLoginRateLimitError(CabinetAuthenticationError):
    """Client превысил допустимое число login attempts."""


class CabinetAuthService:
    """Оркестрировать password, signed cookies, CSRF и Redis sessions."""

    def __init__(self, settings: Settings, store: CabinetSecurityStore) -> None:
        if settings.cabinet_session_secret is None:
            raise ValueError("CABINET_SESSION_SECRET is required")
        self.settings = settings
        self.store = store
        self._session_signer = URLSafeTimedSerializer(
            settings.cabinet_session_secret,
            salt="m4-cabinet-session",
        )
        self._login_csrf_signer = URLSafeTimedSerializer(
            settings.cabinet_session_secret,
            salt="m4-cabinet-login-csrf",
        )

    async def authenticate(
        self,
        *,
        username: str,
        password: str,
        client_id: str,
    ) -> tuple[CabinetSession, str]:
        """Проверить credentials и создать новую server-side session."""

        rate_key = self._rate_key(client_id)
        attempts = await self.store.get_login_failures(rate_key)
        if attempts >= self.settings.cabinet_login_max_attempts:
            raise CabinetLoginRateLimitError

        configured_username = self.settings.cabinet_username or ""
        configured_hash = self.settings.cabinet_password_hash or ""
        username_valid = secrets.compare_digest(username, configured_username)
        password_valid = verify_password(password, configured_hash)
        if not (username_valid and password_valid):
            await self.store.record_login_failure(
                rate_key,
                window_seconds=self.settings.cabinet_login_window_seconds,
            )
            raise CabinetInvalidCredentialsError

        await self.store.clear_login_failures(rate_key)
        session = CabinetSession(
            session_id=secrets.token_urlsafe(32),
            username=configured_username,
            csrf_token=secrets.token_urlsafe(32),
        )
        await self.store.save_session(
            session,
            ttl_seconds=self.settings.cabinet_session_ttl_seconds,
        )
        return session, self._session_signer.dumps(session.session_id)

    async def resolve_session(self, signed_session_id: str | None) -> CabinetSession | None:
        """Проверить cookie signature/age и получить server-side session."""

        if not signed_session_id:
            return None
        try:
            session_id = self._session_signer.loads(
                signed_session_id,
                max_age=self.settings.cabinet_session_ttl_seconds,
            )
        except (BadSignature, SignatureExpired):
            return None
        if not isinstance(session_id, str):
            return None
        return await self.store.get_session(session_id)

    async def logout(self, signed_session_id: str | None) -> None:
        """Удалить server-side session для текущей cookie."""

        if not signed_session_id:
            return
        try:
            session_id = self._session_signer.loads(
                signed_session_id,
                max_age=self.settings.cabinet_session_ttl_seconds,
            )
        except (BadSignature, SignatureExpired):
            return
        if isinstance(session_id, str):
            await self.store.delete_session(session_id)

    def issue_login_csrf(self) -> tuple[str, str]:
        """Создать одноразовую пару form token и signed cookie."""

        token = secrets.token_urlsafe(32)
        return token, self._login_csrf_signer.dumps(token)

    def validate_login_csrf(self, token: str, signed_token: str | None) -> bool:
        """Проверить anonymous login CSRF token."""

        if not token or not signed_token:
            return False
        try:
            expected = self._login_csrf_signer.loads(
                signed_token,
                max_age=LOGIN_CSRF_TTL_SECONDS,
            )
        except (BadSignature, SignatureExpired):
            return False
        return isinstance(expected, str) and secrets.compare_digest(token, expected)

    @staticmethod
    def validate_session_csrf(session: CabinetSession, token: str) -> bool:
        """Проверить session-bound token изменяющей операции."""

        return bool(token) and secrets.compare_digest(token, session.csrf_token)

    @staticmethod
    def _rate_key(client_id: str) -> str:
        """Не хранить исходный IP в ключе rate limiter."""

        return hashlib.sha256(client_id.encode("utf-8")).hexdigest()
