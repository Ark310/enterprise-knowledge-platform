"""Scrape one docs page end-to-end: Theneo .md export + browser capture of the
endpoint block + the API Explorer (capture only) → files on disk → verification.

Returns the result dict the engine journals: status "done" (complete) or "warning"
(saved, every gap listed in `issues`). Raises only when nothing usable was saved, so
the engine can retry; Blocked propagates so the engine can cool down instead.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from kbscraper.paths import safe_filename, unique_filename
from restscraper import guard, theneo
from restscraper.browser import capture_block, capture_tryit
from restscraper.http import Blocked, NotFound
from restscraper.render import LANG_FILES, html_to_md, page_markdown
from restscraper.settings import LANGUAGES

DONE, WARNING = "done", "warning"


def _write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def _json(path: Path, obj) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _status_file(status: str, text: str) -> str:
    name = safe_filename(re.sub(r"\s+", "_", status) or "response")
    try:
        json.loads(text)
        return f"{name}.json"
    except ValueError:
        return f"{name}.txt"


def verify(expected: dict, found: dict, *, screenshots: bool) -> tuple[list[str], list[str]]:
    """Compare what the page's own data says exists with what was captured."""
    issues: list[str] = []
    notes: list[str] = []
    for hit in found.get("api_hits") or []:
        issues.append(f"SAFETY: a request to an API host was attempted and blocked: {hit}")
    if found.get("endpoint"):
        if not found.get("rendered"):
            issues.append("The endpoint block never finished rendering in the browser")
        missing = [label for label, _k, _e in LANGUAGES if not (found.get("snippets") or {}).get(label)]
        if missing:
            issues.append(f"Missing code snippet(s): {', '.join(missing)}")
        if found.get("responses", 0) < expected.get("responses", 0):
            issues.append(f"Captured {found.get('responses', 0)} of {expected['responses']} response example(s)")
        if found.get("tryit_unavailable"):
            notes.append("The site's API Explorer does not offer this endpoint (no path in the docs)")
        elif not found.get("tryit"):
            issues.append("The Try-it (API Explorer) page was not captured")
        else:
            if found.get("tryit_header_fields", 0) < expected.get("header", 0):
                issues.append(f"Try-it shows {found.get('tryit_header_fields', 0)} of "
                              f"{expected['header']} header field(s)")
            if expected.get("body") and not found.get("tryit_body"):
                issues.append("Try-it request body (Code view) was not captured")
            if found.get("tryit_snippets", 0) < len(LANGUAGES):
                notes.append(f"Try-it snippets: {found.get('tryit_snippets', 0)} of {len(LANGUAGES)} languages")
    if found.get("images_saved", 0) < found.get("images_found", 0):
        issues.append(f"Downloaded {found.get('images_saved', 0)} of {found['images_found']} image(s)")
    if found.get("images_found", 0) < expected.get("images", 0):
        issues.append(f"The page shows {found.get('images_found', 0)} of {expected['images']} image(s) in its data")
    if screenshots and not found.get("screenshots"):
        issues.append("No screenshot was saved")
    return issues, notes


async def _download_images(client, srcs: list[str], folder: Path, log) -> tuple[list[dict], list[str]]:
    taken: set[str] = set()
    media, problems = [], []
    for n, src in enumerate(dict.fromkeys(srcs), start=1):
        base = unquote(urlsplit(src).path.rsplit("/", 1)[-1]) or f"image{n}"
        if guard.classify("GET", src) != "allow":
            # Downloads must obey the same allowlist as the browser.
            media.append({"src": src, "local_path": "", "downloaded": False,
                          "error": "not downloaded: host is outside the safety allowlist"})
            problems.append(f"{base}: host is outside the safety allowlist")
            continue
        if "." not in base:
            base += ".png"
        local = unique_filename(safe_filename(base), taken, str(n))
        entry = {"src": src, "local_path": f"images/{local}", "downloaded": False}
        try:
            data, ctype = await client.get_bytes(src)
            _write(folder / "images" / local, data)
            entry.update(downloaded=True, bytes=len(data), content_type=ctype)
        except Blocked:
            raise
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            problems.append(f"{base}: {entry['error']}")
        media.append(entry)
    return media, problems


