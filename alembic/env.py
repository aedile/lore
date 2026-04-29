"""Alembic migration environment for lore-eligibility.

Supports both offline (SQL generation) and online (live database) migration
modes. Target metadata is sourced from SQLModel's metadata registry so that
all table classes are automatically included for autogeneration when any
module imports this environment.

DUAL-DRIVER NOTE:
Alembic migrations run synchronously using the psycopg2 driver
(``postgresql+psycopg2://``). The application runtime uses asyncpg
(``postgresql+asyncpg://``). This separation keeps migrations simple and
compatible with standard Alembic tooling while keeping runtime I/O async.

CONSTITUTION Priority 0: Security — credentials sourced from env at runtime.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# ---------------------------------------------------------------------------
# Alembic configuration object — provides access to values in alembic.ini
# ---------------------------------------------------------------------------

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# DATABASE_URL injection
#
# Read DATABASE_URL from the environment and inject it into the alembic
# configuration so that ``%(DATABASE_URL)s`` in alembic.ini resolves to the
# current runtime value.
# ---------------------------------------------------------------------------

_database_url = os.environ.get("DATABASE_URL", "")
if _database_url:
    # Translate asyncpg DSN to psycopg2 for Alembic if needed.
    if _database_url.startswith("postgresql+asyncpg://"):
        _database_url = _database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    config.set_main_option("DATABASE_URL", _database_url)

# ---------------------------------------------------------------------------
# Target metadata for autogenerate support.
#
# SQLModel.metadata aggregates the metadata from all SQLModel table classes
# that have been imported into this process. Table classes will be imported
# here as they are defined — until then the metadata is empty.
# ---------------------------------------------------------------------------

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (writes SQL to stdout, no DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
