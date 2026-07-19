"""Append-only журнал административных мутаций."""

import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from aibot.db.base import Base
from aibot.models.enums import AdminAuditOutcome
from aibot.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AdminAuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Безопасная запись действия оператора без credentials/payload."""

    __tablename__ = "admin_audit_logs"

    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    outcome: Mapped[AdminAuditOutcome] = mapped_column(
        Enum(AdminAuditOutcome, name="admin_audit_outcome", native_enum=False),
        nullable=False,
        index=True,
    )
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
