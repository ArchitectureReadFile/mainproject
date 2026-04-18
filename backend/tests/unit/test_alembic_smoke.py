from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_alembic_upgrade_head_creates_current_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_smoke.db"
    database_url = f"sqlite:///{db_path}"
    backend_dir = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "users",
        "groups",
        "documents",
        "chat_sessions",
        "chat_session_references",
        "chat_session_reference_chunks",
        "platform_documents",
        "platform_document_chunks",
        "export_jobs",
        "platform_sync_runs",
    }.issubset(table_names)

    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == "20260418_0001"
