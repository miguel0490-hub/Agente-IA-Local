"""Tests de normalización de contenido create_file."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.core.agent_tools import parse_tool_calls
from src.services.file_factory import FileFactory
from src.services.text_unescape import unescape_llm_file_content


def test_unescape_literal_newlines_and_trailing_quote():
    raw = '\\n<!DOCTYPE html>\\n<html><body>OK</body></html>"\\n'
    out = unescape_llm_file_content(raw)
    assert out.startswith("<!DOCTYPE html>")
    assert "\\n" not in out
    assert not out.endswith('"')


def test_parse_tool_calls_preserves_html_newlines_in_json():
    payload = {
        "action": "create_file",
        "filename": "index.html",
        "content": "<!DOCTYPE html>\n<html>\n<head><title>T</title></head>\n<body>Hi</body>\n</html>",
    }
    text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    _, tools = parse_tool_calls(text)
    assert len(tools) == 1
    assert "<html>" in tools[0]["content"]
    assert "\\n" not in tools[0]["content"]


def test_create_file_html_with_script_tag_is_not_blocked():
    payload = {
        "action": "create_file",
        "filename": "index.html",
        "content": (
            '<!DOCTYPE html><html><head><link rel="stylesheet" href="style.css">'
            '</head><body><script src="app.js" defer></script></body></html>'
        ),
    }
    text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"
    _, tools = parse_tool_calls(text)
    assert len(tools) == 1
    assert tools[0]["filename"] == "index.html"
    assert "<script" in tools[0]["content"]


def test_file_factory_writes_real_html():
    content = '\\n<!DOCTYPE html>\\n<html><head></head><body><p>Test</p></body></html>"'
    with tempfile.TemporaryDirectory() as tmp:
        factory = FileFactory(output_dir=tmp)
        path = factory.execute_tool(
            {
                "action": "create_file",
                "filename": "index.html",
                "content": content,
            }
        )
        assert path
        written = Path(path).read_text(encoding="utf-8")
        assert written.startswith("<!DOCTYPE html>")
        assert "\\n" not in written[:80]
