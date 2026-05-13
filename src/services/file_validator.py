"""File validation and anti-bomb checks for uploads."""

from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".ico"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
DOC_EXTS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".txt",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".xml",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
    ".epub",
    ".log",
    ".ini",
    ".toml",
    ".conf",
    ".cfg",
    ".sqlite",
    ".db",
    ".parquet",
    ".feather",
    ".tsv",
    ".heic",
    ".heif",
}
BLOCKED_EXTS = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".js", ".jar", ".msi", ".scr", ".com"}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except Exception:
        return default


MAX_IMAGE_BYTES = _env_int("MAX_IMAGE_MB", 15) * 1024 * 1024
MAX_VIDEO_BYTES = _env_int("MAX_VIDEO_MB", 100) * 1024 * 1024
MAX_AUDIO_BYTES = _env_int("MAX_AUDIO_MB", 100) * 1024 * 1024
MAX_DOC_BYTES = _env_int("MAX_DOC_MB", 25) * 1024 * 1024


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome."""

    ok: bool
    reason: str = ""


def get_upload_policy() -> str:
    """Returns active upload policy: strict (default in production) or permissive."""
    policy = (os.getenv("UPLOAD_POLICY") or "").strip().lower()
    if policy in {"strict", "permissive"}:
        return policy
    env = (os.getenv("ENVIRONMENT") or "production").strip().lower()
    return "strict" if env in {"prod", "production"} else "permissive"


def get_upload_policy_summary() -> str:
    """Human-readable policy summary for UI captions."""
    from src.core.i18n import t

    if get_upload_policy() == "permissive":
        return t("upload_policy_permissive")
    max_doc_mb = MAX_DOC_BYTES // (1024 * 1024)
    max_img_mb = MAX_IMAGE_BYTES // (1024 * 1024)
    max_video_mb = MAX_VIDEO_BYTES // (1024 * 1024)
    max_audio_mb = MAX_AUDIO_BYTES // (1024 * 1024)
    return t(
        "upload_policy_strict",
        doc_mb=max_doc_mb,
        img_mb=max_img_mb,
        video_mb=max_video_mb,
        audio_mb=max_audio_mb,
    )


def _guess_group(ext: str) -> str:
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "document"


def _max_size_for_group(group: str) -> int:
    if group == "image":
        return MAX_IMAGE_BYTES
    if group == "video":
        return MAX_VIDEO_BYTES
    if group == "audio":
        return MAX_AUDIO_BYTES
    return MAX_DOC_BYTES


def _check_zip_bomb(raw: bytes) -> ValidationResult:
    from src.core.i18n import t

    if not raw.startswith(b"PK"):
        return ValidationResult(ok=True)
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        total_uncompressed = sum(i.file_size for i in zf.infolist())
        total_compressed = sum(i.compress_size for i in zf.infolist()) or 1
        ratio = total_uncompressed / total_compressed
        if total_uncompressed > 250 * 1024 * 1024 or ratio > 100:
            return ValidationResult(ok=False, reason=t("upload_err_zip_bomb"))
        return ValidationResult(ok=True)
    except zipfile.BadZipFile:
        return ValidationResult(ok=False, reason=t("upload_err_zip_corrupt"))


def _detect_magic_type(raw: bytes) -> str:
    """Best-effort binary signature detection."""
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw.startswith(b"PK"):
        return "application/zip"
    if len(raw) > 12 and raw[4:8] == b"ftyp":
        return "video/mp4"
    if raw.startswith(b"ID3"):
        return "audio/mpeg"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WAVE":
        return "audio/wav"
    return "application/octet-stream"


def _matches_expected_type(ext: str, detected: str) -> bool:
    if ext in {".png"}:
        return detected == "image/png"
    if ext in {".jpg", ".jpeg"}:
        return detected == "image/jpeg"
    if ext in {".gif"}:
        return detected == "image/gif"
    if ext in {".pdf"}:
        return detected == "application/pdf"
    if ext in {".zip"}:
        return detected == "application/zip"
    if ext in {".mp4", ".m4v"}:
        return detected == "video/mp4"
    if ext in {".mp3"}:
        return detected == "audio/mpeg"
    if ext in {".wav"}:
        return detected == "audio/wav"
    # Formats without robust signature fallback to extension allowlist + size constraints.
    return True


def validate_uploaded_file(filename: str, raw_bytes: bytes) -> ValidationResult:
    """Validates extension, size and payload security according to active policy."""
    from src.core.i18n import t

    if not filename or raw_bytes is None:
        return ValidationResult(ok=False, reason=t("upload_err_invalid_file"))
    ext = Path(filename).suffix.lower()
    if ext in BLOCKED_EXTS:
        return ValidationResult(ok=False, reason=t("upload_err_ext_blocked", ext=ext))
    policy = get_upload_policy()
    allowed_exts = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS | DOC_EXTS

    if policy == "strict":
        if ext not in allowed_exts:
            return ValidationResult(ok=False, reason=t("upload_err_ext_not_allowed", ext=ext))
        group = _guess_group(ext)
        max_size = _max_size_for_group(group)
        if len(raw_bytes) > max_size:
            max_mb = max_size // (1024 * 1024)
            return ValidationResult(ok=False, reason=t("upload_err_size", group=group, max_mb=max_mb))

    detected = _detect_magic_type(raw_bytes)
    if not _matches_expected_type(ext, detected):
        return ValidationResult(ok=False, reason=t("upload_err_mime_mismatch"))

    bomb_check = _check_zip_bomb(raw_bytes)
    if not bomb_check.ok:
        return bomb_check
    return ValidationResult(ok=True)
