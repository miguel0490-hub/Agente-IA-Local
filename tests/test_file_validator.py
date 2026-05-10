from src.services.file_validator import validate_uploaded_file
from src.services import file_validator


def test_blocks_executable_extension():
    result = validate_uploaded_file("malware.exe", b"MZ...")
    assert result.ok is False


def test_rejects_too_large_image_in_strict_mode(monkeypatch):
    monkeypatch.setenv("UPLOAD_POLICY", "strict")
    payload = b"\x89PNG\r\n\x1a\n" + b"a" * (16 * 1024 * 1024)
    result = validate_uploaded_file("test.png", payload)
    assert result.ok is False


def test_accepts_small_text_document():
    result = validate_uploaded_file("ok.txt", b"hello")
    assert result.ok is True


def test_rejects_mime_mismatch():
    result = validate_uploaded_file("fake.png", b"%PDF-1.4 not png")
    assert result.ok is False
    assert "MIME real" in result.reason


def test_rejects_corrupt_zip():
    result = validate_uploaded_file("bad.zip", b"PK\x00\x00invalid")
    assert result.ok is False
    assert "ZIP corrupto" in result.reason


def test_detect_magic_audio_wav():
    raw = b"RIFFxxxxWAVE" + b"\x00" * 10
    assert file_validator._detect_magic_type(raw) == "audio/wav"


def test_accepts_mp3_audio_upload():
    result = validate_uploaded_file("voz.mp3", b"ID3" + b"\x00" * 64)
    assert result.ok is True


def test_accepts_unknown_extension_in_permissive_mode(monkeypatch):
    monkeypatch.setenv("UPLOAD_POLICY", "permissive")
    result = validate_uploaded_file("archivo.customext", b"hello")
    assert result.ok is True
