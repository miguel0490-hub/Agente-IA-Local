"""Execution Timeout Guard — security-level process supervision.

Higher-level guard than ``execution_watchdog.py``: enforces hard kill deadlines,
detects zombie/runaway processes, and provides cleanup guarantees. Designed to
protect the host from resource exhaustion by any subprocess spawned by the
application (code execution, file conversion, external tools).
"""

from __future__ import annotations

import os
import signal
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger(__name__)


class ProcessState(Enum):
    RUNNING = auto()
    COMPLETED = auto()
    TIMED_OUT = auto()
    ZOMBIE = auto()
    KILLED = auto()


@dataclass
class GuardedProcess:
    """A process under guard supervision."""

    pid: int
    label: str
    start_time: float
    hard_timeout: float
    soft_timeout: float
    state: ProcessState = ProcessState.RUNNING
    cpu_checks: list[float] = field(default_factory=list)
    on_kill: Callable[[], None] | None = None

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def is_expired(self) -> bool:
        return self.elapsed >= self.hard_timeout

    @property
    def is_soft_expired(self) -> bool:
        return self.elapsed >= self.soft_timeout


class ExecutionTimeoutGuard:
    """Security-grade process supervisor with zombie detection and hard kill."""

    _instance: ExecutionTimeoutGuard | None = None
    _init_lock = threading.Lock()

    def __init__(
        self,
        poll_interval: float = 3.0,
        default_hard_timeout: float = 120.0,
        default_soft_timeout: float = 60.0,
        max_concurrent: int = 10,
    ):
        self._guarded: dict[int, GuardedProcess] = {}
        self._lock = threading.Lock()
        self._poll_interval = poll_interval
        self._default_hard_timeout = default_hard_timeout
        self._default_soft_timeout = default_soft_timeout
        self._max_concurrent = max_concurrent
        self._running = False
        self._thread: threading.Thread | None = None
        self._kill_log: list[dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> ExecutionTimeoutGuard:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    hard = float(os.getenv("GUARD_HARD_TIMEOUT", "120"))
                    soft = float(os.getenv("GUARD_SOFT_TIMEOUT", "60"))
                    cls._instance = cls(
                        default_hard_timeout=hard,
                        default_soft_timeout=soft,
                    )
                    cls._instance.start()
        return cls._instance

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._supervisor_loop, daemon=True, name="exec-timeout-guard"
        )
        self._thread.start()
        logger.info(
            "ExecutionTimeoutGuard started (hard=%.0fs soft=%.0fs poll=%.1fs)",
            self._default_hard_timeout,
            self._default_soft_timeout,
            self._poll_interval,
        )

    def stop(self) -> None:
        self._running = False

    def guard(
        self,
        pid: int,
        label: str = "",
        hard_timeout: float | None = None,
        soft_timeout: float | None = None,
        on_kill: Callable[[], None] | None = None,
    ) -> bool:
        """Registers a process for guarded execution. Returns False if at capacity."""
        with self._lock:
            if len(self._guarded) >= self._max_concurrent:
                logger.warning(
                    "Guard capacity reached (%d/%d), rejecting pid=%d",
                    len(self._guarded),
                    self._max_concurrent,
                    pid,
                )
                return False

            entry = GuardedProcess(
                pid=pid,
                label=label or f"proc-{pid}",
                start_time=time.monotonic(),
                hard_timeout=hard_timeout or self._default_hard_timeout,
                soft_timeout=soft_timeout or self._default_soft_timeout,
                on_kill=on_kill,
            )
            self._guarded[pid] = entry

        logger.debug(
            "Guard: tracking pid=%d label=%s hard=%.0fs",
            pid,
            entry.label,
            entry.hard_timeout,
        )
        return True

    def release(self, pid: int) -> None:
        """Releases a process from guard (normal completion)."""
        with self._lock:
            entry = self._guarded.pop(pid, None)
        if entry:
            entry.state = ProcessState.COMPLETED
            logger.debug(
                "Guard: released pid=%d label=%s elapsed=%.1fs",
                pid,
                entry.label,
                entry.elapsed,
            )

    def _supervisor_loop(self) -> None:
        while self._running:
            time.sleep(self._poll_interval)
            self._check_processes()
            self._detect_zombies()

    def _check_processes(self) -> None:
        """Checks all guarded processes for timeout violations."""
        to_kill: list[GuardedProcess] = []

        with self._lock:
            for pid, entry in list(self._guarded.items()):
                if entry.state != ProcessState.RUNNING:
                    continue
                if entry.is_expired:
                    entry.state = ProcessState.TIMED_OUT
                    to_kill.append(entry)
                elif entry.is_soft_expired:
                    logger.warning(
                        "Guard: pid=%d label=%s soft timeout (%.0fs/%.0fs)",
                        pid,
                        entry.label,
                        entry.elapsed,
                        entry.hard_timeout,
                    )

        for entry in to_kill:
            self._force_kill(entry)

    def _detect_zombies(self) -> None:
        """Detects processes that no longer exist but are still tracked."""
        to_remove: list[int] = []

        with self._lock:
            for pid, entry in self._guarded.items():
                if entry.state != ProcessState.RUNNING:
                    continue
                if not self._process_exists(pid):
                    entry.state = ProcessState.ZOMBIE
                    to_remove.append(pid)
                    logger.warning(
                        "Guard: zombie detected pid=%d label=%s",
                        pid,
                        entry.label,
                    )

        for pid in to_remove:
            with self._lock:
                self._guarded.pop(pid, None)

    def _force_kill(self, entry: GuardedProcess) -> None:
        """Forcefully terminates a timed-out process."""
        try:
            if os.name == "nt":
                os.kill(entry.pid, signal.SIGTERM)
            else:
                os.kill(entry.pid, signal.SIGKILL)
            entry.state = ProcessState.KILLED
            logger.warning(
                "Guard: KILLED pid=%d label=%s (exceeded %.0fs hard timeout)",
                entry.pid,
                entry.label,
                entry.hard_timeout,
            )
        except ProcessLookupError:
            entry.state = ProcessState.ZOMBIE
        except OSError as exc:
            logger.error("Guard: failed to kill pid=%d: %s", entry.pid, exc)
        finally:
            self._kill_log.append({
                "pid": entry.pid,
                "label": entry.label,
                "elapsed": round(entry.elapsed, 1),
                "state": entry.state.name,
                "timestamp": time.time(),
            })
            if entry.on_kill:
                try:
                    entry.on_kill()
                except Exception as e:
                    logger.error("Guard: on_kill callback error for pid=%d: %s", entry.pid, e)
            with self._lock:
                self._guarded.pop(entry.pid, None)

    @staticmethod
    def _process_exists(pid: int) -> bool:
        """Checks if a process is still alive."""
        try:
            if os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._guarded.values() if e.state == ProcessState.RUNNING)

    def get_kill_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._kill_log[-limit:]

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            processes = [
                {
                    "pid": e.pid,
                    "label": e.label,
                    "elapsed": round(e.elapsed, 1),
                    "state": e.state.name,
                    "hard_timeout": e.hard_timeout,
                }
                for e in self._guarded.values()
            ]
        return {
            "active": self.active_count,
            "max_concurrent": self._max_concurrent,
            "processes": processes,
            "recent_kills": len(self._kill_log),
        }
