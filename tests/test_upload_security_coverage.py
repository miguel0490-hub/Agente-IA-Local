from src.services import upload_security


def test_scan_with_clamav_ok_returncode(monkeypatch):
    class Proc:
        returncode = 0

    monkeypatch.setenv("CLAMSCAN_BIN", "clamscan")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: Proc())
    res = upload_security._scan_with_clamav(b"abc", "a.txt")
    assert res.ok is True


def test_scan_with_clamav_unknown_returncode(monkeypatch):
    class Proc:
        returncode = 2

    monkeypatch.setenv("CLAMSCAN_BIN", "clamscan")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: Proc())
    res = upload_security._scan_with_clamav(b"abc", "a.txt")
    assert res.ok is False
    assert "Fallo en escaneo" in res.reason


def test_scan_with_clamav_exception(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setenv("CLAMSCAN_BIN", "clamscan")
    monkeypatch.setattr("subprocess.run", _raise)
    res = upload_security._scan_with_clamav(b"abc", "a.txt")
    assert res.ok is False
    assert "Error al ejecutar antivirus" in res.reason
