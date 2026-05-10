from src.services.upload_security import ValidationResult, secure_upload_check
from src.services import upload_security


def test_secure_upload_returns_validator_failure(monkeypatch):
    monkeypatch.setattr(
        upload_security,
        "validate_uploaded_file",
        lambda filename, raw: ValidationResult(ok=False, reason="blocked"),
    )
    res = secure_upload_check("a.txt", b"abc")
    assert res.ok is False
    assert res.reason == "blocked"


def test_secure_upload_runs_antivirus_after_validator(monkeypatch):
    monkeypatch.setattr(
        upload_security,
        "validate_uploaded_file",
        lambda filename, raw: ValidationResult(ok=True),
    )
    monkeypatch.setattr(
        upload_security,
        "_scan_with_clamav",
        lambda raw, filename: ValidationResult(ok=False, reason="av"),
    )
    res = secure_upload_check("a.txt", b"abc")
    assert res.ok is False
    assert res.reason == "av"


def test_scan_with_clamav_disabled_when_bin_missing(monkeypatch):
    monkeypatch.setenv("CLAMSCAN_BIN", "")
    res = upload_security._scan_with_clamav(b"abc", "a.txt")
    assert res.ok is True


def test_scan_with_clamav_detects_infected(monkeypatch):
    class Proc:
        returncode = 1

    monkeypatch.setenv("CLAMSCAN_BIN", "clamscan")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: Proc())
    res = upload_security._scan_with_clamav(b"abc", "a.txt")
    assert res.ok is False
    assert "antivirus" in res.reason.lower()
