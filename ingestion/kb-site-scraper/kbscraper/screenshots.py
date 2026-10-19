"""Full-page article screenshots with every dropdown (expand macro) opened.

A small pool of Chrome instances, one capture per instance at a time; a crashed
or hung instance is relaunched. Very tall pages are split into several images because Chrome cannot
render a single bitmap much taller than ~16k px.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

PART_HEIGHT = 12_000
NAV_TIMEOUT_MS = 60_000
SHOT_TIMEOUT_MS = 30_000

# Open every expand macro by its own state (no click toggling — clicking a control
# that is already open would close it again), plus any <details>.
_EXPAND_ALL_JS = """
() => {
  let n = 0;
  document.querySelectorAll('.expand-content').forEach(el => {
    el.classList.remove('expand-hidden');
    el.style.display = 'block'; el.style.opacity = '1'; el.style.height = 'auto';
    n++;
  });
  document.querySelectorAll('.expand-container .expand-icon').forEach(el => {
    el.classList.remove('aui-iconfont-chevron-right');
    el.classList.add('aui-iconfont-chevron-down');
  });
  document.querySelectorAll('details').forEach(d => d.open = true);
  return n;
}
"""

_WAIT_IMAGES_JS = """
async () => {
  const imgs = Array.from(document.images);
  imgs.forEach(i => { i.loading = 'eager'; });
  await Promise.all(imgs.map(i => i.complete ? null :
    new Promise(r => { i.addEventListener('load', r, {once:true});
                       i.addEventListener('error', r, {once:true}); })));
  return imgs.filter(i => i.complete && i.naturalWidth === 0).length;
}
"""


class _Slot:
    """One dedicated Chrome instance; used by one capture at a time."""
    def __init__(self, idx: int):
        self.idx = idx
        self.browser = None
        self.context = None

    def alive(self) -> bool:
        return bool(self.browser and self.browser.is_connected())


class ScreenshotService:
    """A pool of independent Chrome instances (one per worker). Several tabs sharing
    one Chrome stall each other's full-page screenshots (60s Page.screenshot
    timeouts on pages that capture in 0.2s alone), so every capture gets a browser
    to itself. A browser that crashes or wedges is relaunched in place."""

    def __init__(self, headless: bool = True, log=None, size: int = 1):
        self.headless = headless
        self._log = log or (lambda level, msg: None)
        self._size = max(1, size)
        self._pw = None
        self._slots: list[_Slot] = []
        self._pool: asyncio.Queue[_Slot] = asyncio.Queue()
        self._channel: str | None = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        for i in range(self._size):
            slot = _Slot(i)
            await self._launch(slot)
            self._slots.append(slot)
            self._pool.put_nowait(slot)

    async def _launch(self, slot: _Slot) -> None:
        last: Exception | None = None
        channels = [self._channel] if self._channel is not None else ["chrome", "msedge", ""]
        for channel in channels:
            try:
                kwargs = {"headless": self.headless}
                if channel:
                    kwargs["channel"] = channel
                slot.browser = await self._pw.chromium.launch(**kwargs)
                slot.context = await slot.browser.new_context(
                    viewport={"width": 1366, "height": 900}, ignore_https_errors=True)
                slot.context.set_default_timeout(NAV_TIMEOUT_MS)
                # Don't stream videos into the screenshot browser: a loading <video>
                # stalls headless screenshots, and the MP4 is downloaded separately.
                await slot.context.route(
                    "**/*.{mp4,webm,mov,m4v,avi,wmv,mkv,mp3,wav}", lambda route: route.abort())
                self._channel = channel
                return
            except Exception as exc:
                last = exc
        raise RuntimeError(f"Could not launch Chrome/Edge for screenshots: {last}")

    async def _relaunch(self, slot: _Slot, reason: str) -> None:
        self._log("warning", f"Screenshot browser #{slot.idx + 1} restarting ({reason})")
        try:
            if slot.browser:
                await slot.browser.close()
        except Exception:
            pass
        await self._launch(slot)

    async def close(self) -> None:
        for slot in self._slots:
            try:
                if slot.browser:
                    await slot.browser.close()
            except Exception:
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    async def capture(self, url: str, folder: Path) -> list[str]:
        """Screenshot url into folder; returns the file names written. On a crash or
        a hang the browser is relaunched and the capture tried once more."""
        slot = await self._pool.get()
        try:
            try:
                if not slot.alive():
                    await self._relaunch(slot, "not running")
                return await self._capture_once(slot, url, Path(folder))
            except Exception as exc:
                if not slot.alive() or "Timeout" in type(exc).__name__:
                    await self._relaunch(slot, type(exc).__name__)
                    return await self._capture_once(slot, url, Path(folder))
                raise
        finally:
            self._pool.put_nowait(slot)

    async def _capture_once(self, slot: _Slot, url: str, folder: Path) -> list[str]:
        page = await slot.context.new_page()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"page returned HTTP {resp.status}")
            try:
                await page.wait_for_load_state("load", timeout=20_000)
            except Exception:
                pass    # background polling can delay 'load'; content is already there
            await page.evaluate(_EXPAND_ALL_JS)
            # Scroll through once so lazy content renders, then wait for images.
            await page.evaluate("""async () => {
                for (let y = 0; y < document.body.scrollHeight; y += 800) {
                  window.scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); }
                window.scrollTo(0, 0); }""")
            try:
                broken = await asyncio.wait_for(page.evaluate(_WAIT_IMAGES_JS), timeout=30)
                if broken:
                    self._log("warning", f"{broken} image(s) did not render in the screenshot of {url}")
            except asyncio.TimeoutError:
                self._log("warning", f"Images still loading when the screenshot was taken: {url}")
            await page.wait_for_timeout(300)
            height = await page.evaluate(
                "() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            width = await page.evaluate("() => document.documentElement.scrollWidth")
            folder.mkdir(parents=True, exist_ok=True)
            return await self._shoot(page, folder, height, width)
        finally:
            try:
                await page.close()
            except Exception:
                pass

    @staticmethod
    async def _shoot(page, folder: Path, height: int, width: int) -> list[str]:
        if height <= PART_HEIGHT * 1.25:
            tmp = folder / "screenshot.png.part"
            await page.screenshot(path=str(tmp), full_page=True, type="png",
                                  timeout=SHOT_TIMEOUT_MS)
            tmp.replace(folder / "screenshot.png")
            return ["screenshot.png"]
        names: list[str] = []
        part, y = 1, 0
        while y < height:
            h = min(PART_HEIGHT, height - y)
            name = f"screenshot_part{part:02d}.png"
            tmp = folder / (name + ".part")
            await page.screenshot(path=str(tmp), full_page=True, type="png",
                                  clip={"x": 0, "y": y, "width": width, "height": h},
                                  timeout=SHOT_TIMEOUT_MS)
            tmp.replace(folder / name)
            names.append(name)
            y += h
            part += 1
        return names
