from src.core import sanitizer


def test_sanitize_markdown_text_empty():
    assert sanitizer.sanitize_markdown_text("") == ""


def test_sanitize_markdown_text_removes_html():
    text = "<script>alert(1)</script><b>hola</b>"
    out = sanitizer.sanitize_markdown_text(text)
    assert "<script>" not in out
    assert "<b>" not in out
    assert "hola" in out


def test_sanitize_markdown_text_fallback_html_escape(monkeypatch):
    monkeypatch.setattr(sanitizer, "bleach", None)
    out = sanitizer.sanitize_markdown_text("<b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in out


def test_escape_user_data_basic():
    assert sanitizer.escape_user_data('<script>alert(1)</script>') == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert sanitizer.escape_user_data("") == ""
    assert sanitizer.escape_user_data(None) == ""


def test_sanitize_html_output_with_allowed_tags():
    out = sanitizer.sanitize_html_output('<b>bold</b><script>evil</script>', allowed_tags=frozenset({"b"}))
    assert "<b>" in out
    assert "<script>" not in out


def test_sanitize_html_output_empty():
    assert sanitizer.sanitize_html_output("") == ""


def test_sanitize_html_output_fallback(monkeypatch):
    monkeypatch.setattr(sanitizer, "bleach", None)
    out = sanitizer.sanitize_html_output('<script>alert(1)</script>')
    assert "&lt;script&gt;" in out
