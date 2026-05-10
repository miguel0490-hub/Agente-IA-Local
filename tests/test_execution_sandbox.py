from src.services.execution_sandbox import CodeSecurityError, validate_code_security
from src.services import execution_sandbox


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
    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: None)
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Docker" in res.error


def test_run_python_in_docker_container_error(monkeypatch):
    class Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_sandbox.subprocess, "run", lambda *a, **k: Proc())
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "boom" in res.error


def test_run_python_in_docker_timeout(monkeypatch):
    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: "docker")

    def _raise_timeout(*args, **kwargs):
        raise execution_sandbox.subprocess.TimeoutExpired(cmd="docker", timeout=1)

    monkeypatch.setattr(execution_sandbox.subprocess, "run", _raise_timeout)
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Timeout" in res.error


def test_run_python_in_docker_invalid_json(monkeypatch):
    class Proc:
        returncode = 0
        stdout = "not-json"
        stderr = ""

    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_sandbox.subprocess, "run", lambda *a, **k: Proc())
    res = execution_sandbox.run_python_in_docker("print('x')")
    assert res.ok is False
    assert "Respuesta inválida" in res.error
