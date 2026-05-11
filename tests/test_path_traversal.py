"""Tests for path traversal protection in path_guard."""
from __future__ import annotations
import os, pytest, tempfile
os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.security.path_guard import safe_filename, safe_join


@pytest.fixture
def tmp_output(tmp_path):
    return tmp_path / "output"


class TestSafeFilename:
    @pytest.mark.parametrize("malicious", [
        "../../../etc/passwd",
        "..\\..\\windows\\system32\\config",
        "/etc/shadow",
        "C:\\Windows\\System32\\evil.dll",
        "....//....//etc/passwd",
        "foo/../../../bar.txt",
    ])
    def test_blocks_traversal_payloads(self, malicious, tmp_output):
        result = safe_filename(malicious, tmp_output)
        assert str(result).startswith(str(tmp_output.resolve()))
        assert ".." not in result.name

    def test_strips_leading_dots(self, tmp_output):
        result = safe_filename(".hidden_file.txt", tmp_output)
        assert not result.name.startswith(".")

    def test_handles_empty_filename(self, tmp_output):
        result = safe_filename("", tmp_output)
        assert result.name.startswith("file_")
        assert result.suffix == ".bin"

    def test_handles_none(self, tmp_output):
        result = safe_filename(None, tmp_output)
        assert result.name.startswith("file_")

    def test_uuid_prefix(self, tmp_output):
        result = safe_filename("report.pdf", tmp_output, prefix_uuid=True)
        assert "_report.pdf" in result.name
        assert len(result.name) > len("report.pdf")

    def test_sanitizes_special_chars(self, tmp_output):
        result = safe_filename('file<>:"|?.txt', tmp_output)
        assert "<" not in result.name
        assert ">" not in result.name

    def test_reserved_names_windows(self, tmp_output):
        result = safe_filename("CON.txt", tmp_output)
        assert result.name.startswith("_CON")

    def test_creates_output_dir(self, tmp_path):
        new_dir = tmp_path / "nonexistent" / "deep"
        result = safe_filename("test.txt", new_dir)
        assert new_dir.exists()


class TestSafeJoin:
    def test_blocks_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="traversal"):
            safe_join(tmp_path, "../../etc/passwd")

    def test_allows_normal_path(self, tmp_path):
        result = safe_join(tmp_path, "subdir/file.txt")
        assert str(result).startswith(str(tmp_path.resolve()))
