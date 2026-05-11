"""Path traversal protection for file creation and uploads.

Ensures that all generated/uploaded filenames stay within allowed directories
and cannot escape via ../, symlinks, or special characters.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote

from src.core.logger import get_logger

logger = get_logger(__name__)

_DANGEROUS_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


def safe_filename(
    raw_name: str,
    output_dir: str | Path,
    *,
    prefix_uuid: bool = False,
) -> Path:
    """Returns a safe absolute path guaranteed to be inside output_dir.

    Args:
        raw_name: The untrusted filename (may contain path separators, .., etc.).
        output_dir: The directory the file must reside in.
        prefix_uuid: If True, prepend a short UUID to prevent collisions.

    Returns:
        Resolved absolute Path inside output_dir.

    Raises:
        ValueError: If the filename is empty or cannot be made safe.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not raw_name or not isinstance(raw_name, str):
        raw_name = f"file_{uuid.uuid4().hex[:8]}.bin"

    raw_name = unquote(unquote(raw_name))
    raw_name = raw_name.replace("\x00", "")

    for parser in (PurePosixPath, PureWindowsPath):
        raw_name = parser(raw_name).name

    raw_name = _DANGEROUS_CHARS.sub("_", raw_name)
    raw_name = raw_name.lstrip(".")

    stem = Path(raw_name).stem
    suffix = Path(raw_name).suffix

    if stem.upper() in _RESERVED_NAMES:
        stem = f"_{stem}"

    if not stem:
        stem = f"file_{uuid.uuid4().hex[:8]}"
    if not suffix:
        suffix = ".bin"

    if prefix_uuid:
        stem = f"{uuid.uuid4().hex[:8]}_{stem}"

    clean_name = f"{stem}{suffix}"
    candidate = (output_dir / clean_name).resolve()

    if not str(candidate).startswith(str(output_dir)):
        logger.warning("Path traversal blocked: %s -> %s", raw_name, candidate)
        raise ValueError(f"Nombre de archivo rechazado: intento de path traversal.")

    return candidate


def safe_join(directory: str | Path, filename: str) -> Path:
    """Safe os.path.join replacement that prevents directory escape."""
    base = Path(directory).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"Path traversal detectado: '{filename}' escapa de '{base}'.")
    return target
