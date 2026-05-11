"""Sandbox runtime configuration and policy enforcement.

Defines security profiles, resource limits, and isolation policies for code
execution sandboxes. Supports Docker, gVisor (runsc), and Firecracker runtimes.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class SandboxRuntime(Enum):
    DOCKER = "docker"
    GVISOR = "gvisor"
    FIRECRACKER = "firecracker"


@dataclass(frozen=True)
class ResourceLimits:
    """Hard resource limits for a sandbox container."""

    cpu_cores: float = 0.5
    memory_mb: int = 256
    pids_limit: int = 64
    tmpfs_size_mb: int = 64
    timeout_seconds: int = 8
    max_output_bytes: int = 1_048_576  # 1 MB
    max_file_size_bytes: int = 10_485_760  # 10 MB


@dataclass(frozen=True)
class SecurityProfile:
    """Security profile for sandbox execution."""

    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    drop_all_capabilities: bool = True
    network_disabled: bool = True
    run_as_user: str = "65534:65534"
    seccomp_profile: str | None = None
    apparmor_profile: str | None = None

    @classmethod
    def maximum(cls) -> SecurityProfile:
        seccomp = _PROJECT_ROOT / "deploy" / "security" / "seccomp-sandbox.json"
        return cls(
            seccomp_profile=str(seccomp) if seccomp.exists() else None,
            apparmor_profile="superagente-sandbox",
        )

    @classmethod
    def standard(cls) -> SecurityProfile:
        return cls()


@dataclass(frozen=True)
class SandboxPolicy:
    """Complete sandbox policy combining limits, security, and runtime."""

    runtime: SandboxRuntime = SandboxRuntime.DOCKER
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    security: SecurityProfile = field(default_factory=SecurityProfile.standard)
    base_image: str = "python:3.11-alpine"
    auto_destroy: bool = True
    workspace_mount_mode: str = "ro"


def get_sandbox_policy() -> SandboxPolicy:
    """Resolves the active sandbox policy from environment configuration."""
    runtime_str = os.getenv("SANDBOX_RUNTIME", "docker").lower()
    runtime_map = {
        "docker": SandboxRuntime.DOCKER,
        "gvisor": SandboxRuntime.GVISOR,
        "firecracker": SandboxRuntime.FIRECRACKER,
    }
    runtime = runtime_map.get(runtime_str, SandboxRuntime.DOCKER)

    limits = ResourceLimits(
        cpu_cores=float(os.getenv("SANDBOX_CPU_CORES", "0.5")),
        memory_mb=int(os.getenv("SANDBOX_MEMORY_MB", "256")),
        pids_limit=int(os.getenv("SANDBOX_PIDS_LIMIT", "64")),
        timeout_seconds=int(os.getenv("SANDBOX_TIMEOUT", "8")),
    )

    use_max_security = os.getenv("SANDBOX_SECURITY", "standard").lower() == "maximum"
    security = SecurityProfile.maximum() if use_max_security else SecurityProfile.standard()

    return SandboxPolicy(
        runtime=runtime,
        limits=limits,
        security=security,
        base_image=os.getenv("SANDBOX_IMAGE", "python:3.11-alpine"),
    )


def detect_available_runtime() -> SandboxRuntime:
    """Detects the best available sandbox runtime on the host."""
    if shutil.which("firecracker"):
        logger.info("Firecracker runtime detected")
        return SandboxRuntime.FIRECRACKER

    docker_bin = shutil.which("docker")
    if docker_bin:
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.Runtimes}}"],
                capture_output=True, text=True, timeout=5,
            )
            if "runsc" in (result.stdout or ""):
                logger.info("gVisor (runsc) runtime detected")
                return SandboxRuntime.GVISOR
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        logger.info("Standard Docker runtime detected")
        return SandboxRuntime.DOCKER

    logger.warning("No container runtime detected")
    return SandboxRuntime.DOCKER


def build_docker_args(policy: SandboxPolicy, workspace_path: str) -> list[str]:
    """Builds the docker run command arguments from a policy."""
    args = ["docker", "run", "--rm"]

    if policy.runtime == SandboxRuntime.GVISOR:
        args.extend(["--runtime=runsc"])

    sec = policy.security
    lim = policy.limits

    if sec.network_disabled:
        args.extend(["--network", "none"])
    if sec.read_only_rootfs:
        args.append("--read-only")
    if sec.no_new_privileges:
        args.extend(["--security-opt", "no-new-privileges"])
    if sec.drop_all_capabilities:
        args.extend(["--cap-drop", "ALL"])
    if sec.run_as_user:
        args.extend(["--user", sec.run_as_user])
    if sec.seccomp_profile and Path(sec.seccomp_profile).exists():
        args.extend(["--security-opt", f"seccomp={sec.seccomp_profile}"])
    if sec.apparmor_profile:
        args.extend(["--security-opt", f"apparmor={sec.apparmor_profile}"])

    args.extend(["--pids-limit", str(lim.pids_limit)])
    args.extend(["--cpus", str(lim.cpu_cores)])
    args.extend(["--memory", f"{lim.memory_mb}m"])
    args.extend(["--tmpfs", f"/tmp:rw,noexec,nosuid,size={lim.tmpfs_size_mb}m"])

    args.extend(["-v", f"{workspace_path}:/workspace:{policy.workspace_mount_mode}"])
    args.append(policy.base_image)

    return args
