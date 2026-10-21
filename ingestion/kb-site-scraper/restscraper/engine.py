"""Async scrape engine for the REST API docs, modelled on the KB scraper's engine.

Robustness rules (as kbscraper.engine), plus the site's rate limit:
  * every page is attempted up to Settings.max_attempts times, requeued at the back
  * a hard per-page timeout means a hung page can never wedge a worker
  * a streak of real failures pauses the run with an alert
  * Blocked (the site's 403 rate limit) is NOT a failure: the page goes back to the
    queue without spending an attempt, every worker waits, and one probe checks the
    site until it answers again; if it stays blocked past Settings.cooldown_max_min
    the run pauses with an alert (Resume continues)
"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path

from kbscraper.control import RunControl
from kbscraper.state import DONE, FAILED, PENDING, RUNNING, WARNING, RunState
from restscraper.http import Blocked, DocsClient, NotFound, Throttle
from restscraper.page import scrape_page
from restscraper.settings import Settings


class Events:
    """Callback sink; the GUI subclasses this to forward to Qt signals."""
    def log(self, level: str, msg: str) -> None: ...
    def article(self, rec: dict) -> None: ...
    def progress(self, counts: dict) -> None: ...
    def alert(self, severity: str, title: str, body: str) -> None: ...
    def cooldown(self, active: bool) -> None: ...


async def run_scrape(state: RunState, page_ids: list[str], settings: Settings, control: RunControl,
                     events: Events, sitemap=None, *, client=None, pool=None, scrape=scrape_page,
                     probe_interval_s: float = 30.0) -> dict:
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    throttle = Throttle(settings.min_interval_s)
    own_client = client is None
    client = client or DocsClient(throttle)
    workers = max(1, min(6, settings.workers))
    if pool is None:
        from restscraper.browser import BrowserPool
        pool = BrowserPool(workers, settings.headless, throttle, log=events.log)
    started = time.monotonic()
    state.set_meta(status="running", last_started_at=datetime.now().isoformat(timespec="seconds"))
    pool_started = False

    try:
        if not await client.probe():
            events.alert("error", "Cannot reach the REST API docs",
                         "apidocs.contoso.example did not respond (or is refusing this "
                         "computer for a few minutes after heavy use).\n\nNothing was changed. Wait a "
                         "few minutes, then press Resume.")
            state.set_meta(status="stopped")
            return {"aborted": "site unreachable"}
        try:
            await pool.start()
            pool_started = True
        except Exception as exc:
            events.alert("error", "Chrome could not be started",
                         f"{type(exc).__name__}: {exc}\n\nThe REST API pages need a browser to capture "
                         "code snippets and the Try-it explorer. Install Google Chrome, then Resume.")
            state.set_meta(status="stopped")
            return {"aborted": "browser"}

        queue: asyncio.Queue[str] = asyncio.Queue()
        for pid in page_ids:
            queue.put_nowait(pid)
        total = len(page_ids)
        streak = {"fails": 0}
        breaker_lock = asyncio.Lock()
        in_flight: set[asyncio.Task] = set()
        clear = asyncio.Event()      # set = not cooling down
        clear.set()
        cool = {"task": None}
        blocked_after_ok: dict[str, int] = {}   # page -> times blocked while the site answered
        BLOCK_LIMIT = 3

        def emit(pid: str) -> None:
            events.article(dict(state.articles[pid]))
            events.progress(state.counts())

        async def cooldown() -> None:
            events.cooldown(True)
            events.log("warning", "The site is refusing requests (rate limit). Waiting for it to "
                                  "answer again — nothing is lost and no attempts are spent.")
            state.set_meta(status="cooling down")
            deadline = time.monotonic() + settings.cooldown_max_min * 60
            try:
                while not control.cancelled:
                    await asyncio.sleep(probe_interval_s)
                    if await client.probe():
                        events.log("info", "The site answers again — continuing.")
                        return
                    if time.monotonic() > deadline:
                        control.pause()
                        events.alert("warning", "Scrape paused — site still refusing requests",
                                     f"apidocs.contoso.example has refused this computer for "
                                     f"{settings.cooldown_max_min} minutes.\n\nEverything scraped so far "
                                     "is saved. Press Resume to try again later (or lower Workers).")
                        return
            finally:
                state.set_meta(status="running")
                events.cooldown(False)
                clear.set()

        def start_cooldown() -> None:
            if clear.is_set():
                clear.clear()
                cool["task"] = asyncio.ensure_future(cooldown())

        async def check_breaker() -> None:
            async with breaker_lock:
                limit = max(6, workers * 2)
                if streak["fails"] < limit or control.paused or control.cancelled:
                    return
                streak["fails"] = 0
                control.pause()
                events.alert("warning", "Scrape paused — repeated failures",
                             f"The last {limit} pages all failed.\n\nEverything scraped so far is "
                             "saved; pages with retries left are queued again. Check the Issues tab, "
                             "then press Resume (or lower Workers).")
                events.log("error", "Run paused by the failure breaker.")

        async def process(pid: str, tag: str) -> None:
            rec = state.articles[pid]
            attempt = int(rec.get("attempts", 0)) + 1
            t0 = time.monotonic()
            state.update(pid, status=RUNNING, attempts=attempt,
                         started_at=datetime.now().isoformat(timespec="seconds"))
            emit(pid)
            try:
                result = await asyncio.wait_for(
                    scrape(state.articles[pid], client, pool, output_dir, settings, events.log),
                    timeout=settings.page_timeout_s)
            except asyncio.CancelledError:
                state.update(pid, status=PENDING, attempts=attempt - 1, error="Stopped before finishing")
                emit(pid)
                raise
            except Blocked as exc:
                # The site still answering means this page itself is refused, not a rate
                # limit; after a few of those treat it as an ordinary failure, or a page
                # that always answers 403 would cycle forever without spending attempts.
                if await client.probe():
                    blocked_after_ok[pid] = blocked_after_ok.get(pid, 0) + 1
                if blocked_after_ok.get(pid, 0) < BLOCK_LIMIT:
                    state.update(pid, status=PENDING, attempts=attempt - 1,
                                 error="Site rate limit — queued again after the cool-down")
                    emit(pid)
                    queue.put_nowait(pid)
                    if not blocked_after_ok.get(pid):
                        start_cooldown()
                    return
                exc = RuntimeError(f"the site refuses this page (403) while serving others: {exc}")
                err = f"{type(exc).__name__}: {exc}"
                retry = attempt < settings.max_attempts
                blocked_after_ok[pid] = 0
                state.update(pid, status=PENDING if retry else FAILED, error=err,
                             duration_s=round(time.monotonic() - t0, 1),
                             finished_at=datetime.now().isoformat(timespec="seconds"))
                emit(pid)
                if retry:
                    queue.put_nowait(pid)
                events.log("warning" if retry else "error", f"{tag}{rec.get('title')} — {err}")
                return
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    err = f"Timed out after {settings.page_timeout_s}s"
                else:
                    err = f"{type(exc).__name__}: {str(exc)[:300]}"
                retry = attempt < settings.max_attempts and not isinstance(exc, (NotFound, FileNotFoundError))
                state.update(pid, status=PENDING if retry else FAILED, error=err,
                             duration_s=round(time.monotonic() - t0, 1),
                             finished_at=datetime.now().isoformat(timespec="seconds"))
                emit(pid)
                if retry:
                    events.log("warning", f"{tag}Retrying later ({attempt}/{settings.max_attempts}): "
                                          f"{rec.get('title')} — {err}")
                    queue.put_nowait(pid)
                else:
                    events.log("error", f"{tag}FAILED: {rec.get('title')} — {err}")
                streak["fails"] += 1
                await check_breaker()
                return
            streak["fails"] = 0
            state.update(pid, status=result["status"], issues=result["issues"], notes=result["notes"],
                         error="", found=result["found"], expected=result["expected"],
                         files=result["files"], files_expected=result["files_expected"],
                         screenshots=result["screenshots"],
                         duration_s=round(time.monotonic() - t0, 1),
                         finished_at=datetime.now().isoformat(timespec="seconds"))
            emit(pid)
            if result["status"] == WARNING:
                events.log("warning", f"{tag}Saved with {len(result['issues'])} issue(s): "
                                      f"{rec.get('title')} — {result['issues'][0]}")
            else:
                events.log("info", f"{tag}OK: {rec.get('title')} ({result['files']} file(s))")

        async def worker(idx: int) -> None:
            tag = f"[W{idx + 1}] " if workers > 1 else ""
            while not control.cancelled:
                await control.wait_if_paused_async()
                while not clear.is_set() and not control.cancelled:
                    await asyncio.sleep(0.2)
                if control.cancelled:
                    return
                if control.paused:       # e.g. the cool-down gave up: honour the pause first
                    continue
                target = control.target_workers or workers
                if idx >= max(1, min(workers, target)):
                    if queue.empty():
                        return
                    await asyncio.sleep(0.5)
                    continue
                try:
                    pid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    if not in_flight and clear.is_set():
                        return
                    await asyncio.sleep(0.5)
                    continue
                if state.articles.get(pid, {}).get("status") in (DONE, WARNING):
                    continue
                task = asyncio.ensure_future(process(pid, tag))
                in_flight.add(task)
                try:
                    while not task.done():
                        await asyncio.wait({task}, timeout=0.5)
                        if control.cancelled and not task.done():
                            task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        return
                    except Exception as exc:
                        events.log("error", f"{tag}Internal error on {pid}: {exc}\n"
                                            f"{traceback.format_exc(limit=3)}")
                        state.update(pid, status=FAILED, error=f"Internal error: {exc}")
                        emit(pid)
                finally:
                    in_flight.discard(task)

        events.log("info", f"Scraping {total} page(s) with {workers} worker(s), at most one page load "
                           f"every {settings.min_interval_s:g}s → {output_dir}")
        results = await asyncio.gather(*(worker(i) for i in range(workers)), return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                events.log("error", f"A worker stopped unexpectedly: {type(res).__name__}: {res}")
        if cool["task"] is not None and not cool["task"].done():
            cool["task"].cancel()

        counts = state.counts()
        finished = counts[PENDING] == 0 and counts[RUNNING] == 0
        report = {"counts": counts, "elapsed_s": round(time.monotonic() - started, 1)}
        if sitemap is not None:
            try:
                from restscraper.library_index import audit, write_indexes
                write_indexes(output_dir, sitemap)
                report["audit"] = audit(output_dir, sitemap)
                a = report["audit"]
                events.log("info", f"Library audit: {a['on_disk']} on disk / {a['live_articles']} live, "
                                   f"{len(a['missing'])} missing, {len(a['warnings'])} with warnings, "
                                   f"{len(a['stale'])} stale")
            except Exception as exc:
                events.log("error", f"Index/audit failed: {type(exc).__name__}: {exc}")
        state.set_meta(status="completed" if finished else "stopped",
                       last_finished_at=datetime.now().isoformat(timespec="seconds"),
                       last_report={k: v for k, v in report.items() if k != "audit"})
        return report
    finally:
        state.compact()
        if pool_started:
            await pool.close()
        if own_client:
            await client.close()
