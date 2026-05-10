"""Upload security orchestration (validator + optional antivirus quarantine)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.services.file_validator import ValidationResult, validate_uploaded_file


QUARANTINE_DIR = Path("data/quarantine")
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)


def _scan_with_clamav(raw: bytes, filename: str) -> ValidationResult:
    """Optional ClamAV scanning if CLAMSCAN_BIN is configured."""
    clamscan_bin = os.getenv("CLAMSCAN_BIN")
    if not clamscan_bin:
        return ValidationResult(ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)

    try:
        import subprocess

        proc = subprocess.run(
            [clamscan_bin, "--no-summary", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if proc.returncode == 0:
            return ValidationResult(ok=True)
        if proc.returncode == 1:
            qpath = QUARANTINE_DIR / f"infected_{tmp_path.name}"
            tmp_path.replace(qpath)
            return ValidationResult(ok=False, reason="Archivo bloqueado por antivirus.")
        return ValidationResult(ok=False, reason="Fallo en escaneo antivirus.")
    except Exception:
        return ValidationResult(ok=False, reason="Error al ejecutar antivirus.")
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def secure_upload_check(filename: str, raw_bytes: bytes) -> ValidationResult:
    """Runs all upload security controls."""
    validation = validate_uploaded_file(filename, raw_bytes)
    if not validation.ok:
        return validation
    av = _scan_with_clamav(raw_bytes, filename)
    return av
