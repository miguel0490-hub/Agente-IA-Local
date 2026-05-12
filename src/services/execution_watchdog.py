"""Execution timeout watchdog — kills hanging processes that escape normal timeout."""

from __future__ import annotations

import os
import signal
import threading
from dataclasses import dataclass
from datetime import datetime

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WatchdogEntry:
    """Tracks a watched process."""
    pid: int
    label: str
    deadline: float
    killed: bool = False


class ExecutionWatchdog:
    """Background watchdog that forcefully terminates hanging processes."""

    _instance: ExecutionWatchdog | None = None
    _lock = threading.Lock()

    def __init__(self, poll_interval: float = 2.0):
        self._watched: dict[int, WatchdogEntry] = {}
        self._poll_interval = poll_interval
        self._running = False
        self._thread: threading.Thread | None = None

    @classmethod
    def get_instance(cls) -> ExecutionWatchdog:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.start()
        return cls._instance

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="exec-watchdog")
        self._thread.start()
        logger.info("Execution watchdog started (poll=%.1fs)", self._poll_interval)

    def stop(self) -> None:
        self._running = False

    def watch(self, pid: int, timeout_seconds: float, label: str = "") -> None:
        """Registers a process for watchdog monitoring."""
        import time
        deadline = time.monotonic() + timeout_seconds
        entry = WatchdogEntry(pid=pid, label=label or f"proc-{pid}", deadline=deadline)
        with self._lock:
            self._watched[pid] = entry
        logger.debug("Watchdog: tracking pid=%d label=%s timeout=%.0fs", pid, entry.label, timeout_seconds)

    def unwatch(self, pid: int) -> None:
        """Removes a process from watchdog monitoring (normal completion)."""
        with self._lock:
            self._watched.pop(pid, None)

    def _poll_loop(self) -> None:
        import time
        while self._running:
            time.sleep(self._poll_interval)
            self._check_deadlines()

    def _check_deadlines(self) -> None:
        import time
        now = time.monotonic()
        to_kill: list[WatchdogEntry] = []

        with self._lock:
            for pid, entry in list(self._watched.items()):
                if now >= entry.deadline and not entry.killed:
                    to_kill.append(entry)

        for entry in to_kill:
            self._kill_process(entry)

    def _kill_process(self, entry: WatchdogEntry) -> None:
        """Forcefully terminates a process that exceeded its deadline."""
        try:
            if os.name == "nt":
                os.kill(entry.pid, signal.SIGTERM)
            else:
                os.kill(entry.pid, signal.SIGKILL)
            entry.killed = True
            logger.warning(
                "Watchdog KILLED pid=%d label=%s (exceeded deadline)",
                entry.pid, entry.label,
            )
        except ProcessLookupError:
            pass
        except OSError as exc:
            logger.error("Watchdog failed to kill pid=%d: %s", entry.pid, exc)
        finally:
            with self._lock:
                self._watched.pop(entry.pid, None)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._watched)
