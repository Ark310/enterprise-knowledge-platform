"""Chrome capture of one docs page: the endpoint's own block (snippets in every language,
fully expanded responses, screenshot) and its API Explorer page (capture only).

One Chrome instance per worker (several tabs in one Chrome stall each other's
screenshots, as the KB scraper found). Every context is wrapped by guard.install,
so no request can reach an API host whatever the page does. The explorer is
opened by URL and only its language dropdown and Code view tab are ever clicked.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

from playwright.async_api import async_playwright

from restscraper import guard, theneo
from restscraper.http import Blocked, Throttle
from restscraper.settings import BASE_URL, LANGUAGES, RUNNER_PREFIX

NAV_TIMEOUT_MS = 60_000
PART_HEIGHT = 12_000
SHOT_TIMEOUT_MS = 30_000
BLOCK_SEL = 'section.th-content_section-item:has([id="{sid}"])'
DROPDOWN_SEL = ".request-widget-language-switcher-dropdown"

# Code text without the line-number gutter of react-syntax-highlighter.
_CODE_JS = """el => { if (!el) return null; const c = el.cloneNode(true);
  c.querySelectorAll('.linenumber, .react-syntax-highlighter-line-number').forEach(n => n.remove());
  return c.textContent; }"""

_SELECTED_LANG_JS = """el => { const v = el.querySelector('[title]'); return v ? v.getAttribute('title') : el.innerText.trim(); }"""

_BLOCK_INFO_JS = """b => ({
  html: b.outerHTML,
  text: b.innerText,
  images: [...b.querySelectorAll('img')].map(i => i.currentSrc || i.src).filter(s => s && !s.startsWith('data:')),
  tables: b.querySelectorAll('table').length,
})"""

_TRYIT_JS = """() => {
  const heads = [...document.querySelectorAll('h4')];
  const groupOf = el => { let g = ''; for (const h of heads)
      if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) g = h.innerText.trim();
    return g; };
  const fields = [...document.querySelectorAll('[data-testid^="api-runner-input-"]')].map(e => {
    const item = e.closest('[class*=ApiRunner_input_item]') && e.closest('[class*=ApiRunner_inner]');
    const label = item ? (item.innerText || '').trim() : '';
    return {group: groupOf(e), name: e.dataset.testid.replace('api-runner-input-', ''),
            value: e.value, placeholder: e.placeholder || '', label: label.slice(0, 200)};
  });
  const sections = heads.map(h => ({title: h.innerText.trim(),
                                    text: (h.parentElement ? h.parentElement.innerText : '').trim()}));
  const ep = document.querySelector('[class*=ApiRunner_editor_endpoint_header]') ||
             document.querySelector('.th-snippet-box__header');
  return {fields, sections, endpoint: ep ? ep.innerText.trim() : ''};
}"""

_UNSTICK_JS = """() => { for (const e of document.querySelectorAll('body *')) {
  const p = getComputedStyle(e).position;
  if (p === 'sticky') e.style.setProperty('position', 'static', 'important');
  else if (p === 'fixed') e.style.setProperty('visibility', 'hidden', 'important');
} }"""

_MONACO_JS = """() => window.monaco ? window.monaco.editor.getModels().map(m => m.getValue()) : null"""


def _is_403(resp, title: str) -> bool:
    return (resp is not None and resp.status == 403) or title.strip() == "403 Forbidden"


class _Slot:
    def __init__(self, idx: int):
        self.idx = idx
        self.browser = None
        self.context = None
        self.blocked: list[dict] = []
        self.dirty = False      # a capture was cancelled mid-way: relaunch before reuse

    def alive(self) -> bool:
        return bool(self.browser and self.browser.is_connected())


class BrowserPool:
    def __init__(self, size: int, headless: bool, throttle: Throttle, log=None):
        self.size = max(1, size)
        self.headless = headless
        self.throttle = throttle
        self._log = log or (lambda level, msg: None)
        self._pw = None
        self._slots: list[_Slot] = []
        self._pool: asyncio.Queue[_Slot] = asyncio.Queue()
        self._channel: str | None = None
        self.cache = guard.AssetCache()

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        for i in range(self.size):
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
                probe = await slot.browser.new_page()
                ua = (await probe.evaluate("navigator.userAgent")).replace("HeadlessChrome", "Chrome")
                await probe.close()
                # The site answers 403 to a "HeadlessChrome" user agent.
                slot.context = await slot.browser.new_context(
                    viewport={"width": 1600, "height": 1000}, user_agent=ua, ignore_https_errors=True,
                    # Service-worker requests bypass context.route(), so no service workers.
                    service_workers="block")
                slot.context.set_default_timeout(NAV_TIMEOUT_MS)
                await guard.install(slot.context, slot.blocked, self.cache)
                self._channel = channel
                return
            except Exception as exc:
                last = exc
        raise RuntimeError(f"Could not launch Chrome/Edge: {last}")

    async def close(self) -> None:
        for slot in self._slots:
            with contextlib.suppress(Exception):
                if slot.browser:
                    await slot.browser.close()
        with contextlib.suppress(Exception):
            if self._pw:
                await self._pw.stop()

    @contextlib.asynccontextmanager
    async def slot(self):
        slot = await self._pool.get()
        try:
            if not slot.alive() or slot.dirty:
                self._log("warning", f"Browser #{slot.idx + 1} restarting "
                                     f"({'after a timeout' if slot.dirty else 'not running'})")
                with contextlib.suppress(Exception):
                    await slot.browser.close()
                await self._launch(slot)
                slot.dirty = False
            slot.blocked.clear()
            yield slot
        except Exception as exc:
            if not slot.alive() or "Timeout" in type(exc).__name__:
                with contextlib.suppress(Exception):
                    await slot.browser.close()
                with contextlib.suppress(Exception):
                    await self._launch(slot)
            raise
        except BaseException:
            # Cancelled (page timeout / Stop): the browser may be hung; relaunch on next use.
            slot.dirty = True
            raise
        finally:
            self._pool.put_nowait(slot)

    async def open(self, slot: _Slot, url: str):
        await self.throttle.wait()
        page = await slot.context.new_page()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=20_000)
            if _is_403(resp, await page.title()):
                raise Blocked(f"HTTP 403 in the browser for {url}")
            if resp is not None and resp.status == 404:
                raise FileNotFoundError(url)
            return page
        except BaseException:
            with contextlib.suppress(Exception):
                await page.close()
            raise


async def _click_all(scope, selector_text: str, rounds: int = 4) -> int:
    """Click every button whose text is exactly selector_text, until none are left."""
    n = 0
    for _ in range(rounds):
        btns = scope.locator("button").filter(has_text=selector_text)
        count = await btns.count()
        clicked = 0
        for i in range(count):
            b = btns.nth(i)
            with contextlib.suppress(Exception):
                if (await b.inner_text()).strip() == selector_text and await b.is_visible():
                    await b.click(timeout=3000)
                    clicked += 1
        n += clicked
        if not clicked:
            break
        await asyncio.sleep(0.25)
    return n


async def _read_snippets(page, scope, log, where: str) -> dict[str, str]:
    """Pick each language in scope's snippet dropdown and read the code."""
    out: dict[str, str] = {}
    dd = scope.locator(DROPDOWN_SEL).first
    if not await dd.count():
        return out
    card = scope.locator(f"{DROPDOWN_SEL} >> xpath=ancestor::*[.//code][1]").first
    previous = None
    for label, _key, _ext in LANGUAGES:
        try:
            await dd.click(timeout=5000)
            opt = scope.locator("li").filter(has_text=label)
            picked = False
            for i in range(await opt.count()):
                o = opt.nth(i)
                if (await o.inner_text()).strip() == label and await o.is_visible():
                    await o.click(timeout=3000)
                    picked = True
                    break
            if not picked:
                await page.keyboard.press("Escape")
                log("warning", f"{where}: language '{label}' not offered")
                continue
            code = None
            for _ in range(30):          # wait until the snippet re-renders
                await asyncio.sleep(0.15)
                shown = await dd.evaluate(_SELECTED_LANG_JS)
                code = await card.locator("code").first.evaluate(_CODE_JS)
                if shown == label and code and code != previous:
                    out[label] = code
                    previous = code
                    break
            else:
                # Never switched: keeping the old text would save one language's code
                # under another's name; leave it missing so verification flags it.
                log("warning", f"{where}: the {label} snippet did not appear")
        except Exception as exc:
            log("warning", f"{where}: could not read the {label} snippet ({type(exc).__name__})")
    return out


