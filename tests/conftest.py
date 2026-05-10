"""
Pytest: garantiza variables de entorno mínimas antes de importar módulos que cargan `src.core.config`.

En CI no hay `.env`; sin `APP_SECRET_KEY`, `config.py` aborta al importarse.
La clave siguiente es solo para tests/CI (no usar en producción).
"""

from __future__ import annotations

import os

# Solo debe ser no vacío para `src.core.config`; no es el secreto de producción.
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")
