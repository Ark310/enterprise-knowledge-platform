"""Async scrape engine: N workers over a queue of articles, sharing one HTTP client and
one screenshot browser.

Robustness rules
  * every article is attempted up to Settings.max_attempts times (requeued at the
    back so a transient outage has time to clear); 404s are not retried
  * a hard per-article timeout means a hung page can never wedge a worker
  * after a streak of consecutive failures the engine checks the site; if it is
    unreachable (or failures continue) the run PAUSES with an alert instead of
    burning through the queue — Resume continues, nothing is lost
  * Stop cancels in-flight articles immediately and puts them back to pending, so
    "Resume last run" redoes them; every status change is journaled (state.py)
"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path

from kbscraper.article import scrape_article
from kbscraper.confluence import ConfluenceClient, NotFound
from kbscraper.control import RunControl
from kbscraper.discovery import SiteMap
from kbscraper.library_index import audit, write_indexes
from kbscraper.settings import Settings
from kbscraper.state import DONE, FAILED, PENDING, RUNNING, WARNING, RunState


class Events:
    """Callback sink; the GUI subclasses this to forward to Qt signals."""
    def log(self, level: str, msg: str) -> None: ...
    def article(self, rec: dict) -> None: ...
    def progress(self, counts: dict) -> None: ...
    def alert(self, severity: str, title: str, body: str) -> None: ...


async def site_reachable(client: ConfluenceClient) -> bool:
    try:
        await asyncio.wait_for(client.get_json("/rest/api/space", {"limit": 1}), timeout=60)
        return True
    except Exception:
        return False


async def run_scrape(state: RunState, page_ids: list[str], settings: Settings,
                     control: RunControl, events: Events, sitemap: SiteMap | None = None) -> dict:
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    client = ConfluenceClient(log=events.log, max_concurrency=max(8, settings.workers * 3))
    shots = None
    started = time.monotonic()
    state.set_meta(status="running", last_started_at=datetime.now().isoformat(timespec="seconds"))

    try:
        if not await site_reachable(client):
            events.alert("error", "Cannot reach help.contoso.example",
                         "The knowledge base did not respond.\n\nNothing was changed. Check the "
                         "network connection, then press Resume.")
            state.set_meta(status="stopped")
            return {"aborted": "site unreachable"}

        if settings.screenshots:
            from kbscraper.screenshots import ScreenshotService
            shots = ScreenshotService(headless=settings.headless, log=events.log,
                                      size=max(1, min(10, settings.workers)))
            try:
                await shots.start()
            except Exception as exc:
                events.alert("warning", "Screenshots unavailable",
                             f"Chrome/Edge could not be started ({type(exc).__name__}).\n\n"
                             "The scrape will continue without screenshots; affected articles "
                             "are flagged as warnings so you can retry them later.")
                events.log("error", f"Screenshot browser failed to start: {exc}")
                shots = None

        queue: asyncio.Queue[str] = asyncio.Queue()
        for pid in page_ids:
            queue.put_nowait(pid)
        total = len(page_ids)
        workers = max(1, min(10, settings.workers))
        streak = {"fails": 0}
        breaker_lock = asyncio.Lock()
        in_flight: set[asyncio.Task] = set()

        def emit(pid: str) -> None:
            events.article(dict(state.articles[pid]))
            events.progress(state.counts())

        async def check_breaker() -> None:
            async with breaker_lock:
                limit = max(6, workers * 2)
                if streak["fails"] < limit or control.paused or control.cancelled:
                    return
                reachable = await site_reachable(client)
                streak["fails"] = 0
                control.pause()
                if reachable:
                    events.alert("warning", "Scrape paused — repeated failures",
                                 f"The last {limit} articles all failed even though the site is "
                                 "reachable.\n\nEverything scraped so far is saved; articles with "
                                 "retries left are queued again. Check the Issues tab, then press "
                                 "Resume (or lower Workers).")
                else:
                    events.alert("error", "Scrape paused — site unreachable",
                                 "help.contoso.example stopped responding.\n\nEverything scraped so "
                                 "far is saved. When the connection is back, press Resume.")
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
                    scrape_article(client, state.articles[pid], output_dir,
                                   screenshots=shots, screenshots_expected=settings.screenshots,
                                   log=events.log),
                    timeout=settings.article_timeout_s)
            except asyncio.CancelledError:
                state.update(pid, status=PENDING, error="Stopped before finishing")
                emit(pid)
                raise
            except Exception as exc:
                if isinstance(exc, asyncio.TimeoutError):
                    err = f"Timed out after {settings.article_timeout_s}s"
                else:
                    err = f"{type(exc).__name__}: {str(exc)[:300]}"
                retry = attempt < settings.max_attempts and not isinstance(exc, NotFound)
                state.update(pid, status=PENDING if retry else FAILED, error=err,
                             duration_s=round(time.monotonic() - t0, 1),
                             finished_at=datetime.now().isoformat(timespec="seconds"))
                emit(pid)
                if retry:
                    events.log("warning", f"{tag}Retrying later ({attempt}/{settings.max_attempts}): "
                                          f"{rec['title']} — {err}")
                    queue.put_nowait(pid)
                else:
                    events.log("error", f"{tag}FAILED: {rec['title']} — {err}")
                streak["fails"] += 1
                await check_breaker()
                return
            streak["fails"] = 0
            state.update(pid, status=result["status"], issues=result["issues"], notes=result["notes"], error="",
                         found=result["found"], expected=result["expected"],
                         files=result["files"], files_expected=result["files_expected"],
                         screenshots=result["screenshots"],
                         duration_s=round(time.monotonic() - t0, 1),
                         finished_at=datetime.now().isoformat(timespec="seconds"))
            emit(pid)
            if result["status"] == WARNING:
                events.log("warning", f"{tag}Saved with {len(result['issues'])} issue(s): "
                                      f"{rec['title']} — {result['issues'][0]}")
            else:
                events.log("info", f"{tag}OK: {rec['title']} ({result['files']} file(s))")

        async def worker(idx: int) -> None:
            tag = f"[W{idx + 1}] " if workers > 1 else ""
            while not control.cancelled:
                await control.wait_if_paused_async()
                if control.cancelled:
                    return
                target = control.target_workers or workers
                if idx >= max(1, min(workers, target)):
                    if queue.empty():
                        return
                    await asyncio.sleep(0.5)      # parked by the live worker setting
                    continue
                try:
                    pid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    # Another worker may still requeue a retry; wait for in-flight work.
                    if not in_flight:
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
                    except Exception as exc:     # a bug in process() must not kill the run
                        events.log("error", f"{tag}Internal error on {pid}: {exc}\n"
                                            f"{traceback.format_exc(limit=3)}")
                        state.update(pid, status=FAILED, error=f"Internal error: {exc}")
                        emit(pid)
                finally:
                    in_flight.discard(task)

        events.log("info", f"Scraping {total} article(s) with {workers} worker(s)"
                           f"{', screenshots on' if shots else ''} → {output_dir}")
        results = await asyncio.gather(*(worker(i) for i in range(workers)),
                                       return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                events.log("error", f"A worker stopped unexpectedly: {type(res).__name__}: {res}")

        counts = state.counts()
        finished = counts[PENDING] == 0 and counts[RUNNING] == 0
        report = {"counts": counts, "elapsed_s": round(time.monotonic() - started, 1)}
        if sitemap is not None:
            try:
                write_indexes(output_dir, sitemap)
                run_spaces = {r.get("space_key") for r in state.articles.values()}
                report["audit"] = audit(output_dir, sitemap, spaces=run_spaces)
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
        if shots is not None:
            await shots.close()
        await client.close()
