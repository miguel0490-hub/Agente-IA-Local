from src.services import file_validator
import zipfile


def test_guess_group_variants():
    assert file_validator._guess_group(".png") == "image"
    assert file_validator._guess_group(".mp4") == "video"
    assert file_validator._guess_group(".mp3") == "audio"
    assert file_validator._guess_group(".txt") == "document"


def test_max_size_for_group_variants():
    assert file_validator._max_size_for_group("image") == file_validator.MAX_IMAGE_BYTES
    assert file_validator._max_size_for_group("video") == file_validator.MAX_VIDEO_BYTES
    assert file_validator._max_size_for_group("audio") == file_validator.MAX_AUDIO_BYTES
    assert file_validator._max_size_for_group("other") == file_validator.MAX_DOC_BYTES


def test_detect_magic_known_types():
    assert file_validator._detect_magic_type(b"%PDF-1.7") == "application/pdf"
    assert file_validator._detect_magic_type(b"\x89PNG\r\n\x1a\nabc") == "image/png"
    assert file_validator._detect_magic_type(b"\xff\xd8\xffabc") == "image/jpeg"
    assert file_validator._detect_magic_type(b"GIF89aabc") == "image/gif"
    assert file_validator._detect_magic_type(b"PK\x03\x04abc") == "application/zip"
    assert file_validator._detect_magic_type(b"0000ftyp00000") == "video/mp4"
    assert file_validator._detect_magic_type(b"ID3abc") == "audio/mpeg"
    assert file_validator._detect_magic_type(b"RIFFzzzzWAVEabcd") == "audio/wav"
    assert file_validator._detect_magic_type(b"unknown") == "application/octet-stream"


def test_matches_expected_type_audio_cases():
    assert file_validator._matches_expected_type(".mp3", "audio/mpeg") is True
    assert file_validator._matches_expected_type(".wav", "audio/wav") is True
    assert file_validator._matches_expected_type(".wav", "audio/mpeg") is False


def test_validate_uploaded_file_invalid_input_and_extension():
    assert file_validator.validate_uploaded_file("", b"x").ok is False
    assert file_validator.validate_uploaded_file("x.unknown", b"x").ok is False


def test_validate_uploaded_file_unknown_extension_permissive(monkeypatch):
    monkeypatch.setenv("UPLOAD_POLICY", "permissive")
    assert file_validator.validate_uploaded_file("x.unknown", b"x").ok is True


def test_get_upload_policy_default_production(monkeypatch):
    monkeypatch.delenv("UPLOAD_POLICY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert file_validator.get_upload_policy() == "strict"


def test_get_upload_policy_summary_non_empty():
    assert file_validator.get_upload_policy_summary()


def test_env_int_invalid_and_non_positive():
    assert file_validator._env_int("MAX_DOC_MB", 25) == 25
    import os

    os.environ["MAX_DOC_MB"] = "abc"
    assert file_validator._env_int("MAX_DOC_MB", 25) == 25
    os.environ["MAX_DOC_MB"] = "0"
    assert file_validator._env_int("MAX_DOC_MB", 25) == 25


def test_get_upload_policy_summary_permissive(monkeypatch):
    monkeypatch.setenv("UPLOAD_POLICY", "permissive")
    text = file_validator.get_upload_policy_summary()
    assert "modo pruebas" in text.lower()


def test_zip_bomb_checks_ratio_and_success_path():
    class BombZip:
        def infolist(self):
            return [type("I", (), {"file_size": 300 * 1024 * 1024, "compress_size": 1})()]

    class SafeZip:
        def infolist(self):
            return [type("I", (), {"file_size": 100, "compress_size": 50})()]

    original = zipfile.ZipFile
    try:
        zipfile.ZipFile = lambda *a, **k: BombZip()
        res = file_validator._check_zip_bomb(b"PK123")
        assert res.ok is False

        zipfile.ZipFile = lambda *a, **k: SafeZip()
        res2 = file_validator._check_zip_bomb(b"PK123")
        assert res2.ok is True
    finally:
        zipfile.ZipFile = original


def test_matches_expected_type_remaining_branches():
    assert file_validator._matches_expected_type(".jpg", "image/jpeg") is True
    assert file_validator._matches_expected_type(".gif", "image/gif") is True
    assert file_validator._matches_expected_type(".pdf", "application/pdf") is True
    assert file_validator._matches_expected_type(".mp4", "video/mp4") is True
