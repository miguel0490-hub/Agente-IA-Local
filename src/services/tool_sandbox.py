"""Per-tool sandbox isolation.

Each tool type runs in its own sandboxed environment with tool-specific
resource limits and policies. Tools with side effects get stricter isolation.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from src.core.logger import get_logger
from src.services.sandbox_config import (
    ResourceLimits,
    SandboxPolicy,
    SecurityProfile,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolPolicy:
    """Per-tool execution policy."""

    tool_name: str
    sandbox_policy: SandboxPolicy
    requires_approval: bool = False
    max_invocations_per_session: int = 50
    cooldown_seconds: float = 0.0


_TOOL_POLICIES: dict[str, ToolPolicy] = {
    "execute_code": ToolPolicy(
        tool_name="execute_code",
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(cpu_cores=0.5, memory_mb=256, timeout_seconds=8),
            security=SecurityProfile(
                read_only_rootfs=True,
                no_new_privileges=True,
                drop_all_capabilities=True,
                network_disabled=True,
            ),
        ),
        requires_approval=True,
        max_invocations_per_session=20,
        cooldown_seconds=1.0,
    ),
    "search_web": ToolPolicy(
        tool_name="search_web",
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(cpu_cores=0.25, memory_mb=128, timeout_seconds=15),
            security=SecurityProfile(network_disabled=False),
        ),
        max_invocations_per_session=30,
        cooldown_seconds=2.0,
    ),
    "generate_image": ToolPolicy(
        tool_name="generate_image",
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(cpu_cores=0.25, memory_mb=128, timeout_seconds=60),
            security=SecurityProfile(network_disabled=False),
        ),
        max_invocations_per_session=10,
        cooldown_seconds=5.0,
    ),
    "create_file": ToolPolicy(
        tool_name="create_file",
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(
                cpu_cores=0.25,
                memory_mb=128,
                timeout_seconds=10,
                max_file_size_bytes=10_485_760,
            ),
            security=SecurityProfile(read_only_rootfs=False, network_disabled=True),
        ),
        max_invocations_per_session=50,
    ),
    "open_converter": ToolPolicy(
        tool_name="open_converter",
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(cpu_cores=1.0, memory_mb=512, timeout_seconds=30),
            security=SecurityProfile(network_disabled=True),
        ),
        requires_approval=True,
        max_invocations_per_session=10,
        cooldown_seconds=3.0,
    ),
}


class ToolInvocationTracker:
    """Tracks per-session tool invocation counts and cooldowns."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._last_invocation: dict[str, float] = {}

    def can_invoke(self, tool_name: str) -> tuple[bool, str]:
        """Checks if a tool can be invoked within policy limits."""
        policy = _TOOL_POLICIES.get(tool_name)
        if not policy:
            return True, ""

        count = self._counts.get(tool_name, 0)
        if count >= policy.max_invocations_per_session:
            return False, f"Límite de invocaciones alcanzado ({count}/{policy.max_invocations_per_session})"

        if policy.cooldown_seconds > 0:
            last = self._last_invocation.get(tool_name, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < policy.cooldown_seconds:
                remaining = policy.cooldown_seconds - elapsed
                return False, f"Cooldown activo ({remaining:.1f}s restantes)"

        return True, ""

    def record_invocation(self, tool_name: str) -> None:
        self._counts[tool_name] = self._counts.get(tool_name, 0) + 1
        self._last_invocation[tool_name] = time.monotonic()

    def get_stats(self) -> dict[str, int]:
        return dict(self._counts)

    def reset(self) -> None:
        self._counts.clear()
        self._last_invocation.clear()


def get_tool_policy(tool_name: str) -> ToolPolicy:
    """Returns the sandbox policy for a specific tool."""
    if tool_name in _TOOL_POLICIES:
        return _TOOL_POLICIES[tool_name]

    return ToolPolicy(
        tool_name=tool_name,
        sandbox_policy=SandboxPolicy(
            limits=ResourceLimits(cpu_cores=0.25, memory_mb=128, timeout_seconds=10),
            security=SecurityProfile.standard(),
        ),
    )


def register_tool_policy(tool_name: str, policy: ToolPolicy) -> None:
    """Registers or overrides a tool policy at runtime."""
    _TOOL_POLICIES[tool_name] = policy
    logger.info("Registered tool policy: %s (approval=%s, max=%d)",
                tool_name, policy.requires_approval, policy.max_invocations_per_session)
