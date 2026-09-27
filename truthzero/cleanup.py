"""Cleanup registry — always registered BEFORE execution.

SIGINT, crashes, and budget exhaustion all trigger reverse-order cleanup.
Mirrors Pentest-Swarm-AI internal/pipeline/cleanup*.go.
"""
from __future__ import annotations

import atexit
import signal
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CleanupTask:
    name: str
    fn: Callable[[], None]
    order: int = 0


class CleanupRegistry:
    def __init__(self):
        self._tasks: list[CleanupTask] = []
        self._installed = False
        self._done = False

    def register(self, name: str, fn: Callable[[], None], order: int = 0) -> None:
        self._tasks.append(CleanupTask(name, fn, order))
        self.install()

    def install(self) -> None:
        if self._installed:
            return
        self._installed = True
        try:
            signal.signal(signal.SIGINT, self._on_signal)
            signal.signal(signal.SIGTERM, self._on_signal)
        except Exception:
            pass
        atexit.register(self.run_all)

    def _on_signal(self, signum, frame) -> None:  # noqa: ANN001
        self.run_all()
        # Re-raise KeyboardInterrupt for SIGINT so CLI exits normally.
        if signum == signal.SIGINT:
            raise KeyboardInterrupt

    def run_all(self) -> list[str]:
        if self._done:
            return []
        self._done = True
        ran: list[str] = []
        for task in sorted(self._tasks, key=lambda t: t.order, reverse=True):
            try:
                task.fn()
                ran.append(task.name)
            except Exception:
                ran.append(f"{task.name} (failed)")
        return ran

    def reset(self) -> None:
        self._tasks.clear()
        self._done = False


# Global registry — import and register; execution order is reverse.
GLOBAL_CLEANUP = CleanupRegistry()
