"""
Pytest: garantiza variables de entorno mínimas antes de importar módulos que cargan `src.core.config`.

En CI no hay `.env`; sin `APP_SECRET_KEY`, `config.py` aborta al importarse.
La clave siguiente es solo para tests/CI (no usar en producción).
"""

from __future__ import annotations

import os

# Solo debe ser no vacío para `src.core.config`; no es el secreto de producción.
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

# Pytest importa todos los módulos de test antes de aplicar `-m "not e2e"`. Sin Playwright,
# `tests/e2e/` rompe la recolección en CI. Con Playwright instalado, los e2e se recogen
# y se filtran con el marker como de costumbre.
try:
    import playwright  # noqa: F401
except ImportError:
    collect_ignore = ["e2e"]
else:
    collect_ignore = []
