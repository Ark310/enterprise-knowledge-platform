"""Command-line runner (the GUI is the main entry point; this is handy for testing).

    python -m kbscraper.cli --spaces SHAccounts,Functions --workers 4
    python -m kbscraper.cli --resume
    python -m kbscraper.cli --retry
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from kbscraper.confluence import ConfluenceClient
from kbscraper.control import RunControl
from kbscraper.discovery import SiteMap, discover
from kbscraper.engine import Events, run_scrape
from kbscraper.settings import Settings
from kbscraper.state import FAILED, PENDING, RUNNING, WARNING, RunState


class _Print(Events):
    def log(self, level, msg):
        print(f"{level.upper():7} {msg}", flush=True)

    def alert(self, severity, title, body):
        print(f"\n*** {severity.upper()}: {title}\n{body}\n", flush=True)


def plan_records(sitemap: SiteMap, page_ids: set[str] | None = None) -> list[dict]:
    spaces = {s.key: s for s in sitemap.spaces}
    out = []
    for a in sitemap.articles:
        if page_ids is not None and a.page_id not in page_ids:
            continue
        sp = spaces[a.space_key]
        out.append({"page_id": a.page_id, "title": a.title, "space_key": a.space_key,
                    "space_name": sp.name, "product": sp.product,
                    "product_label": sp.product_label, "folder": a.folder, "url": a.url,
                    "content_type": a.content_type, "version": a.version})
    return out


async def _discover(settings: Settings, only: set[str] | None, ev: Events) -> SiteMap:
    client = ConfluenceClient(log=ev.log)
    try:
        sm = await discover(client, settings.excluded_spaces, ev.log, only_spaces=only)
    finally:
        await client.close()
    return sm


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Contoso KB site scraper")
    ap.add_argument("--spaces", help="comma-separated space keys (default: all)")
    ap.add_argument("--limit", type=int, help="only the first N articles (testing)")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--output")
    ap.add_argument("--no-screenshots", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--resume", action="store_true", help="continue the last run")
    ap.add_argument("--retry", action="store_true", help="retry failed + warning articles of the last run")
    args = ap.parse_args(argv)

    settings = Settings.load()
    if args.workers:
        settings.workers = args.workers
    if args.output:
        settings.output_dir = args.output
    if args.no_screenshots:
        settings.screenshots = False
    if args.headed:
        settings.headless = False
    ev = _Print()

    if args.resume or args.retry:
        rid = RunState.latest_id()
        if not rid:
            print("No previous run found.")
            return 1
        state = RunState.load(rid)
        statuses = (PENDING, RUNNING) + ((FAILED, WARNING) if args.retry else ())
        ids = state.ids_with_status(*statuses)
        for pid in ids:
            state.update(pid, status=PENDING, attempts=0)
        sitemap = SiteMap.load()
    else:
        only = set(args.spaces.split(",")) if args.spaces else None
        sitemap = asyncio.run(_discover(settings, only, ev))
        if not only:
            sitemap.save()
        records = plan_records(sitemap)
        if args.limit:
            records = records[: args.limit]
        state = RunState.create(records, {"spaces": sorted(only) if only else "all",
                                          "output_dir": settings.output_dir})
        ids = [r["page_id"] for r in records]

    report = asyncio.run(run_scrape(state, ids, settings, RunControl(), ev, sitemap))
    print("\nRESULT:", report.get("counts"), "elapsed", report.get("elapsed_s"), "s")
    return 0 if not state.ids_with_status(FAILED) else 2


if __name__ == "__main__":
    sys.exit(main())
