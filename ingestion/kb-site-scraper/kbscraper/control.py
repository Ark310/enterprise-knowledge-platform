"""Run control shared by the GUI thread and the async engine: cancel + pause/resume.

Ported from the Knowledge Base scraper's RunControl. The GUI thread flips the flags;
engine coroutines poll them at article boundaries via wait_if_paused_async(), which
sleeps instead of blocking so the event loop (and Playwright's keep-alive) keeps
running while paused.
"""
from __future__ import annotations

import asyncio
import threading


class RunControl:
    def __init__(self) -> None:
        self._cancelled = False
        self._resume = threading.Event()
        self._resume.set()  # set == running; cleared == paused
        # Live worker target from the GUI; None means "use the run's worker count".
        self.target_workers: int | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    def cancel(self) -> None:
        self._cancelled = True
        self._resume.set()  # wake waiters so they observe the cancel

    def pause(self) -> None:
        if not self._cancelled:
            self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    async def wait_if_paused_async(self, poll: float = 0.2) -> None:
        while not self._resume.is_set() and not self._cancelled:
            await asyncio.sleep(poll)
