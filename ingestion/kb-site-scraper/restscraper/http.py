"""HTTP access to the docs site: one shared throttle, browser user agent, block detection.

The site rate-limits by IP and answers 403 to everything for a few minutes when it
does. That is reported as Blocked (never as a page failure) so the engine can cool
down and continue without spending attempts.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from restscraper.guard import classify
from restscraper.settings import BASE_URL

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")


class Blocked(Exception):
    """The site refused us (rate limit / 403)."""


class NotFound(Exception):
    pass


def looks_blocked(status: int, text: str) -> bool:
    return status == 403 or "<title>403 Forbidden</title>" in text[:2000] \
        or text[:200].lstrip().startswith("<html><head><title>403")


class Throttle:
    """A minimum gap between requests, shared by every worker and browser."""

    def __init__(self, min_interval_s: float):
        self.min_interval_s = max(0.0, float(min_interval_s))
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next:
                await asyncio.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self.min_interval_s


class DocsClient:
    def __init__(self, throttle: Throttle, transport=None, backoff_s: float = 2.0, retries: int = 3):
        self.throttle = throttle
        self.backoff_s = backoff_s
        self.retries = retries
        self._http = httpx.AsyncClient(
            base_url=BASE_URL, transport=transport, follow_redirects=True, timeout=60,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})

    async def get_text(self, path_or_url: str) -> str:
        last: Exception | None = None
        for attempt in range(self.retries):
            await self.throttle.wait()
            try:
                r = await self._http.get(path_or_url)
            except httpx.HTTPError as exc:
                last = exc
            else:
                text = r.text
                if looks_blocked(r.status_code, text):
                    raise Blocked(f"HTTP {r.status_code} for {path_or_url}")
                if r.status_code == 404:
                    raise NotFound(path_or_url)
                if r.status_code < 400:
                    return text
                last = RuntimeError(f"HTTP {r.status_code} for {path_or_url}")
                if r.status_code < 500 and r.status_code != 429:
                    raise last
            await asyncio.sleep(self.backoff_s * (attempt + 1))
        raise last or RuntimeError(f"GET {path_or_url} failed")

    async def get_bytes(self, url: str) -> tuple[bytes, str]:
        """Download an asset (images). Returns (content, content type). Only the docs
        host is rate-limited; asset hosts (S3) skip the throttle."""
        if url.startswith("/") or url.startswith(BASE_URL):
            await self.throttle.wait()
        r = await self._http.get(url, follow_redirects=False)
        hops = 0
        while r.is_redirect and hops < 5:      # follow only to allowlisted hosts
            target = str(r.next_request.url)
            if classify("GET", target) != "allow":
                raise RuntimeError(f"redirect to a host outside the safety allowlist: {target}")
            r = await self._http.get(target, follow_redirects=False)
            hops += 1
        if r.status_code == 403 and BASE_URL in str(r.url):
            raise Blocked(f"HTTP 403 for {url}")
        r.raise_for_status()
        if (r.headers.get("content-length") and not r.headers.get("content-encoding")
                and int(r.headers["content-length"]) != len(r.content)):
            raise RuntimeError(f"incomplete download of {url}")
        return r.content, r.headers.get("content-type", "")

    async def probe(self) -> bool:
        try:
            r = await self._http.get("/llms.txt")
            return r.status_code == 200 and not looks_blocked(r.status_code, r.text)
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        await self._http.aclose()
