"""Статические контракты Alembic как production-источника схемы."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_configuration_and_initial_revision_exist() -> None:
    """Проект содержит рабочий Alembic environment и ровно одну initial revision."""

    assert (PROJECT_ROOT / "alembic.ini").is_file()
    assert (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "env.py").is_file()
    assert (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "script.py.mako").is_file()

    revisions = list(
        (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "versions").glob("*.py")
    )
    assert len(revisions) == 1
    revision_text = revisions[0].read_text(encoding="utf-8")
    assert 'down_revision: str | None = None' in revision_text
    assert "def upgrade() -> None:" in revision_text
    assert "def downgrade() -> None:" in revision_text


def test_production_init_db_uses_alembic_instead_of_create_all() -> None:
    """Production bootstrap не обходит versioned migrations."""

    init_source = (
        PROJECT_ROOT / "src" / "aibot" / "db" / "init_db.py"
    ).read_text(encoding="utf-8")

    assert "command.upgrade" in init_source
    assert "Base.metadata.create_all" not in init_source
