from src.security.tool_guard import ToolGuard, _tool_audit_log, log_tool_execution


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


def test_audit_log_trimming():
    """Verify audit log trims when exceeding 10_000 entries."""
    original_len = len(_tool_audit_log)
    while len(_tool_audit_log) <= 10_000:
        _tool_audit_log.append({"action": "filler"})
    log_tool_execution(user_id=0, action="trim_test", role="user", allowed=True)
    assert len(_tool_audit_log) <= 10_001
    # Cleanup
    while len(_tool_audit_log) > original_len + 1:
        _tool_audit_log.pop(0)
