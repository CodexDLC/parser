"""Статические контракты Alembic как production-источника схемы."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_configuration_and_revision_chain_exist() -> None:
    """Проект содержит initial schema и cabinet operations revision."""

    assert (PROJECT_ROOT / "alembic.ini").is_file()
    assert (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "env.py").is_file()
    assert (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "script.py.mako").is_file()

    revisions = list(
        (PROJECT_ROOT / "src" / "aibot" / "db" / "migrations" / "versions").glob("*.py")
    )
    assert len(revisions) == 2
    revision_texts = [path.read_text(encoding="utf-8") for path in revisions]
    assert any('down_revision: str | None = None' in text for text in revision_texts)
    assert any(
        'down_revision: str | None = "20260719_0001"' in text
        for text in revision_texts
    )
    assert all("def upgrade() -> None:" in text for text in revision_texts)
    assert all("def downgrade() -> None:" in text for text in revision_texts)


def test_production_init_db_uses_alembic_instead_of_create_all() -> None:
    """Production bootstrap не обходит versioned migrations."""

    init_source = (
        PROJECT_ROOT / "src" / "aibot" / "db" / "init_db.py"
    ).read_text(encoding="utf-8")

    assert "command.upgrade" in init_source
    assert "Base.metadata.create_all" not in init_source
