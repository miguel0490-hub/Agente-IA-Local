from src.services.execution_sandbox import CodeSecurityError, validate_code_security
from src.services import execution_sandbox
from unittest.mock import MagicMock


def test_validate_code_security_blocks_os_import():
    code = "import os\nprint('x')"
    try:
        validate_code_security(code)
        assert False, "expected CodeSecurityError"
    except CodeSecurityError:
        assert True


def test_validate_code_security_blocks_eval():
    code = "print(eval('2+2'))"
    try:
        validate_code_security(code)
        assert False, "expected CodeSecurityError"
    except CodeSecurityError:
        assert True


def test_validate_code_security_allows_math():
    code = "import math\nprint(math.sqrt(9))"
    validate_code_security(code)


def test_run_python_in_docker_without_docker(monkeypatch):
    monkeypatch.setattr(
        execution_sandbox.subprocess,
        "Popen",
        MagicMock(side_effect=FileNotFoundError("docker not found")),
    )
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Docker" in res.error


def test_run_python_in_docker_container_error(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = ("", "boom")
    mock_proc.pid = 99999
    monkeypatch.setattr(
        execution_sandbox.subprocess, "Popen", MagicMock(return_value=mock_proc)
    )
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "boom" in res.error


def test_run_python_in_docker_timeout(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.kill.return_value = None
    mock_proc.communicate.side_effect = [
        execution_sandbox.subprocess.TimeoutExpired(cmd="docker", timeout=1),
        ("", ""),
    ]
    monkeypatch.setattr(
        execution_sandbox.subprocess, "Popen", MagicMock(return_value=mock_proc)
    )
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Timeout" in res.error


def test_run_python_in_docker_invalid_json(monkeypatch):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = ("not-json", "")
    mock_proc.pid = 99999
    monkeypatch.setattr(
        execution_sandbox.subprocess, "Popen", MagicMock(return_value=mock_proc)
    )
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Respuesta inválida" in res.error