async def _shoot(page, folder: Path, name: str, clip_el=None) -> list[str]:
    """Screenshot the page (or just clip_el), split into parts when very tall."""
    folder.mkdir(parents=True, exist_ok=True)
    # Sticky columns go back into flow and fixed bars (site header, AI button) are hidden;
    # otherwise a tall capture paints them mid-image.
    await page.evaluate(_UNSTICK_JS)
    if clip_el is not None:
        await clip_el.scroll_into_view_if_needed()
        box = await clip_el.evaluate(
            "e => { const r = e.getBoundingClientRect(); return {x: r.left + scrollX, y: r.top + scrollY,"
            " width: r.width, height: r.height}; }")
    else:
        box = await page.evaluate("() => ({x: 0, y: 0, width: document.documentElement.scrollWidth,"
                                  " height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)})")
    if box["height"] <= 0 or box["width"] <= 0:
        return []
    names = []
    parts = 1 if box["height"] <= PART_HEIGHT * 1.25 else -(-int(box["height"]) // PART_HEIGHT)
    for part in range(parts):
        y = box["y"] + part * PART_HEIGHT
        h = box["height"] - part * PART_HEIGHT if parts > 1 else box["height"]
        h = min(h, PART_HEIGHT) if parts > 1 else h
        fname = f"{name}.png" if parts == 1 else f"{name}_part{part + 1:02d}.png"
        tmp = folder / (fname + ".part")
        await page.screenshot(path=str(tmp), full_page=True, type="png", timeout=SHOT_TIMEOUT_MS,
                              clip={"x": box["x"], "y": y, "width": box["width"], "height": h})
        tmp.replace(folder / fname)
        names.append(fname)
    return names


async def capture_block(pool: BrowserPool, slot: _Slot, url: str, section_id: str, folder: Path,
                        *, screenshots: bool, log) -> dict:
    """Capture the block of section_id on url. Whether it is an endpoint (snippets,
    responses) is read from the page's own data, not assumed from the menu."""
    page = await pool.open(slot, url)
    where = url.rsplit("/", 1)[-1]
    try:
        raw = await page.evaluate("() => (document.getElementById('__NEXT_DATA__') || {}).textContent || ''")
        next_props = json.loads(raw)["props"]["pageProps"] if raw else None
        entry = theneo.section_entry(next_props, section_id) if next_props else None
        endpoint = theneo.is_endpoint(entry)
        block = page.locator(BLOCK_SEL.format(sid=section_id)).first
        await block.wait_for(state="attached", timeout=20_000)
        await block.scroll_into_view_if_needed()
        rendered = True
        if endpoint:
            try:
                await block.locator(".th-snippet-box__header").first.wait_for(timeout=20_000)
            except Exception:
                rendered = False
        await asyncio.sleep(0.5)
        expanded = await _click_all(block, "Expand all")
        await _click_all(block, "Show more")
        snippets = await _read_snippets(page, block, log, where) if endpoint and rendered else {}
        responses: dict[str, str] = {}
        previous_code = None
        tabs = block.locator('[role="tab"]')
        n_tabs = await tabs.count()
        # Tab captions are truncated ("200 (Statu..."), so two tabs can look alike; name
        # them by the documented status codes, which are listed in the same order.
        statuses = [str(r.get("statusCode")) for r in (entry or {}).get("responses") or []]
        for i in range(n_tabs):
            tab = tabs.nth(i)
            label = statuses[i] if len(statuses) == n_tabs else (await tab.inner_text()).strip()
            if label in responses:
                label = f"{label} ({i + 1})"
            with contextlib.suppress(Exception):
                await tab.click(timeout=3000)
                await asyncio.sleep(0.25)
                await _click_all(block, "Show more")
                code = None
                for _ in range(10):      # wait until the panel shows this tab's example
                    code = await block.locator("pre.response-code-block").first.evaluate(_CODE_JS)
                    if code is not None and (i == 0 or code != previous_code):
                        break
                    await asyncio.sleep(0.2)
                if code is not None and (i == 0 or code != previous_code):
                    responses[label] = code
                    previous_code = code
                else:
                    log("warning", f"{where}: response tab {label} did not show its own example")
        info = await block.evaluate(_BLOCK_INFO_JS)
        shots = await _shoot(page, folder, "screenshot", block) if screenshots else []
        return {"next_props": next_props, "entry": entry, "endpoint": endpoint, "rendered": rendered, "expanded": expanded,
                "snippets": snippets, "responses": responses, "screenshots": shots, **info}
    finally:
        with contextlib.suppress(Exception):
            await page.close()


async def capture_tryit(pool: BrowserPool, slot: _Slot, slug: str, folder: Path,
                        *, screenshots: bool, log) -> dict:
    url = f"{BASE_URL}{RUNNER_PREFIX}{slug}"
    page = await pool.open(slot, url)
    where = f"Try-it {slug.rsplit('/', 1)[-1]}"
    try:
        with contextlib.suppress(Exception):
            await page.locator(DROPDOWN_SEL).first.wait_for(timeout=20_000)
        await asyncio.sleep(0.5)
        form = await page.evaluate(_TRYIT_JS)
        landing = await page.evaluate(
            "() => document.body.innerText.includes('Select a section and subsection to get started')")
        if landing and not form["fields"]:
            # The site's explorer cannot open this endpoint (it has no path in the docs)
            # and shows its generic landing page instead; record that, with a screenshot.
            shots = await _shoot(page, folder, "tryit") if screenshots else []
            return {"url": url, "unavailable": "The site's API Explorer does not open this endpoint "
                                               "(it has no path configured in the documentation); "
                                               "it shows its generic landing page instead.",
                    "endpoint": form["endpoint"], "request_url": "", "fields": [], "sections": [],
                    "body_code": "", "snippets": {}, "screenshots": shots}
        snippets = await _read_snippets(page, page.locator("body"), log, where)
        shots = await _shoot(page, folder, "tryit") if screenshots else []
        body_code = ""
        code_tab = page.locator('[role="tab"]').filter(has_text="Code view")
        if await code_tab.count():
            await code_tab.first.click(timeout=5000)
            for i in range(60):          # the editor loads lazily; give it up to ~18s
                await asyncio.sleep(0.3)
                if i == 25:              # still empty: switch away and back once
                    with contextlib.suppress(Exception):
                        await page.locator('[role="tab"]').filter(has_text="Form view").first.click(timeout=3000)
                        await asyncio.sleep(0.3)
                        await code_tab.first.click(timeout=3000)
                models = await page.evaluate(_MONACO_JS)
                if models and any(m.strip() for m in models):
                    body_code = next(m for m in models if m.strip())
                    break
            if screenshots:
                shots += await _shoot(page, folder, "tryit_code")
        base_url = ""
        first = next(iter(snippets.values()), "")
        for token in first.replace("'", " ").replace('"', " ").split():
            if token.startswith("http"):
                base_url = token
                break
        return {"url": url, "endpoint": form["endpoint"],
                "request_url": base_url, "fields": form["fields"], "sections": form["sections"],
                "body_code": body_code, "snippets": snippets, "screenshots": shots}
    finally:
        with contextlib.suppress(Exception):
            await page.close()
