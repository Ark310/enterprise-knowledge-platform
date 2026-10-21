"""QThreads that run discovery / scrape / audit off the GUI thread (adapted from kbscraper)."""
from __future__ import annotations

import asyncio
import traceback

from PySide6.QtCore import QThread, Signal

from kbscraper.control import RunControl
from kbscraper.state import RunState
from restscraper.discovery import SiteMap, discover
from restscraper.engine import Events, run_scrape
from restscraper.http import DocsClient, Throttle
from restscraper.library_index import audit, write_site_files
from restscraper.settings import Settings


class _Bridge(Events):
    def __init__(self, thread: "ScrapeThread"):
        self.t = thread

    def log(self, level, msg):
        self.t.log.emit(level, msg)

    def article(self, rec):
        self.t.article.emit(rec)

    def progress(self, counts):
        self.t.progress.emit(counts)

    def alert(self, severity, title, body):
        self.t.alert.emit(severity, title, body)

    def cooldown(self, active):
        self.t.cooldown.emit(active)


async def _discover(settings: Settings, log) -> SiteMap:
    client = DocsClient(Throttle(settings.min_interval_s))
    try:
        sm, pp, llms = await discover(client, log)
    finally:
        await client.close()
    sm.save()
    try:
        write_site_files(settings.output_path, pp, llms, sm.report)
    except OSError as exc:
        log("warning", f"Could not write the _site files: {exc}")
    return sm


class DiscoverThread(QThread):
    log = Signal(str, str)
    done = Signal(object)        # SiteMap or None
    failed = Signal(str)

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def run(self):
        try:
            self.done.emit(asyncio.run(_discover(self.settings, lambda lv, m: self.log.emit(lv, m))))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            self.done.emit(None)


class ScrapeThread(QThread):
    log = Signal(str, str)
    article = Signal(dict)
    progress = Signal(dict)
    alert = Signal(str, str, str)
    cooldown = Signal(bool)
    finished_report = Signal(dict)

    def __init__(self, state: RunState, page_ids: list[str], settings: Settings,
                 control: RunControl, sitemap: SiteMap | None):
        super().__init__()
        self.state, self.page_ids = state, page_ids
        self.settings, self.control, self.sitemap = settings, control, sitemap

    def run(self):
        try:
            report = asyncio.run(run_scrape(self.state, self.page_ids, self.settings,
                                            self.control, _Bridge(self), self.sitemap))
            self.finished_report.emit(report or {})
        except Exception as exc:
            self.log.emit("error", f"Scrape engine crashed: {type(exc).__name__}: {exc}\n"
                                   f"{traceback.format_exc(limit=5)}")
            self.alert.emit("error", "Scrape engine crashed",
                            f"{type(exc).__name__}: {exc}\n\nEverything scraped before the crash "
                            "is saved and the run is journaled — press 'Resume last run' to "
                            "continue where it stopped.")
            try:
                self.state.set_meta(status="crashed")
                self.state.compact()
            except Exception:
                pass
            self.finished_report.emit({"crashed": True})


class AuditThread(QThread):
    log = Signal(str, str)
    done = Signal(object, object)   # (SiteMap, audit dict) or (None, error str)

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    def run(self):
        try:
            sm = asyncio.run(_discover(self.settings, lambda lv, m: self.log.emit(lv, m)))
            self.done.emit(sm, audit(self.settings.output_path, sm))
        except Exception as exc:
            self.done.emit(None, f"{type(exc).__name__}: {exc}")
