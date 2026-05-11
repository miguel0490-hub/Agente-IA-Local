"""Ephemeral sandbox runtime with full lifecycle management.

Orchestrates code execution in isolated, auto-destroying containers with
per-task workspace isolation, resource enforcement, and secure cleanup.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.logger import get_logger
from src.services.sandbox_config import (
    SandboxPolicy,
    SandboxRuntime,
    build_docker_args,
    get_sandbox_policy,
)

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Outcome of a sandboxed execution."""

    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    exit_code: int = -1
    duration_ms: int = 0
    sandbox_id: str = ""
    runtime: str = ""


@dataclass
class SandboxSession:
    """Tracks an ephemeral sandbox from creation to destruction."""

    sandbox_id: str
    workspace: Path
    policy: SandboxPolicy
    created_at: float = field(default_factory=time.monotonic)
    destroyed: bool = False

    def destroy(self) -> None:
        """Securely removes the workspace and all artifacts."""
        if self.destroyed:
            return
        try:
            if self.workspace.exists():
                shutil.rmtree(self.workspace, ignore_errors=True)
            self.destroyed = True
            logger.info("Sandbox %s destroyed (%.1fs lifetime)",
                        self.sandbox_id, time.monotonic() - self.created_at)
        except Exception as exc:
            logger.error("Failed to destroy sandbox %s: %s", self.sandbox_id, exc)


def _create_runner_script() -> str:
    """Generates the in-container runner script that captures stdout/stderr/errors."""
    return textwrap.dedent("""
        import io, json, contextlib, traceback, resource, signal, sys

        # Hard resource limits inside container
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        except (ValueError, resource.error):
            pass

        signal.alarm(10)

        USER_CODE = open('/workspace/user_code.py', 'r', encoding='utf-8').read()
        out = io.StringIO()
        err = io.StringIO()
        payload = {"stdout": "", "stderr": "", "error": "", "exit_code": 0}
        try:
            restricted_builtins = dict(__builtins__) if isinstance(__builtins__, dict) else dict(vars(__builtins__))
            for name in ['__import__', 'eval', 'exec', 'compile', 'open', 'input',
                         'globals', 'locals', 'vars', 'dir', 'getattr', 'setattr',
                         'delattr', 'breakpoint', 'exit', 'quit']:
                restricted_builtins.pop(name, None)

            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exec(compile(USER_CODE, "<sandbox>", "exec"), {"__builtins__": restricted_builtins}, {})
        except Exception:
            payload["error"] = traceback.format_exc(limit=3)
            payload["exit_code"] = 1
        payload["stdout"] = out.getvalue()[:1048576]
        payload["stderr"] = err.getvalue()[:1048576]
        print(json.dumps(payload))
    """).strip()


def create_sandbox(
    code: str,
    *,
    policy: SandboxPolicy | None = None,
    extra_files: dict[str, str] | None = None,
) -> SandboxSession:
    """Creates an ephemeral sandbox workspace with isolated files."""
    policy = policy or get_sandbox_policy()
    sandbox_id = f"sbx-{secrets.token_hex(8)}"

    workspace = Path(tempfile.mkdtemp(prefix=f"superagente-{sandbox_id}-"))

    (workspace / "user_code.py").write_text(code, encoding="utf-8")
    (workspace / "runner.py").write_text(_create_runner_script(), encoding="utf-8")

    if extra_files:
        for name, content in extra_files.items():
            safe_name = Path(name).name
            (workspace / safe_name).write_text(content, encoding="utf-8")

    return SandboxSession(
        sandbox_id=sandbox_id,
        workspace=workspace,
        policy=policy,
    )


def execute_in_sandbox(
    code: str,
    *,
    policy: SandboxPolicy | None = None,
    extra_files: dict[str, str] | None = None,
) -> ExecutionResult:
    """Full lifecycle: create sandbox -> execute code -> destroy sandbox."""
    from src.services.execution_sandbox import validate_code_security, CodeSecurityError

    try:
        validate_code_security(code)
    except (CodeSecurityError, SyntaxError) as exc:
        return ExecutionResult(ok=False, error=str(exc), runtime="pre-validation")

    policy = policy or get_sandbox_policy()
    session = create_sandbox(code, policy=policy, extra_files=extra_files)

    try:
        result = _run_container(session)
        return result
    finally:
        session.destroy()


def _run_container(session: SandboxSession) -> ExecutionResult:
    """Executes the runner inside a container using the session policy."""
    if not shutil.which("docker"):
        return ExecutionResult(
            ok=False,
            error="Docker not available",
            sandbox_id=session.sandbox_id,
            runtime="none",
        )

    args = build_docker_args(session.policy, session.workspace.as_posix())
    args.extend(["python", "/workspace/runner.py"])

    start = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=session.policy.limits.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _kill_container(session.sandbox_id)
        return ExecutionResult(
            ok=False,
            error="Execution timeout exceeded",
            sandbox_id=session.sandbox_id,
            runtime=session.policy.runtime.value,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    duration_ms = int((time.monotonic() - start) * 1000)

    if proc.returncode != 0:
        return ExecutionResult(
            ok=False,
            error=(proc.stderr or "Container execution failed").strip()[:4096],
            exit_code=proc.returncode,
            sandbox_id=session.sandbox_id,
            runtime=session.policy.runtime.value,
            duration_ms=duration_ms,
        )

    try:
        output_lines = (proc.stdout or "").strip().splitlines()
        data = json.loads(output_lines[-1]) if output_lines else {}
    except (json.JSONDecodeError, IndexError):
        return ExecutionResult(
            ok=False,
            error="Invalid sandbox response",
            sandbox_id=session.sandbox_id,
            runtime=session.policy.runtime.value,
            duration_ms=duration_ms,
        )

    has_error = bool(data.get("error"))
    return ExecutionResult(
        ok=not has_error,
        stdout=(data.get("stdout") or "").strip()[:session.policy.limits.max_output_bytes],
        stderr=(data.get("stderr") or "").strip()[:session.policy.limits.max_output_bytes],
        error=(data.get("error") or "").strip()[:4096],
        exit_code=data.get("exit_code", 0),
        sandbox_id=session.sandbox_id,
        runtime=session.policy.runtime.value,
        duration_ms=duration_ms,
    )


def _kill_container(sandbox_id: str) -> None:
    """Best-effort kill of a timed-out container."""
    try:
        subprocess.run(
            ["docker", "kill", sandbox_id],
            capture_output=True, timeout=5, check=False,
        )
    except Exception:
        pass


def cleanup_stale_sandboxes(max_age_seconds: int = 300) -> int:
    """Removes stale sandbox temp directories older than max_age_seconds."""
    cleaned = 0
    tmp_root = Path(tempfile.gettempdir())
    now = time.time()
    for entry in tmp_root.iterdir():
        if entry.name.startswith("superagente-sbx-") and entry.is_dir():
            age = now - entry.stat().st_mtime
            if age > max_age_seconds:
                shutil.rmtree(entry, ignore_errors=True)
                cleaned += 1
    if cleaned:
        logger.info("Cleaned %d stale sandbox directories", cleaned)
    return cleaned
