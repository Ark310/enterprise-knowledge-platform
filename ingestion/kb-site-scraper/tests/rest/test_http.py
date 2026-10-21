import asyncio
import time

import httpx
import pytest

from restscraper.http import Blocked, DocsClient, NotFound, Throttle


def _client(handler, interval=0.0):
    return DocsClient(Throttle(interval), transport=httpx.MockTransport(handler), backoff_s=0.01)


def test_403_raises_blocked():
    async def go():
        c = _client(lambda req: httpx.Response(403, text="<h1>403 Forbidden</h1>"))
        with pytest.raises(Blocked):
            await c.get_text("/x")
        await c.close()
    asyncio.run(go())


def test_forbidden_body_with_200_raises_blocked():
    async def go():
        c = _client(lambda req: httpx.Response(200, text="<title>403 Forbidden</title>"))
        with pytest.raises(Blocked):
            await c.get_text("/x")
        await c.close()
    asyncio.run(go())


def test_404_raises_not_found():
    async def go():
        c = _client(lambda req: httpx.Response(404))
        with pytest.raises(NotFound):
            await c.get_text("/missing")
        await c.close()
    asyncio.run(go())


def test_5xx_is_retried():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(500) if len(calls) == 1 else httpx.Response(200, text="ok")

    async def go():
        c = _client(handler)
        assert await c.get_text("/x") == "ok"
        await c.close()
    asyncio.run(go())
    assert len(calls) == 2


def test_browser_user_agent_sent():
    seen = {}

    def handler(req):
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200, text="ok")

    async def go():
        c = _client(handler)
        await c.get_text("/x")
        await c.close()
    asyncio.run(go())
    assert "Chrome/" in seen["ua"] and "Headless" not in seen["ua"]


def test_probe():
    async def go():
        ok = _client(lambda req: httpx.Response(200, text="Contoso REST API"))
        bad = _client(lambda req: httpx.Response(403))
        assert await ok.probe() is True
        assert await bad.probe() is False
        await ok.close()
        await bad.close()
    asyncio.run(go())


def test_throttle_spacing():
    async def go():
        t = Throttle(0.2)
        await t.wait()
        t0 = time.monotonic()
        await t.wait()
        return time.monotonic() - t0
    assert asyncio.run(go()) >= 0.18
