"""Integration tests for the Execution Timeout Guard."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import pytest

os.environ.setdefault("APP_SECRET_KEY", "pytest-ci-placeholder-not-for-production")

from src.security.execution_timeout_guard import (
    ExecutionTimeoutGuard,
    GuardedProcess,
    ProcessState,
)


class TestGuardedProcess:

    def test_elapsed_tracking(self):
        gp = GuardedProcess(
            pid=99999, label="test", start_time=time.monotonic() - 5.0,
            hard_timeout=10.0, soft_timeout=3.0,
        )
        assert gp.elapsed >= 5.0
        assert gp.is_soft_expired
        assert not gp.is_expired

    def test_hard_expiry(self):
        gp = GuardedProcess(
            pid=99999, label="test", start_time=time.monotonic() - 15.0,
            hard_timeout=10.0, soft_timeout=5.0,
        )
        assert gp.is_expired


class TestExecutionTimeoutGuard:

    def setup_method(self):
        self.guard = ExecutionTimeoutGuard(
            poll_interval=0.1,
            default_hard_timeout=2.0,
            default_soft_timeout=1.0,
            max_concurrent=5,
        )

    def test_guard_and_release(self):
        ok = self.guard.guard(pid=99999, label="test-proc", hard_timeout=10.0)
        assert ok
        assert self.guard.active_count == 1
        self.guard.release(99999)
        assert self.guard.active_count == 0

    def test_capacity_limit(self):
        for i in range(5):
            assert self.guard.guard(pid=90000 + i, label=f"proc-{i}")
        assert not self.guard.guard(pid=90005, label="overflow")
        for i in range(5):
            self.guard.release(90000 + i)

    def test_status_report(self):
        self.guard.guard(pid=88888, label="status-test")
        status = self.guard.get_status()
        assert status["active"] == 1
        assert status["max_concurrent"] == 5
        assert len(status["processes"]) == 1
        self.guard.release(88888)

    def test_kill_log_initially_empty(self):
        assert self.guard.get_kill_log() == []

    def test_zombie_detection(self):
        self.guard.guard(pid=1, label="zombie-test")
        self.guard._detect_zombies()
        assert self.guard.active_count == 0

    def test_real_process_guard_and_kill(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ok = self.guard.guard(
                pid=proc.pid, label="sleep-proc",
                hard_timeout=0.3, soft_timeout=0.1,
            )
            assert ok
            time.sleep(0.5)
            self.guard._check_processes()
            log = self.guard.get_kill_log()
            assert len(log) >= 1
            assert log[-1]["label"] == "sleep-proc"
        finally:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
