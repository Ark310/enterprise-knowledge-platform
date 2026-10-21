import asyncio

from kbscraper.control import RunControl
from kbscraper.state import DONE, FAILED, RunState
from restscraper.engine import Events, run_scrape
from restscraper.http import Blocked
from restscraper.settings import Settings


class FakeClient:
    def __init__(self, probes):
        self.probes = list(probes)
        self.probed = 0

    async def probe(self):
        self.probed += 1
        return self.probes.pop(0) if self.probes else True

    async def close(self):
        pass


class FakePool:
    async def start(self):
        pass

    async def close(self):
        pass


class Recorder(Events):
    def __init__(self):
        self.logs, self.cool = [], []

    def log(self, level, msg):
        self.logs.append((level, msg))

    def cooldown(self, active):
        self.cool.append(active)


OK = {"status": DONE, "issues": [], "notes": [], "found": {}, "expected": {}, "files": 1,
      "files_expected": 1, "screenshots": 1}


def _run(tmp_path, scrape, probes, ids=("a",)):
    st = RunState.create([{"page_id": i, "title": i, "folder": i} for i in ids], {}, runs_dir=tmp_path)
    s = Settings(output_dir=str(tmp_path / "out"), workers=2, max_attempts=2)
    ev = Recorder()
    client = FakeClient(probes)
    report = asyncio.run(run_scrape(st, list(ids), s, RunControl(), ev, client=client, pool=FakePool(),
                                    scrape=scrape, probe_interval_s=0.01))
    return st, report, ev, client


def test_engine_cooldown_on_blocked(tmp_path):
    calls = {"a": 0}

    async def scrape(rec, client, pool, out, settings, log):
        calls["a"] += 1
        if calls["a"] == 1:
            raise Blocked("403")
        return OK

    # first probe at start passes (site reachable), then one failed probe during cooldown, then OK
    st, report, ev, client = _run(tmp_path, scrape, [True, False, True])
    assert st.articles["a"]["status"] == DONE
    assert st.articles["a"]["attempts"] == 1          # the blocked try was not counted
    assert ev.cool == [True, False]
    assert client.probed >= 3


def test_engine_retries_then_fails(tmp_path):
    async def scrape(rec, client, pool, out, settings, log):
        raise RuntimeError("boom")

    st, report, ev, _ = _run(tmp_path, scrape, [True])
    assert st.articles["a"]["status"] == FAILED and st.articles["a"]["attempts"] == 2
    assert "boom" in st.articles["a"]["error"]


def test_engine_aborts_when_site_unreachable(tmp_path):
    async def scrape(*a):
        raise AssertionError("must not scrape")

    st, report, ev, _ = _run(tmp_path, scrape, [False])
    assert report == {"aborted": "site unreachable"}


def test_engine_page_always_403_is_not_endless(tmp_path):
    async def scrape(rec, client, pool, out, settings, log):
        raise Blocked("403 for this page only")

    st, report, ev, _ = _run(tmp_path, scrape, [True] * 50)    # the site itself keeps answering
    assert st.articles["a"]["status"] == FAILED
    assert "refuses this page" in st.articles["a"]["error"]
