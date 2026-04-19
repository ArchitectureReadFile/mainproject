from __future__ import annotations

import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, inspect, pool, text

from alembic import context

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

config = context.config
logger = logging.getLogger("alembic.env")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_target_metadata():
    import models  # noqa: F401
    from database import Base

    return Base.metadata


target_metadata = get_target_metadata()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "DATABASE_URL이 설정되지 않았습니다. Alembic 실행 전 DATABASE_URL을 설정하세요."
        )
    return url


def _target_table_names() -> set[str]:
    return {table.name for table in target_metadata.sorted_tables}


def _is_pre_alembic_database(connection) -> bool:
    existing_tables = set(inspect(connection).get_table_names())
    has_version_table = "alembic_version" in existing_tables
    if has_version_table:
        current_revision = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar_one_or_none()
        if current_revision:
            return False

    target_tables = _target_table_names()
    existing_app_tables = target_tables.intersection(existing_tables)
    if not existing_app_tables:
        return False

    logger.info(
        "Detected existing application tables without alembic_version: %s",
        ", ".join(sorted(existing_app_tables)),
    )
    return True


def _stamp_existing_schema(connection) -> None:
    head_revision = ScriptDirectory.from_config(config).get_current_head()
    if not head_revision:
        raise RuntimeError("Alembic head revision을 찾을 수 없습니다.")

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
            """
        )
    )
    connection.execute(text("DELETE FROM alembic_version"))
    connection.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
        {"version_num": head_revision},
    )
    connection.commit()


def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url().replace("%", "%%")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if _is_pre_alembic_database(connection):
            logger.info("Detected pre-Alembic schema. Stamping current schema to head.")
            _stamp_existing_schema(connection)
            return

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