async def scrape_page(rec: dict, client, pool, output_dir: Path, settings, log=None) -> dict:
    log = log or (lambda level, msg: None)
    folder = Path(output_dir) / rec["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    source_md = ""
    try:
        source_md = await client.get_text(f"/{rec['slug']}.md")
    except NotFound:
        notes.append("Theneo has no Markdown export for this page")

    async with pool.slot() as slot:
        blk = await capture_block(pool, slot, rec["url"], rec["page_id"], folder,
                                  screenshots=settings.screenshots, log=log)
        tryit = None
        if blk["endpoint"]:
            try:
                tryit = await capture_tryit(pool, slot, rec["slug"], folder / "tryit",
                                            screenshots=settings.screenshots, log=log)
            except Blocked:
                raise
            except Exception as exc:
                log("warning", f"Try-it capture failed for {rec['title']}: {type(exc).__name__}: {exc}")
        blocked = list(slot.blocked)

    entry = blk["entry"]
    if entry is None:
        raise RuntimeError("the page data does not contain this section (it may have been removed)")
    info = theneo.endpoint_info(entry) if blk["endpoint"] else None
    expected = theneo.expected_counts(entry)
    images, img_problems = await _download_images(client, blk["images"], folder, log)

    # ── files ────────────────────────────────────────────────────────────────
    snippets = []
    for label, _key, _ext in LANGUAGES:
        code = blk["snippets"].get(label)
        if code:
            rel = f"snippets/{LANG_FILES[label]}"
            _write(folder / rel, code)
            snippets.append({"language": label, "file": rel, "code": code})
    responses_files = {}
    for status, text in blk["responses"].items():
        rel = f"responses/{_status_file(status, text)}"
        _write(folder / rel, text)
        responses_files[status] = rel
    if tryit:
        for label, code in tryit["snippets"].items():
            if label in LANG_FILES:
                _write(folder / "tryit" / "snippets" / LANG_FILES[label], code)
        if tryit.get("body_code"):
            _write(folder / "tryit" / "request_body.json", tryit["body_code"])
        tryit["title"] = rec["title"]
        if info:
            info["request_url"] = tryit.get("request_url", "")
        _json(folder / "tryit" / "tryit.json", {k: v for k, v in tryit.items()})
    if source_md:
        _write(folder / "source.md", source_md)
    _write(folder / "page.html", blk["html"])

    description_md = html_to_md(entry.get("description") or "")
    api_hits = [f"{b['method']} {b['url']}" for b in blocked if b["kind"] == "api"]
    found = {"endpoint": blk["endpoint"], "rendered": blk["rendered"], "snippets": blk["snippets"],
             "responses": len(blk["responses"]), "tryit": bool(tryit),
             "tryit_unavailable": bool((tryit or {}).get("unavailable")),
             "tryit_header_fields": sum(1 for f in (tryit or {}).get("fields", [])
                                        if "header" in (f.get("group") or "").lower()),
             "tryit_body": bool((tryit or {}).get("body_code")),
             "tryit_snippets": len((tryit or {}).get("snippets", {})),
             "images_found": len(set(blk["images"])), "images_saved": sum(1 for i in images if i["downloaded"]),
             "screenshots": len(blk["screenshots"]) + len((tryit or {}).get("screenshots", [])),
             "api_hits": api_hits}
    issues, more_notes = verify(expected, found, screenshots=settings.screenshots)
    issues += [f"Image download failed — {p}" for p in img_problems]
    notes += more_notes
    other_blocked = len(blocked) - len(api_hits)
    if other_blocked:
        notes.append(f"{other_blocked} non-docs request(s) blocked by the safety guard (analytics etc.)")

    doc = {
        "page_id": rec["page_id"], "slug": rec["slug"], "kind": "endpoint" if blk["endpoint"] else rec["kind"],
        "title": rec["title"], "url": rec["url"], "section": rec.get("space_name", ""),
        "breadcrumb": [rec.get("space_name", "")] + ([rec["title"]] if rec["kind"] != "section" else []),
        "updated_at": entry.get("updatedAt", ""), "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "endpoint": info,
        "content": {"description_html": entry.get("description") or "", "markdown": description_md,
                    "text": blk["text"], "tables": blk["tables"]},
        "snippets": snippets,
        "responses_rendered": blk["responses"], "responses_files": responses_files,
        "tryit": tryit, "media": {"images": images, "screenshots": blk["screenshots"]},
        "raw": entry,
        "verification": {"expected": expected, "found": {k: (len(v) if isinstance(v, dict) else v)
                                                         for k, v in found.items()},
                         "issues": issues, "notes": notes, "blocked_requests": blocked},
    }
    _write(folder / "page.md", page_markdown(doc))
    _json(folder / "page.json", doc)
    if rec["kind"] == "section":
        _json(folder / "_section.json", {"key": rec.get("space_key"), "name": rec["title"],
                                         "url": rec["url"], "description_markdown": description_md})

    files = (len(snippets) + len(responses_files) + sum(1 for i in images if i["downloaded"])
             + (1 if source_md else 0) + 3 + found["screenshots"])
    return {"status": WARNING if issues else DONE, "issues": issues, "notes": notes,
            "found": doc["verification"]["found"], "expected": expected,
            "files": files, "files_expected": files + len(img_problems),
            "screenshots": found["screenshots"]}
