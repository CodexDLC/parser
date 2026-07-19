"""HTTP security boundary вокруг всего cabinet mount."""

from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, quote

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.types import ASGIApp

from aibot.cabinet.auth import SESSION_COOKIE_NAME, CabinetAuthService
from aibot.cabinet.redis_store import CabinetSecurityStoreError

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class CabinetSecurityMiddleware(BaseHTTPMiddleware):
    """Закрыть private routes до provider/action dispatch."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        auth_service: CabinetAuthService,
        mount_path: str,
    ) -> None:
        super().__init__(app)
        self.auth_service = auth_service
        self.mount_path = mount_path.rstrip("/")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Разрешить public routes и потребовать session для остальных."""

        path = request.url.path
        if not self._is_cabinet_path(path):
            return await call_next(request)

        try:
            session = await self.auth_service.resolve_session(
                request.cookies.get(SESSION_COOKIE_NAME)
            )
        except CabinetSecurityStoreError:
            return self._secure(
                PlainTextResponse(
                    "Cabinet security store is unavailable",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            )

        request.state.cabinet_session = session
        request.state.csrf_token = session.csrf_token if session is not None else ""

        if not self._is_public_path(path) and session is None:
            target = quote(path, safe="/")
            redirect_response = RedirectResponse(
                url=f"{self.mount_path}/login?next={target}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
            return self._secure(redirect_response)

        if (
            not self._is_public_path(path)
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and session is not None
        ):
            body = await request.body()
            form = parse_qs(body.decode("utf-8", errors="replace"))
            token = form.get("csrf_token", [""])[0]
            if not self.auth_service.validate_session_csrf(session, token):
                return self._secure(
                    PlainTextResponse(
                        "Invalid CSRF token",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )
                )

        response = await call_next(request)
        return self._secure(response)

    def _is_cabinet_path(self, path: str) -> bool:
        return path == self.mount_path or path.startswith(f"{self.mount_path}/")

    def _is_public_path(self, path: str) -> bool:
        return path == f"{self.mount_path}/login" or path.startswith(
            f"{self.mount_path}/static/"
        )

    @staticmethod
    def _secure(response: Response) -> Response:
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        return response
