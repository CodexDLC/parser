"""Permission adapter для defence-in-depth внутри cabinet library."""

from fastapi import Request


class CabinetPermissionProvider:
    """Разрешать declared permissions только авторизованной admin session."""

    async def can(self, request: Request, permission: str) -> bool:
        """Проверить session независимо от конкретного permission этапа 1."""

        return (
            permission.startswith("cabinet.")
            and getattr(request.state, "cabinet_session", None) is not None
        )
