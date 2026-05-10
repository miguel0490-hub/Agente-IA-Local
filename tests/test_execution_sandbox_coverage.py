from src.services import execution_sandbox


def test_validate_code_security_blocks_attribute_access():
    code = "import math\nos.system('x')"
    try:
        execution_sandbox.validate_code_security(code)
        assert False, "expected CodeSecurityError"
    except execution_sandbox.CodeSecurityError:
        assert True


def test_run_python_in_docker_success_payload(monkeypatch):
    class Proc:
        returncode = 0
        stdout = '{"stdout":"ok","stderr":"","error":""}\n'
        stderr = ""

    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_sandbox.subprocess, "run", lambda *a, **k: Proc())
    res = execution_sandbox.run_python_in_docker("print('ok')")
    assert res.ok is True
    assert res.stdout == "ok"


def test_run_python_in_docker_payload_with_error(monkeypatch):
    class Proc:
        returncode = 0
        stdout = '{"stdout":"","stderr":"","error":"trace"}\n'
        stderr = ""

    monkeypatch.setattr(execution_sandbox.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(execution_sandbox.subprocess, "run", lambda *a, **k: Proc())
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
