"""
Genera estado_actual_proyecto.md (volcado para auditoría). Uso: python scripts/_build_estado_actual.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "estado_actual_proyecto.md"
EXCLUDE_DIR_NAMES = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "logs",
    "generated_images",
    ".pytest_cache",
    "htmlcov",
    ".mypy_cache",
    "node_modules",
    ".ruff_cache",
}


def build_tree_display() -> str:
    """Árbol tipo Unix desde ROOT; omite directorios en EXCLUDE_DIR_NAMES."""

    def walk_sub(p: Path, prefix: str) -> list[str]:
        acc: list[str] = []
        try:
            children = sorted(
                [x for x in p.iterdir() if x.name not in EXCLUDE_DIR_NAMES],
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
        except OSError:
            return acc
        for i, c in enumerate(children):
            last = i == len(children) - 1
            br = "└── " if last else "├── "
            acc.append(f"{prefix}{br}{c.name}")
            ext = "    " if last else "│   "
            if c.is_dir():
                acc.extend(walk_sub(c, prefix + ext))
        return acc

    lines: list[str] = ["./"]
    try:
        children = sorted(
            [p for p in ROOT.iterdir() if p.name not in EXCLUDE_DIR_NAMES],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
    except OSError:
        return "\n".join(lines)

    for i, c in enumerate(children):
        last = i == len(children) - 1
        br = "└── " if last else "├── "
        lines.append(f"{br}{c.name}")
        ext = "    " if last else "│   "
        if c.is_dir():
            lines.extend(walk_sub(c, ext))
    return "\n".join(lines)


def main() -> None:
    tree_str = build_tree_display()

    parts: list[str] = [
        "# Estado actual del proyecto — volcado para auditoría externa\n",
        "\n",
        "_Generado automáticamente. Orden: (1) árbol, (2) `app.py`, (3) todos los `.py` bajo `src/`, (4) `requirements.txt`._\n",
        "\n",
        "## 1. Árbol de directorios\n",
        "\n",
        "Directorios excluidos: `venv/`, `.git/`, `__pycache__/`, `logs/`, `generated_images/`, `.pytest_cache/`, `htmlcov/`, `.mypy_cache/`, `node_modules/`, `.ruff_cache/`.\n",
        "\n",
        "```text\n",
        tree_str,
        "\n```\n\n",
        "## app.py\n",
        "\n",
        "```python\n",
        (ROOT / "app.py").read_text(encoding="utf-8"),
        "```\n\n",
    ]

    src_root = ROOT / "src"
    py_files = sorted(src_root.rglob("*.py"), key=lambda p: str(p).replace("\\", "/").lower())

    for fp in py_files:
        rel = fp.relative_to(ROOT).as_posix()
        parts.append(f"## {rel}\n\n")
        parts.append("```python\n")
        parts.append(fp.read_text(encoding="utf-8"))
        parts.append("```\n\n")

    req_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    if not req_text.endswith("\n"):
        req_text += "\n"
    parts.extend(
        [
            "## requirements.txt\n",
            "\n",
            "```text\n",
            req_text,
            "```\n",
        ]
    )

    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"Escrito {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
