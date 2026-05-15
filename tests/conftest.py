"""
Pytest: garantiza variables de entorno mínimas antes de importar módulos que cargan `src.core.config`.

En CI no hay `.env`; sin `APP_SECRET_KEY`, `config.py` aborta al importarse.
La clave siguiente es solo para tests/CI (no usar en producción).
"""

from __future__ import annotations

import os

# Solo debe ser no vacío para `src.core.config`; no es el secreto de producción.
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

# Tests unitarios/integración ligeros: SQLite en archivo salvo que se fuerce Postgres.
# No usar :memory: aquí: SQLAlchemy abriría una BD vacía distinta por conexión y el gateway fallaría.
if os.getenv("PYTEST_USE_PG_DATABASE") != "1":
    os.environ["DATABASE_URL"] = "sqlite:///data/pytest_automation.db"

# Backoff/rate-limit de login en memoria en tests salvo que el job pida Redis obligatorio.
os.environ.setdefault("LOGIN_REQUIRE_REDIS", "0")

# Pytest importa todos los módulos de test antes de aplicar `-m "not e2e"`. Sin Playwright,
# `tests/e2e/` rompe la recolección en CI. Con Playwright instalado, los e2e se recogen
# y se filtran con el marker como de costumbre.
try:
    import playwright  # noqa: F401
except ImportError:
    collect_ignore = ["e2e"]
else:
    collect_ignore = []


def pytest_sessionstart(session):
    if os.getenv("PYTEST_USE_PG_DATABASE") == "1":
        return
    os.makedirs("data", exist_ok=True)
    from src.database.database import init_db

    init_db()


def pytest_sessionfinish(session, exitstatus):
    if os.getenv("PYTEST_USE_PG_DATABASE") == "1":
        return
    try:
        from src.database.database import engine

        engine.dispose()
    except Exception:
        pass
