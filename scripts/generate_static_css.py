"""Genera .streamlit/static/superagente.css desde src.ui.theme (ejecutar tras cambiar theme.py)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from src.ui.theme import ESTILOS_CSS

    body = ESTILOS_CSS.strip()
    body = re.sub(r"^<style>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\s*</style>\s*$", "", body, flags=re.IGNORECASE)
    out = ROOT / ".streamlit" / "static" / "superagente.css"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body.strip() + "\n", encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
