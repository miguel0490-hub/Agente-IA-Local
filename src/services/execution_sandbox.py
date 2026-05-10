"""Secure Python execution in isolated Docker sandbox."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


ALLOWED_IMPORTS = {
    "math",
    "statistics",
    "random",
    "itertools",
    "functools",
    "collections",
    "datetime",
    "decimal",
    "fractions",
    "json",
    "re",
}
BLOCKED_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "os",
    "sys",
    "socket",
    "subprocess",
    "pathlib",
    "shutil",
}


@dataclass
class SandboxResult:
    """Outcome of sandbox execution."""

    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str = ""


class CodeSecurityError(Exception):
    """Raised when code violates sandbox policy."""


def validate_code_security(code: str) -> None:
    """Rejects dangerous syntax/imports before execution."""
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = []
            if isinstance(node, ast.Import):
                modules = [n.name.split(".")[0] for n in node.names]
            elif node.module:
                modules = [node.module.split(".")[0]]
            for module in modules:
                if module not in ALLOWED_IMPORTS:
                    raise CodeSecurityError(f"Import bloqueado: {module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_NAMES:
                raise CodeSecurityError(f"Llamada bloqueada: {node.func.id}")
            if isinstance(node.func, ast.Attribute):
                base = getattr(node.func.value, "id", "")
                if base in {"os", "sys", "socket", "subprocess", "pathlib", "shutil"}:
                    raise CodeSecurityError(f"Uso bloqueado: {base}.{node.func.attr}")
        elif isinstance(node, ast.Attribute):
            if getattr(node.value, "id", "") in {"os", "sys", "socket", "subprocess"}:
                raise CodeSecurityError("Acceso a módulo bloqueado.")


def run_python_in_docker(code: str, timeout_seconds: int = 8) -> SandboxResult:
    """Executes validated code inside a hardened ephemeral container."""
    validate_code_security(code)
    if not shutil.which("docker"):
        return SandboxResult(ok=False, error="Docker no está instalado o no está en PATH.")

    runner = textwrap.dedent(
        """
        import io, json, contextlib, traceback

        USER_CODE = open('/workspace/user_code.py', 'r', encoding='utf-8').read()
        out = io.StringIO()
        err = io.StringIO()
        payload = {"stdout": "", "stderr": "", "error": ""}
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exec(compile(USER_CODE, "<sandbox>", "exec"), {"__builtins__": __builtins__}, {})
        except Exception:
            payload["error"] = traceback.format_exc(limit=1)
        payload["stdout"] = out.getvalue()
        payload["stderr"] = err.getvalue()
        print(json.dumps(payload))
        """
    ).strip()

    with tempfile.TemporaryDirectory(prefix="safe-exec-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "user_code.py").write_text(code, encoding="utf-8")
        (tmp_path / "runner.py").write_text(runner, encoding="utf-8")

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--pids-limit",
            "64",
            "--cpus",
            "0.50",
            "--memory",
            "256m",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "-v",
            f"{tmp_path.as_posix()}:/workspace:ro",
            "python:3.11-alpine",
            "python",
            "/workspace/runner.py",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return SandboxResult(ok=False, error="Timeout de ejecución excedido. Proceso terminado.")

        if proc.returncode != 0:
            return SandboxResult(ok=False, error=(proc.stderr or "Fallo de contenedor sandbox.").strip())

        try:
            data = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except Exception:
            return SandboxResult(ok=False, error="Respuesta inválida del sandbox.")

        has_error = bool(data.get("error"))
        return SandboxResult(
            ok=not has_error,
            stdout=(data.get("stdout") or "").strip(),
            stderr=(data.get("stderr") or "").strip(),
            error=(data.get("error") or "").strip(),
        )
