"""Configurazione pytest: i test girano SEMPRE su un database separato.

``DATABASE_URL`` viene riscritto (prima di importare ``app``) verso
``<nome_db>_test`` sullo stesso server Postgres. Il DB viene creato se manca,
migrato con Alembic e seedato una volta per sessione. I test di integrazione
fanno TRUNCATE: senza questa separazione cancellerebbero i dati reali dell'utente.
"""
import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

_default_url = "postgresql+asyncpg://deutsch:deutsch@localhost:5433/deutsch_tutor"
_live_url = make_url(os.environ.get("DATABASE_URL", _default_url))
if not _live_url.database.endswith("_test"):
    TEST_URL = _live_url.set(database=f"{_live_url.database}_test")
else:
    TEST_URL = _live_url
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)

# Solo ora è sicuro importare l'app: ``settings`` legge DATABASE_URL all'import.
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.config import settings  # noqa: E402
from app.seed import run_seed  # noqa: E402

assert settings.database_url.endswith("_test"), settings.database_url


def _create_test_db_if_missing() -> None:
    async def _run() -> None:
        admin = TEST_URL.set(database="postgres", drivername="postgresql")
        conn = await asyncpg.connect(admin.render_as_string(hide_password=False))
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_URL.database)
            if not exists:
                await conn.execute(f'CREATE DATABASE "{TEST_URL.database}"')
        finally:
            await conn.close()

    asyncio.run(_run())


def _migrate() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


def pytest_sessionstart(session: pytest.Session) -> None:
    _create_test_db_if_missing()
    _migrate()
    asyncio.run(run_seed())
