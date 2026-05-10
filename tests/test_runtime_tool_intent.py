from src.ui.chat.runtime import _normalize_tool_by_user_intent


def test_normalize_tool_forces_pdf_when_prompt_requests_pdf():
    tool = {"action": "create_file", "filename": "informe.html", "content": "<html>x</html>"}
    out = _normalize_tool_by_user_intent(tool, "hazme un PDF exhaustivo")
    assert out["filename"] == "informe.pdf"


def test_normalize_tool_keeps_non_pdf_requests():
    tool = {"action": "create_file", "filename": "informe.html"}
    out = _normalize_tool_by_user_intent(tool, "hazme una web")
    assert out["filename"] == "informe.html"


def test_normalize_tool_ignores_non_create_file():
    tool = {"action": "edit_file", "filename": "x.html"}
    out = _normalize_tool_by_user_intent(tool, "pdf")
    assert out["filename"] == "x.html"
