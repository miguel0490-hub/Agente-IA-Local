from src.security.tool_guard import ToolGuard


def test_tool_guard_default_allows():
    decision = ToolGuard.evaluate("create_file")
    assert decision.allowed is True
    assert decision.requires_confirmation is False


def test_tool_guard_open_converter_requires_confirmation():
    decision = ToolGuard.evaluate("open_converter")
    assert decision.allowed is True
    assert decision.requires_confirmation is True


def test_has_explicit_approval_case_insensitive():
    assert ToolGuard.has_explicit_approval("please [APPROVE:EXECUTE_CODE]", "execute_code") is True
    assert ToolGuard.has_explicit_approval("no marker", "execute_code") is False
