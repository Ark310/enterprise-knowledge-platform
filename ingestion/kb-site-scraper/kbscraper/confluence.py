"""Async Confluence REST client with retry/backoff and verified, atomic downloads."""
from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urljoin

import httpx

from kbscraper.settings import BASE_URL

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ContosoKBSiteScraper/5"
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class NotFound(Exception):
    """The site answered 404/410 — retrying will not help."""


class HttpError(Exception):
    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status


class IncompleteDownload(Exception):
    pass


def absolute(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return urljoin(BASE_URL + "/", url)


class ConfluenceClient:
    def __init__(self, *, retries: int = 5, max_concurrency: int = 8,
                 timeout: float = 60.0, log=None):
        self._retries = retries
        self._sem = asyncio.Semaphore(max_concurrency)
        self._log = log or (lambda level, msg: None)
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(timeout, connect=20.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=max_concurrency * 2),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = min(30.0, 1.5 * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
        if retry_after:
            try:
                delay = max(delay, min(120.0, float(retry_after)))
            except ValueError:
                pass
        await asyncio.sleep(delay)

    async def get_json(self, path: str, params: dict | None = None) -> dict:
        url = absolute(path)
        last: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                async with self._sem:
                    resp = await self._client.get(url, params=params)
                if resp.status_code in (404, 410):
                    raise NotFound(f"HTTP {resp.status_code} for {url}")
                if resp.status_code in RETRY_STATUSES:
                    last = HttpError(resp.status_code, url)
                    self._log("warning", f"API {resp.status_code}, retry {attempt}/{self._retries}: {url}")
                    await self._backoff(attempt, resp.headers.get("Retry-After"))
                    continue
                if resp.status_code >= 400:
                    raise HttpError(resp.status_code, url)
                return resp.json()
            except (httpx.TransportError, ValueError) as exc:
                # ValueError covers a truncated/garbled JSON body.
                last = exc
                self._log("warning", f"API {type(exc).__name__}, retry {attempt}/{self._retries}: {url}")
                await self._backoff(attempt)
        raise last or HttpError(0, url)

    async def paginate(self, path: str, params: dict | None = None) -> AsyncIterator[dict]:
        """Yield every result, following _links.next until exhausted."""
        data = await self.get_json(path, params)
        while True:
            for item in data.get("results", []):
                yield item
            nxt = (data.get("_links") or {}).get("next")
            if not nxt:
                return
            data = await self.get_json(nxt)

    async def download(self, url: str, dest: Path) -> int:
        """Stream url to dest atomically (via a .part file), verifying the byte count
        against Content-Length. Returns bytes written."""
        url = absolute(url)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        last: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                async with self._sem:
                    async with self._client.stream("GET", url) as resp:
                        if resp.status_code in (404, 410):
                            raise NotFound(f"HTTP {resp.status_code} for {url}")
                        if resp.status_code in RETRY_STATUSES:
                            last = HttpError(resp.status_code, url)
                            retry_after = resp.headers.get("Retry-After")
                        elif resp.status_code >= 400:
                            raise HttpError(resp.status_code, url)
                        else:
                            retry_after = None
                            ctype = resp.headers.get("Content-Type", "")
                            final = str(resp.url)
                            if "login.action" in final or "os_destination" in final or (
                                    ctype.startswith("text/html")
                                    and dest.suffix.lower() not in (".html", ".htm")):
                                raise HttpError(403, f"{url} (site served a login/HTML page, not the file)")
                            declared = resp.headers.get("Content-Length")
                            written = 0
                            with open(part, "wb") as fh:
                                async for chunk in resp.aiter_bytes(256 * 1024):
                                    fh.write(chunk)
                                    written += len(chunk)
                            # Integrity is checked against Content-Length. The attachment
                            # metadata's fileSize is NOT used: on this site it is often
                            # stale (the served file is consistently a different size).
                            if declared and resp.headers.get("Content-Encoding") in (None, "identity") \
                                    and int(declared) != written:
                                raise IncompleteDownload(f"got {written} of {declared} bytes")
                            if written == 0:
                                raise IncompleteDownload("empty file")
                            os.replace(part, dest)
                            return written
                self._log("warning", f"Download {last}, retry {attempt}/{self._retries}")
                await self._backoff(attempt, retry_after)
            except (httpx.TransportError, IncompleteDownload) as exc:
                last = exc
                self._log("warning", f"Download {type(exc).__name__} ({exc}), retry {attempt}/{self._retries}: {dest.name}")
                await self._backoff(attempt)
            finally:
                if part.exists():
                    try:
                        part.unlink()
                    except OSError:
                        pass
        raise last or HttpError(0, url)
