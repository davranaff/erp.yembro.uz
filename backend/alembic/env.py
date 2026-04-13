from __future__ import annotations

import asyncio
import os.path
import os
from urllib.parse import urlparse, urlunparse

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    import logging.config
    logging.config.fileConfig(config.config_file_name)


def _normalize_alembic_db_url(raw_url: str) -> str:
    if not raw_url:
        return raw_url

    parsed = urlparse(raw_url)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg"}:
        return raw_url

    if os.path.exists("/.dockerenv"):
        return raw_url

    host = parsed.hostname
    if host not in {"postgres", "localhost", "127.0.0.1", "::1"}:
        return raw_url

    effective_port = parsed.port
    if host == "postgres":
        effective_port = int(os.environ.get("POSTGRES_PUBLISHED_PORT", "30001"))
        host = "localhost"
    elif effective_port == 30010:
        effective_port = int(os.environ.get("POSTGRES_PUBLISHED_PORT", "30001"))
    else:
        host = "localhost"
    netloc = host
    username = parsed.username or ""
    password = parsed.password
    userinfo = username if password is None else f"{username}:{password}"
    if userinfo:
        netloc = f"{userinfo}@{host}:{effective_port}"
    else:
        netloc = f"{host}:{effective_port}"

    normalized = parsed._replace(
        scheme="postgresql+asyncpg",
        netloc=netloc,
        path=parsed.path,
    )
    return urlunparse(normalized)

settings = get_settings()
db_url = settings.sqlalchemy_database_url
if os.getenv("DATABASE_URL"):
    env_db_url = os.getenv("DATABASE_URL", "")
    if env_db_url.startswith("postgresql://"):
        db_url = env_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        db_url = env_db_url

db_url = _normalize_alembic_db_url(db_url)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def do_run() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(do_run())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
