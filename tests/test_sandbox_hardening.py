"""Tests for sandbox hardening: security profiles, resource limits, isolation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.sandbox_config import (
    ResourceLimits,
    SandboxPolicy,
    SandboxRuntime,
    SecurityProfile,
    build_docker_args,
    detect_available_runtime,
    get_sandbox_policy,
)
from src.services.sandbox_runtime import (
    ExecutionResult,
    SandboxSession,
    cleanup_stale_sandboxes,
    create_sandbox,
    execute_in_sandbox,
)
from src.services.tool_sandbox import (
    ToolInvocationTracker,
    ToolPolicy,
    get_tool_policy,
    register_tool_policy,
)


class TestSecurityProfile:
    def test_standard_profile_defaults(self):
        profile = SecurityProfile.standard()
        assert profile.read_only_rootfs is True
        assert profile.no_new_privileges is True
        assert profile.drop_all_capabilities is True
        assert profile.network_disabled is True
        assert profile.run_as_user == "65534:65534"

    def test_maximum_profile(self):
        profile = SecurityProfile.maximum()
        assert profile.read_only_rootfs is True
        assert profile.no_new_privileges is True
        assert profile.apparmor_profile == "superagente-sandbox"

    def test_profile_is_frozen(self):
        profile = SecurityProfile.standard()
        with pytest.raises(AttributeError):
            profile.read_only_rootfs = False


class TestResourceLimits:
    def test_defaults(self):
        limits = ResourceLimits()
        assert limits.cpu_cores == 0.5
        assert limits.memory_mb == 256
        assert limits.pids_limit == 64
        assert limits.timeout_seconds == 8
        assert limits.max_output_bytes == 1_048_576

    def test_custom_limits(self):
        limits = ResourceLimits(cpu_cores=1.0, memory_mb=512, timeout_seconds=30)
        assert limits.cpu_cores == 1.0
        assert limits.memory_mb == 512

    def test_limits_are_frozen(self):
        limits = ResourceLimits()
        with pytest.raises(AttributeError):
            limits.cpu_cores = 2.0


class TestSandboxPolicy:
    def test_default_policy(self):
        policy = SandboxPolicy()
        assert policy.runtime == SandboxRuntime.DOCKER
        assert policy.auto_destroy is True
        assert policy.workspace_mount_mode == "ro"

    @patch.dict("os.environ", {
        "SANDBOX_RUNTIME": "gvisor",
        "SANDBOX_CPU_CORES": "1.0",
        "SANDBOX_MEMORY_MB": "512",
        "SANDBOX_TIMEOUT": "15",
    })
    def test_get_sandbox_policy_from_env(self):
        policy = get_sandbox_policy()
        assert policy.runtime == SandboxRuntime.GVISOR
        assert policy.limits.cpu_cores == 1.0
        assert policy.limits.memory_mb == 512
        assert policy.limits.timeout_seconds == 15


class TestBuildDockerArgs:
    def test_standard_args(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/workspace")

        assert "--rm" in args
        assert "--network" in args
        assert args[args.index("--network") + 1] == "none"
        assert "--read-only" in args
        assert "--cap-drop" in args
        assert args[args.index("--cap-drop") + 1] == "ALL"

    def test_gvisor_runtime_arg(self):
        policy = SandboxPolicy(runtime=SandboxRuntime.GVISOR)
        args = build_docker_args(policy, "/tmp/workspace")
        assert "--runtime=runsc" in args

    def test_seccomp_profile_included(self):
        seccomp_path = Path(__file__).parent.parent / "deploy" / "security" / "seccomp-sandbox.json"
        if seccomp_path.exists():
            profile = SecurityProfile(seccomp_profile=str(seccomp_path))
            policy = SandboxPolicy(security=profile)
            args = build_docker_args(policy, "/tmp/workspace")
            assert any(f"seccomp={seccomp_path}" in a for a in args)

    def test_user_restriction(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/workspace")
        assert "--user" in args
        assert args[args.index("--user") + 1] == "65534:65534"

    def test_resource_limits_in_args(self):
        policy = SandboxPolicy(limits=ResourceLimits(cpu_cores=0.5, memory_mb=256, pids_limit=64))
        args = build_docker_args(policy, "/tmp/workspace")
        assert "--cpus" in args
        assert args[args.index("--cpus") + 1] == "0.5"
        assert "--memory" in args
        assert args[args.index("--memory") + 1] == "256m"
        assert "--pids-limit" in args
        assert args[args.index("--pids-limit") + 1] == "64"


class TestSandboxSession:
    def test_create_and_destroy(self):
        code = "print('hello')"
        session = create_sandbox(code)
        assert session.workspace.exists()
        assert (session.workspace / "user_code.py").exists()
        assert (session.workspace / "runner.py").exists()
        assert session.sandbox_id.startswith("sbx-")
        assert not session.destroyed

        session.destroy()
        assert session.destroyed
        assert not session.workspace.exists()

    def test_double_destroy_is_safe(self):
        session = create_sandbox("x = 1")
        session.destroy()
        session.destroy()
        assert session.destroyed

    def test_extra_files_written(self):
        session = create_sandbox("x = 1", extra_files={"data.json": '{"key": "value"}'})
        assert (session.workspace / "data.json").exists()
        content = (session.workspace / "data.json").read_text()
        assert json.loads(content) == {"key": "value"}
        session.destroy()


class TestExecuteInSandbox:
    def test_rejects_dangerous_code(self):
        result = execute_in_sandbox("import os; os.system('rm -rf /')")
        assert not result.ok
        assert "bloqueado" in result.error.lower() or "blocked" in result.error.lower()

    def test_rejects_syntax_error(self):
        result = execute_in_sandbox("def invalid(")
        assert not result.ok

    @patch("src.services.sandbox_runtime.shutil.which", return_value=None)
    def test_no_docker_returns_error(self, mock_which):
        result = execute_in_sandbox("print(1)")
        assert not result.ok
        assert "Docker" in result.error or "docker" in result.error.lower()


class TestToolInvocationTracker:
    def test_allows_within_limits(self):
        tracker = ToolInvocationTracker()
        ok, reason = tracker.can_invoke("execute_code")
        assert ok
        assert reason == ""

    def test_blocks_over_limit(self):
        tracker = ToolInvocationTracker()
        for _ in range(20):
            tracker.record_invocation("execute_code")
        ok, reason = tracker.can_invoke("execute_code")
        assert not ok
        assert "límite" in reason.lower() or "Límite" in reason

    def test_cooldown_enforced(self):
        tracker = ToolInvocationTracker()
        tracker.record_invocation("search_web")
        ok, reason = tracker.can_invoke("search_web")
        assert not ok
        assert "cooldown" in reason.lower()

    def test_unknown_tool_always_allowed(self):
        tracker = ToolInvocationTracker()
        ok, _ = tracker.can_invoke("unknown_tool")
        assert ok

    def test_reset_clears_state(self):
        tracker = ToolInvocationTracker()
        for _ in range(20):
            tracker.record_invocation("execute_code")
        tracker.reset()
        ok, _ = tracker.can_invoke("execute_code")
        assert ok

    def test_stats(self):
        tracker = ToolInvocationTracker()
        tracker.record_invocation("execute_code")
        tracker.record_invocation("execute_code")
        tracker.record_invocation("search_web")
        stats = tracker.get_stats()
        assert stats["execute_code"] == 2
        assert stats["search_web"] == 1


class TestToolPolicies:
    def test_get_known_policy(self):
        policy = get_tool_policy("execute_code")
        assert policy.tool_name == "execute_code"
        assert policy.requires_approval is True
        assert policy.sandbox_policy.security.network_disabled is True

    def test_get_unknown_returns_default(self):
        policy = get_tool_policy("nonexistent_tool")
        assert policy.tool_name == "nonexistent_tool"
        assert policy.sandbox_policy.limits.timeout_seconds == 10

    def test_register_custom_policy(self):
        custom = ToolPolicy(
            tool_name="custom_tool",
            sandbox_policy=SandboxPolicy(limits=ResourceLimits(timeout_seconds=5)),
            requires_approval=True,
            max_invocations_per_session=3,
        )
        register_tool_policy("custom_tool", custom)
        retrieved = get_tool_policy("custom_tool")
        assert retrieved.requires_approval is True
        assert retrieved.max_invocations_per_session == 3


class TestSeccompProfile:
    def test_seccomp_json_is_valid(self):
        seccomp_path = Path(__file__).parent.parent / "deploy" / "security" / "seccomp-sandbox.json"
        if seccomp_path.exists():
            data = json.loads(seccomp_path.read_text())
            assert data["defaultAction"] == "SCMP_ACT_ERRNO"
            assert "syscalls" in data
            assert len(data["syscalls"]) > 0
            allowed_syscalls = data["syscalls"][0]["names"]
            assert "read" in allowed_syscalls
            assert "write" in allowed_syscalls
            assert "execve" in allowed_syscalls

    def test_seccomp_blocks_dangerous_syscalls(self):
        seccomp_path = Path(__file__).parent.parent / "deploy" / "security" / "seccomp-sandbox.json"
        if seccomp_path.exists():
            data = json.loads(seccomp_path.read_text())
            all_allowed = set()
            for entry in data["syscalls"]:
                all_allowed.update(entry["names"])
            dangerous = {"reboot", "kexec_load", "init_module", "delete_module",
                         "swapon", "swapoff", "acct", "ioperm", "iopl"}
            for syscall in dangerous:
                assert syscall not in all_allowed, f"Dangerous syscall {syscall} should be blocked"


class TestSandboxEscapeAttempts:
    """Verifies that common sandbox escape vectors are blocked."""

    @pytest.mark.parametrize("code", [
        "import os; os.system('cat /etc/passwd')",
        "import subprocess; subprocess.run(['id'])",
        "import socket; socket.socket()",
        "__import__('os').popen('whoami').read()",
        "eval('__import__(\"os\").system(\"id\")')",
        "exec('import sys; sys.exit(0)')",
        "open('/etc/shadow', 'r').read()",
        "import pathlib; pathlib.Path('/etc/passwd').read_text()",
        "import shutil; shutil.rmtree('/')",
    ])
    def test_code_validation_blocks_escapes(self, code):
        result = execute_in_sandbox(code)
        assert not result.ok, f"Should block escape attempt: {code}"

    @pytest.mark.parametrize("code", [
        "import os\nexec('print(1)')",
        "globals()['__builtins__']['__import__']('os')",
        "getattr(__builtins__, '__import__')('os')",
    ])
    def test_indirect_escape_attempts(self, code):
        result = execute_in_sandbox(code)
        assert not result.ok, f"Should block indirect escape: {code}"


class TestPrivilegeEscalation:
    """Verifies Docker args prevent privilege escalation."""

    def test_no_new_privileges(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/ws")
        assert "--security-opt" in args
        idx = args.index("--security-opt")
        assert "no-new-privileges" in args[idx + 1]

    def test_all_caps_dropped(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/ws")
        cap_idx = args.index("--cap-drop")
        assert args[cap_idx + 1] == "ALL"

    def test_unprivileged_user(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/ws")
        user_idx = args.index("--user")
        assert args[user_idx + 1] == "65534:65534"

    def test_read_only_filesystem(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/ws")
        assert "--read-only" in args


class TestFileIsolation:
    def test_workspace_mounted_readonly(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/workspace")
        vol_args = [a for a in args if "/workspace:ro" in a]
        assert len(vol_args) == 1

    def test_tmpfs_noexec(self):
        policy = SandboxPolicy()
        args = build_docker_args(policy, "/tmp/ws")
        tmpfs_idx = args.index("--tmpfs")
        tmpfs_val = args[tmpfs_idx + 1]
        assert "noexec" in tmpfs_val
        assert "nosuid" in tmpfs_val


class TestRuntimeDetection:
    @patch("subprocess.run")
    @patch("shutil.which", side_effect=lambda x: "/usr/bin/docker" if x == "docker" else None)
    def test_detects_gvisor(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(stdout="runc runsc", returncode=0)
        runtime = detect_available_runtime()
        assert runtime == SandboxRuntime.GVISOR

    @patch("subprocess.run")
    @patch("shutil.which", side_effect=lambda x: "/usr/bin/docker" if x == "docker" else None)
    def test_detects_docker(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(stdout="runc", returncode=0)
        runtime = detect_available_runtime()
        assert runtime == SandboxRuntime.DOCKER

    @patch("shutil.which", side_effect=lambda x: "/usr/bin/firecracker" if x == "firecracker" else None)
    def test_detects_firecracker(self, mock_which):
        runtime = detect_available_runtime()
        assert runtime == SandboxRuntime.FIRECRACKER
