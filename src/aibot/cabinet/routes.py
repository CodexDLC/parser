"""Login/logout HTTP routes административного кабинета."""

from urllib.parse import parse_qs

from fastapi import APIRouter, Request, status
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from aibot.cabinet.auth import (
    LOGIN_CSRF_COOKIE_NAME,
    LOGIN_CSRF_TTL_SECONDS,
    SESSION_COOKIE_NAME,
    CabinetAuthenticationError,
    CabinetAuthService,
    CabinetInvalidCredentialsError,
    CabinetLoginRateLimitError,
    CabinetSession,
)
from aibot.cabinet.redis_store import CabinetSecurityStoreError
from aibot.config import Settings


def build_cabinet_auth_router(
    *,
    settings: Settings,
    auth_service: CabinetAuthService,
    templates: Jinja2Templates,
) -> APIRouter:
    """Собрать public login и protected logout routes."""

    mount_path = settings.cabinet_mount_path
    router = APIRouter(prefix=mount_path, include_in_schema=False)

    def login_response(
        request: Request,
        *,
        error: str | None = None,
        status_code: int = status.HTTP_200_OK,
        next_path: str | None = None,
    ) -> Response:
        token, signed_token = auth_service.issue_login_csrf()
        response = templates.TemplateResponse(
            request=request,
            name="cabinet/login.html",
            context={
                "brand_name": "M4 Управление",
                "mount_path": mount_path,
                "static_mount_path": f"{mount_path}/static",
                "csrf_token": token,
                "error": error,
                "next_path": _safe_next(next_path, mount_path),
            },
            status_code=status_code,
        )
        response.set_cookie(
            LOGIN_CSRF_COOKIE_NAME,
            signed_token,
            max_age=LOGIN_CSRF_TTL_SECONDS,
            httponly=True,
            secure=settings.cabinet_cookie_secure,
            samesite="lax",
            path=mount_path,
        )
        return response

    @router.get("/login")
    async def login_page(request: Request, next: str | None = None) -> Response:  # noqa: A002
        """Показать login form или вернуть уже авторизованного оператора."""

        if getattr(request.state, "cabinet_session", None) is not None:
            return RedirectResponse(mount_path, status_code=status.HTTP_303_SEE_OTHER)
        return login_response(request, next_path=next)

    @router.post("/login")
    async def login_action(request: Request) -> Response:
        """Проверить CSRF/credentials и установить новую opaque session cookie."""

        form = _parse_form(await request.body())
        csrf_token = form.get("csrf_token", "")
        next_path = form.get("next_path")
        if not auth_service.validate_login_csrf(
            csrf_token,
            request.cookies.get(LOGIN_CSRF_COOKIE_NAME),
        ):
            return login_response(
                request,
                error="Срок формы истёк. Обновите страницу.",
                status_code=status.HTTP_403_FORBIDDEN,
                next_path=next_path,
            )

        client_id = request.client.host if request.client is not None else "unknown"
        try:
            _, signed_session = await auth_service.authenticate(
                username=form.get("username", ""),
                password=form.get("password", ""),
                client_id=client_id,
            )
        except CabinetInvalidCredentialsError:
            return login_response(
                request,
                error="Неверный логин или пароль.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                next_path=next_path,
            )
        except CabinetLoginRateLimitError:
            return login_response(
                request,
                error="Слишком много попыток. Повторите позже.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                next_path=next_path,
            )
        except (CabinetAuthenticationError, CabinetSecurityStoreError):
            return login_response(
                request,
                error="Сервис входа временно недоступен.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                next_path=next_path,
            )

        response = RedirectResponse(
            _safe_next(next_path, mount_path),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.set_cookie(
            SESSION_COOKIE_NAME,
            signed_session,
            max_age=settings.cabinet_session_ttl_seconds,
            httponly=True,
            secure=settings.cabinet_cookie_secure,
            samesite="lax",
            path=mount_path,
        )
        response.delete_cookie(LOGIN_CSRF_COOKIE_NAME, path=mount_path)
        return response

    @router.post("/logout")
    async def logout_action(request: Request) -> Response:
        """Проверить CSRF, инвалидировать Redis session и удалить cookie."""

        session = getattr(request.state, "cabinet_session", None)
        if not isinstance(session, CabinetSession):
            return Response(status_code=status.HTTP_401_UNAUTHORIZED)
        form = _parse_form(await request.body())
        if not auth_service.validate_session_csrf(session, form.get("csrf_token", "")):
            return Response(status_code=status.HTTP_403_FORBIDDEN)
        try:
            await auth_service.logout(request.cookies.get(SESSION_COOKIE_NAME))
        except CabinetSecurityStoreError:
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = RedirectResponse(
            f"{mount_path}/login",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie(SESSION_COOKIE_NAME, path=mount_path)
        return response

    return router


def _parse_form(body: bytes) -> dict[str, str]:
    """Разобрать application/x-www-form-urlencoded без multipart side effects."""

    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


def _safe_next(value: str | None, mount_path: str) -> str:
    """Запретить open redirect за пределы cabinet mount."""

    if not value or not value.startswith(f"{mount_path}/") or value.startswith("//"):
        return mount_path
    return value
