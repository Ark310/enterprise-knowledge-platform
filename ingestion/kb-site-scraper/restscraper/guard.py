"""Request allowlist for every browser context: the scraper must never reach an API.

Only GET requests to the docs site and the static hosts its pages need are let
through; everything else is aborted. Requests aimed at a Contoso API host are
classified "api" so the page that triggered them is flagged, not just logged.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

DOCS_HOST = "apidocs.contoso.example"
_ASSET_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}
_S3_HOST = re.compile(r"^theneo-prod-public\.s3(\.[a-z0-9-]+)?\.amazonaws\.com$")
# Anything that looks like the explorer's request runner or a proxy on the docs host.
_RUNNER_PATH = re.compile(r"^/api/|/proxy|/run(ner)?(/|$)", re.I)


def _is_api_host(host: str) -> bool:
    return host != DOCS_HOST and ("contoso" in host)


def classify(method: str, url: str) -> str:
    """'allow', 'block', or 'api' (a blocked request that targeted a Contoso API)."""
    if url.startswith(("data:", "blob:")):
        return "allow"
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if _is_api_host(host):
        return "api"
    if method.upper() != "GET":
        return "block"
    if host == DOCS_HOST:
        return "block" if _RUNNER_PATH.search(parts.path) and not parts.path.startswith("/api-runner/") \
            else "allow"
    if host in _ASSET_HOSTS or _S3_HOST.match(host):
        return "allow"
    # The explorer's Code view editor (a static library, nothing else from this CDN).
    if host == "cdn.jsdelivr.net" and parts.path.startswith("/npm/monaco-editor@"):
        return "allow"
    return "block"


_STATIC_EXT = re.compile(r"\.(js|css|woff2?|ttf|otf|png|jpe?g|gif|svg|ico|webp)$", re.I)


def cacheable(url: str) -> bool:
    """Static, versioned assets that can be served from memory after the first load."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host == DOCS_HOST:
        return parts.path.startswith("/_next/static/") or bool(_STATIC_EXT.search(parts.path))
    return classify("GET", url) == "allow" and not url.startswith(("data:", "blob:"))


class AssetCache:
    """Shared by every browser of a run. Playwright turns the browser's HTTP cache off
    once a context is routed, so without this every page would re-download ~100
    script files — enough to trip the site's per-IP rate limit within a few pages."""

    def __init__(self, max_bytes: int = 300_000_000):
        self.max_bytes = max_bytes
        self.size = 0
        self.hits = 0
        self._items: dict[str, tuple[int, dict, bytes]] = {}

    def get(self, url: str):
        item = self._items.get(url)
        if item is not None:
            self.hits += 1
        return item

    def put(self, url: str, status: int, headers: dict, body: bytes) -> None:
        if status != 200 or self.size + len(body) > self.max_bytes:
            return
        keep = {k: v for k, v in headers.items()
                if k.lower() in ("content-type", "cache-control", "access-control-allow-origin")}
        self._items[url] = (status, keep, body)
        self.size += len(body)


async def install(context, sink: list, cache: AssetCache | None = None) -> None:
    """Route every request of a Playwright context through classify(). Blocked
    requests are appended to sink as {"kind", "method", "url"}; allowed static assets
    are served from `cache` after their first download."""
    async def handler(route):
        req = route.request
        verdict = classify(req.method, req.url)
        if verdict != "allow":
            sink.append({"kind": verdict, "method": req.method, "url": req.url.split("?")[0][:300]})
            await route.abort()
            return
        use_cache = cache is not None and cacheable(req.url)
        if use_cache:
            hit = cache.get(req.url)
            if hit is not None:
                status, headers, body = hit
                await route.fulfill(status=status, headers=headers, body=body)
                return
        # Fetch ourselves with redirects OFF: a redirect is handed back to the browser,
        # whose follow-up request comes through this handler (and classify) again.
        # route.continue_() would let the browser follow redirects unchecked.
        try:
            resp = await route.fetch(max_redirects=0)
        except Exception:
            await route.abort()
            return
        location = resp.headers.get("location")
        if 300 <= resp.status < 400 and location:
            target = urljoin(req.url, location)
            if classify("GET", target) != "allow":
                sink.append({"kind": classify("GET", target), "method": "REDIRECT",
                             "url": target.split("?")[0][:300]})
                await route.abort()
                return
        body = await resp.body()
        if use_cache:
            cache.put(req.url, resp.status, resp.headers, body)
        await route.fulfill(response=resp, body=body)

    async def ws_handler(ws):
        sink.append({"kind": classify("GET", ws.url.replace("ws", "http", 1)),
                     "method": "WEBSOCKET", "url": ws.url.split("?")[0][:300]})
        await ws.close()

    await context.route("**/*", handler)
    # WebSockets are not covered by route(); refuse every one.
    await context.route_web_socket("**/*", ws_handler)
