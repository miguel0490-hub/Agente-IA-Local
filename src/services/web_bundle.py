"""Enlaza assets web (CSS/JS) con los nombres reales en disco."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from urllib.parse import urldefrag, urlsplit, urlunsplit

_ASSET_ATTR_RE = re.compile(
    r'(?i)\b(href|src)\s*=\s*(["\'])([^"\']+)\2'
)
_WEB_ASSET_SUFFIXES = (".html", ".htm", ".css", ".js", ".mjs")


def is_web_asset_filename(filename: str) -> bool:
    return (filename or "").lower().endswith(_WEB_ASSET_SUFFIXES)


def resolve_asset_ref(ref: str, directory: Path) -> str:
    """Mapea style.css → 834ee3cd_style.css si solo hay un candidato en el directorio."""
    if not ref or not directory.is_dir():
        return ref

    ref_no_frag, frag = urldefrag(ref)
    parts = urlsplit(ref_no_frag)
    if parts.scheme in ("http", "https", "file", "data") or parts.netloc:
        return ref
    if parts.path.startswith("/"):
        return ref

    base = PurePosixPath(parts.path).name
    if not base:
        return ref

    names = [p.name for p in directory.iterdir() if p.is_file()]
    if base in names:
        resolved = base
    else:
        prefixed = [n for n in names if n.endswith(f"_{base}")]
        if not prefixed:
            return ref
        if len(prefixed) > 1:
            prefixed.sort(
                key=lambda n: (directory / n).stat().st_mtime,
                reverse=True,
            )
        resolved = prefixed[0]

    new_path = parts.path
    if parts.path.endswith(base):
        new_path = parts.path[: -len(base)] + resolved
    else:
        new_path = resolved

    rebuilt = urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, ""))
    return rebuilt + (f"#{frag}" if frag else "")


def patch_html_content(content: str, directory: Path) -> str:
    def _replace(match: re.Match[str]) -> str:
        attr, quote, ref = match.group(1), match.group(2), match.group(3)
        return f"{attr}={quote}{resolve_asset_ref(ref, directory)}{quote}"

    return _ASSET_ATTR_RE.sub(_replace, content)


def order_tools_for_web_bundle(tools: list[dict]) -> list[dict]:
    """CSS/JS antes que HTML para que el parche de enlaces encuentre los assets."""
    def _sort_key(tool: dict) -> tuple[int, int, str]:
        if tool.get("action") != "create_file":
            return (0, 0, "")
        fn = (tool.get("filename") or "").lower()
        if fn.endswith(".css"):
            return (1, 0, fn)
        if fn.endswith((".js", ".mjs")):
            return (1, 1, fn)
        if fn.endswith((".html", ".htm")):
            return (1, 3, fn)
        return (1, 2, fn)

    return sorted(tools, key=_sort_key)


def find_broken_asset_refs(html_path: Path) -> list[str]:
    """Referencias href/src relativas sin fichero en el mismo directorio."""
    if not html_path.is_file():
        return []
    directory = html_path.parent
    broken: list[str] = []
    content = html_path.read_text(encoding="utf-8")
    for match in _ASSET_ATTR_RE.finditer(content):
        ref = match.group(3)
        resolved = resolve_asset_ref(ref, directory)
        target = directory / PurePosixPath(resolved).name
        if not target.is_file():
            broken.append(ref)
    return broken


def patch_html_asset_links(html_path: str | Path) -> bool:
    """Reescribe href/src en un HTML para apuntar a CSS/JS con prefijo UUID."""
    path = Path(html_path)
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    patched = patch_html_content(original, path.parent)
    if patched != original:
        path.write_text(patched, encoding="utf-8")
        return True
    return False
