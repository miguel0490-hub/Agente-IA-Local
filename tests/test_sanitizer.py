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
