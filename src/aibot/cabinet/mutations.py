"""Application port и production service административных CRUD-мутаций."""

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aibot.models.enums import AdminAuditOutcome, SourceType
from aibot.repositories.admin_audit_log_repository import AdminAuditLogRepository
from aibot.repositories.keyword_repository import KeywordRepository
from aibot.repositories.source_repository import SourceRepository
from aibot.services.admin_audit import AdminAuditService
from aibot.services.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
)
from aibot.services.keyword_service import KeywordService
from aibot.services.source_service import SourceService


class ConcurrentEntityUpdateError(RuntimeError):
    """Форма построена по устаревшей версии сущности."""


class CabinetMutationPort(Protocol):
    async def create_source(
        self,
        *,
        actor: str,
        source_type: str,
        name: str,
        url: str,
        enabled: bool,
    ) -> uuid.UUID: ...

    async def update_source(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        expected_updated_at: datetime,
        source_type: str,
        name: str,
        url: str,
        enabled: bool,
    ) -> uuid.UUID: ...

    async def toggle_source(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> uuid.UUID: ...

    async def create_keyword(
        self,
        *,
        actor: str,
        word: str,
        enabled: bool,
    ) -> uuid.UUID: ...

    async def update_keyword(
        self,
        *,
        actor: str,
        keyword_id: uuid.UUID,
        expected_updated_at: datetime,
        word: str,
        enabled: bool,
    ) -> uuid.UUID: ...

    async def toggle_keyword(
        self,
        *,
        actor: str,
        keyword_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> uuid.UUID: ...


class CabinetMutationService:
    """Переиспользовать domain services и дополнять их lock/version/audit."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_source(
        self,
        *,
        actor: str,
        source_type: str,
        name: str,
        url: str,
        enabled: bool,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            try:
                entity = await SourceService(session).create_source(
                    source_type=SourceType(source_type),
                    name=name,
                    url=url,
                    enabled=enabled,
                )
            except (EntityAlreadyExistsError, ValueError):
                await self._audit(
                    session,
                    actor=actor,
                    action="source.create",
                    entity_type="source",
                    entity_id=None,
                    outcome=AdminAuditOutcome.REJECTED,
                    detail="validation_or_duplicate",
                )
                raise
            await self._audit(
                session,
                actor=actor,
                action="source.create",
                entity_type="source",
                entity_id=entity.id,
                outcome=AdminAuditOutcome.SUCCEEDED,
            )
            return entity.id

    async def update_source(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        expected_updated_at: datetime,
        source_type: str,
        name: str,
        url: str,
        enabled: bool,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            repository = SourceRepository(session)
            source = await repository.get_for_update(source_id)
            await self._ensure_current(
                source,
                expected_updated_at,
                session=session,
                actor=actor,
                action="source.update",
                entity_type="source",
                entity_id=source_id,
            )
            try:
                entity = await SourceService(session).update_source(
                    source_id,
                    source_type=SourceType(source_type),
                    name=name,
                    url=url,
                    enabled=enabled,
                )
            except (EntityAlreadyExistsError, ValueError):
                await self._audit(
                    session,
                    actor=actor,
                    action="source.update",
                    entity_type="source",
                    entity_id=source_id,
                    outcome=AdminAuditOutcome.REJECTED,
                    detail="validation_or_duplicate",
                )
                raise
            await self._audit_success(session, actor, "source.update", "source", entity.id)
            return entity.id

    async def toggle_source(
        self,
        *,
        actor: str,
        source_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            source = await SourceRepository(session).get_for_update(source_id)
            await self._ensure_current(
                source,
                expected_updated_at,
                session=session,
                actor=actor,
                action="source.toggle",
                entity_type="source",
                entity_id=source_id,
            )
            assert source is not None
            entity = await SourceService(session).update_source(
                source_id,
                enabled=not source.enabled,
            )
            await self._audit_success(session, actor, "source.toggle", "source", entity.id)
            return entity.id

    async def create_keyword(
        self,
        *,
        actor: str,
        word: str,
        enabled: bool,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            try:
                entity = await KeywordService(session).create_keyword(
                    word=word,
                    enabled=enabled,
                )
            except EntityAlreadyExistsError:
                await self._audit(
                    session,
                    actor=actor,
                    action="keyword.create",
                    entity_type="keyword",
                    entity_id=None,
                    outcome=AdminAuditOutcome.REJECTED,
                    detail="duplicate",
                )
                raise
            await self._audit_success(session, actor, "keyword.create", "keyword", entity.id)
            return entity.id

    async def update_keyword(
        self,
        *,
        actor: str,
        keyword_id: uuid.UUID,
        expected_updated_at: datetime,
        word: str,
        enabled: bool,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            keyword = await KeywordRepository(session).get_for_update(keyword_id)
            await self._ensure_current(
                keyword,
                expected_updated_at,
                session=session,
                actor=actor,
                action="keyword.update",
                entity_type="keyword",
                entity_id=keyword_id,
            )
            try:
                entity = await KeywordService(session).update_keyword(
                    keyword_id,
                    word=word,
                    enabled=enabled,
                )
            except EntityAlreadyExistsError:
                await self._audit(
                    session,
                    actor=actor,
                    action="keyword.update",
                    entity_type="keyword",
                    entity_id=keyword_id,
                    outcome=AdminAuditOutcome.REJECTED,
                    detail="duplicate",
                )
                raise
            await self._audit_success(session, actor, "keyword.update", "keyword", entity.id)
            return entity.id

    async def toggle_keyword(
        self,
        *,
        actor: str,
        keyword_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> uuid.UUID:
        async with self._session_factory() as session:
            keyword = await KeywordRepository(session).get_for_update(keyword_id)
            await self._ensure_current(
                keyword,
                expected_updated_at,
                session=session,
                actor=actor,
                action="keyword.toggle",
                entity_type="keyword",
                entity_id=keyword_id,
            )
            assert keyword is not None
            entity = await KeywordService(session).update_keyword(
                keyword_id,
                enabled=not keyword.enabled,
            )
            await self._audit_success(session, actor, "keyword.toggle", "keyword", entity.id)
            return entity.id

    async def _ensure_current(
        self,
        entity: object | None,
        expected_updated_at: datetime,
        *,
        session: AsyncSession,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        if entity is None:
            await self._audit(
                session,
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                outcome=AdminAuditOutcome.REJECTED,
                detail="not_found",
            )
            raise EntityNotFoundError(f"{entity_type} not found")
        actual_updated_at = getattr(entity, "updated_at", None)
        if actual_updated_at != expected_updated_at:
            await self._audit(
                session,
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                outcome=AdminAuditOutcome.REJECTED,
                detail="stale_version",
            )
            raise ConcurrentEntityUpdateError("Entity was changed by another request")

    async def _audit_success(
        self,
        session: AsyncSession,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        await self._audit(
            session,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=AdminAuditOutcome.SUCCEEDED,
        )

    @staticmethod
    async def _audit(
        session: AsyncSession,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        outcome: AdminAuditOutcome,
        detail: str | None = None,
    ) -> None:
        await AdminAuditService(AdminAuditLogRepository(session)).record(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=outcome,
            detail=detail,
        )
