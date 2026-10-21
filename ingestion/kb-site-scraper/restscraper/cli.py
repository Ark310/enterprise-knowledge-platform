"""Command line:  python -m restscraper.cli [--sections deal,bank] [--only slug,...] [--out DIR]
                                         [--resume | --retry] [--workers N] [--no-screenshots]"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from kbscraper.control import RunControl
from kbscraper.state import FAILED, PENDING, RUNNING, WARNING, RunState
from restscraper.discovery import discover
from restscraper.engine import Events, run_scrape
from restscraper.http import DocsClient, Throttle
from restscraper.library_index import write_site_files
from restscraper.settings import RUNS_DIR, Settings


class _Print(Events):
    def log(self, level, msg):
        print(f"{level.upper():7s} {msg}", flush=True)

    def alert(self, severity, title, body):
        print(f"\n*** {title}\n{body}\n", flush=True)

    def cooldown(self, active):
        print("COOLDOWN " + ("started" if active else "ended"), flush=True)


async def _discover(settings: Settings, ev: Events):
    client = DocsClient(Throttle(settings.min_interval_s))
    try:
        sm, pp, llms = await discover(client, ev.log)
    finally:
        await client.close()
    sm.save()
    write_site_files(settings.output_path, pp, llms, sm.report)
    return sm


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="restscraper")
    ap.add_argument("--sections", help="comma-separated section slugs (e.g. deal,bank)")
    ap.add_argument("--only", help="comma-separated page slugs (e.g. authorization/login-via-web-user)")
    ap.add_argument("--out", help="output folder (default: REST API)")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--no-screenshots", action="store_true")
    ap.add_argument("--show-browser", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--resume", action="store_true")
    g.add_argument("--retry", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    s = Settings.load()
    if args.out:
        s.output_dir = str(Path(args.out).resolve())
    if args.workers:
        s.workers = max(1, min(6, args.workers))
    if args.no_screenshots:
        s.screenshots = False
    if args.show_browser:
        s.headless = False
    ev = _Print()

    sm = asyncio.run(_discover(s, ev))
    if args.resume or args.retry:
        rid = RunState.latest_id(RUNS_DIR)
        if not rid:
            print("No previous run.")
            return 1
        state = RunState.load(rid, RUNS_DIR)
        wanted = (PENDING, RUNNING) if args.resume else (FAILED, WARNING, PENDING, RUNNING)
        ids = state.ids_with_status(*wanted)
        for pid in ids:
            state.update(pid, status=PENDING, **({"attempts": 0, "issues": []} if args.retry else {}))
    else:
        keys = set(args.sections.split(",")) if args.sections else None
        recs = sm.records(section_keys=keys)
        if args.only:
            only = set(args.only.split(","))
            recs = [r for r in recs if r["slug"] in only]
        if not recs:
            print("Nothing matches.")
            return 1
        state = RunState.create(recs, {"output_dir": s.output_dir, "kind": "cli"}, runs_dir=RUNS_DIR)
        ids = [r["page_id"] for r in recs]
    report = asyncio.run(run_scrape(state, ids, s, RunControl(), ev, sm))
    print(report.get("counts", report))
    c = report.get("counts") or {}
    return 0 if not (c.get(FAILED) or c.get(WARNING)) and not report.get("aborted") else 2


if __name__ == "__main__":
    sys.exit(main())
