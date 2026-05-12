from src.services import execution_sandbox
from unittest.mock import MagicMock


def test_validate_code_security_blocks_attribute_access():
    code = "import math\nos.system('x')"
    try:
        execution_sandbox.validate_code_security(code)
        assert False, "expected CodeSecurityError"
    except execution_sandbox.CodeSecurityError:
        assert True


def test_run_python_in_docker_success_payload(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = ('{"stdout":"ok","stderr":"","error":""}\n', "")
    mock_proc.pid = 99999
    monkeypatch.setattr(
        execution_sandbox.subprocess, "Popen", MagicMock(return_value=mock_proc)
    )
    res = execution_sandbox.run_python_in_docker("print('ok')")
    assert res.ok is True
    assert res.stdout == "ok"


def test_run_python_in_docker_payload_with_error(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = ('{"stdout":"","stderr":"","error":"trace"}\n', "")
    mock_proc.pid = 99999
    monkeypatch.setattr(
        execution_sandbox.subprocess, "Popen", MagicMock(return_value=mock_proc)
    )
    res = execution_sandbox.run_python_in_docker("print('ok')")
    assert res.ok is False
    assert res.error == "trace"


def test_validate_code_security_blocks_import_from_and_attribute():
    try:
        execution_sandbox.validate_code_security("from os import path")
        assert False, "expected CodeSecurityError"
    except execution_sandbox.CodeSecurityError:
        assert True

    try:
        execution_sandbox.validate_code_security("import math\nos.path")
        assert False, "expected CodeSecurityError"
    except execution_sandbox.CodeSecurityError:
        assert True
