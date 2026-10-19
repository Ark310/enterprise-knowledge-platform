"""Scrape one article end-to-end: fetch → parse → download media/files → screenshot →
write article.json + article.md → verify against the page source.

Returns a result with status "done" (complete) or "warning" (saved, but something is
missing — every gap is listed in `issues`). Raises only when nothing usable could be
saved (e.g. the page API itself failed), so the engine can retry the article.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path

from kbscraper.confluence import ConfluenceClient
from kbscraper.parser import parse_body, storage_counts, youtube_watch_url
from kbscraper.paths import safe_filename, unique_filename
from urllib.parse import unquote
from html import unescape

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "tif", "tiff", "ico"}
CONTENT_EXPAND = "body.view,body.storage,version,ancestors,space,metadata.labels,history.lastUpdated"
_PLACEHOLDER = re.compile(r"\{\{res:(\d+)\}\}")
# <ri:attachment ri:filename="x"/> with no nested <ri:page> = an attachment of this page.
_OWN_ATTACHMENT_REF = re.compile(r'<ri:attachment\s+ri:filename="([^"]+)"\s*/>')


def _is_image(filename: str, media_type: str = "") -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return media_type.startswith("image/") or ext in IMAGE_EXTS


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _md_link_path(rel: str) -> str:
    return f"<{rel}>" if re.search(r"[\s()<>]", rel) else rel


async def scrape_article(client: ConfluenceClient, rec: dict, output_dir: Path, *,
                         screenshots=None, screenshots_expected: bool = False, log=None) -> dict:
    log = log or (lambda level, msg: None)
    pid = rec["page_id"]
    folder = Path(output_dir) / rec["folder"]
    issues: list[str] = []
    notes: list[str] = []      # informational; does not make the article a warning

    data = await client.get_json(f"/rest/api/content/{pid}", {"expand": CONTENT_EXPAND})
    body = (data.get("body") or {})
    view_html = (body.get("view") or {}).get("value", "")
    storage = (body.get("storage") or {}).get("value", "")
    attachments = [a async for a in client.paginate(
        f"/rest/api/content/{pid}/child/attachment", {"limit": 100, "expand": "version,extensions"})]

    parsed = parse_body(view_html, pid)
    expected = storage_counts(storage)
    folder.mkdir(parents=True, exist_ok=True)

    # ── plan downloads ───────────────────────────────────────────────────────
    taken: dict[str, set[str]] = {"images": set(), "attachments": set()}
    by_ref: dict[tuple[str, str], dict] = {}
    att_entries: list[dict] = []
    for a in attachments:
        title = a.get("title", "")
        ext = a.get("extensions") or {}
        media_type = ext.get("mediaType", "")
        sub = "images" if _is_image(title, media_type) else "attachments"
        local = unique_filename(safe_filename(title), taken[sub], str(a.get("id", "")))
        entry = {"id": str(a.get("id", "")), "filename": title, "media_type": media_type,
                 "listed_size": ext.get("fileSize"), "url": (a.get("_links") or {}).get("download", ""),
                 "local_path": f"{sub}/{local}", "downloaded": False, "error": ""}
        att_entries.append(entry)
        by_ref[(pid, title)] = entry

    downloads: list[dict] = list(att_entries)
    for res in parsed.resources:
        if res["kind"] == "embed":
            res["local_path"] = ""
            res["url"] = youtube_watch_url(res["src"])
            continue
        key = (res.get("attachment_page_id") or "", res.get("filename") or "")
        if key in by_ref:
            res["local_path"] = by_ref[key]["local_path"]
            res["entry"] = by_ref[key]
            continue
        # Image/file that lives on another page or another site, or a data: URI.
        name = res.get("filename") or res["kind"]
        sub = "images" if res["kind"] == "image" or _is_image(name) else "attachments"
        prefix = res.get("attachment_page_id") or "ext"
        local = unique_filename(safe_filename(name), taken[sub], prefix)
        entry = {"id": "", "filename": name, "media_type": "", "listed_size": None,
                 "url": res["src"], "local_path": f"{sub}/{local}", "downloaded": False,
                 "error": "", "external": True}
        if res.get("is_attachment"):
            by_ref[key] = entry
        res["local_path"] = entry["local_path"]
        res["entry"] = entry
        downloads.append(entry)

    sem = asyncio.Semaphore(4)

    async def fetch(entry: dict) -> None:
        dest = folder / entry["local_path"]
        try:
            async with sem:
                if entry["url"].startswith("data:"):
                    header, payload = entry["url"].split(",", 1)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(base64.b64decode(payload) if ";base64" in header
                                     else unquote(payload).encode("utf-8"))
                else:
                    entry["bytes"] = await client.download(entry["url"], dest)
            entry["downloaded"] = True
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"

    await asyncio.gather(*(fetch(e) for e in downloads))
    for e in downloads:
        if not e["downloaded"]:
            issues.append(f"Download failed: {e['filename']} — {e['error']}")

    # ── screenshot ───────────────────────────────────────────────────────────
    shot_names: list[str] = []
    if screenshots is None and screenshots_expected:
        issues.append("Screenshot skipped — the screenshot browser was unavailable this run")
    if screenshots is not None:
        try:
            shot_names = await screenshots.capture(rec["url"], folder)
        except Exception as exc:
            issues.append(f"Screenshot failed — {type(exc).__name__}: {str(exc)[:200]}")

    # ── markdown & json ──────────────────────────────────────────────────────
    def render(match: re.Match) -> str:
        res = parsed.resources[int(match.group(1))]
        if res["kind"] == "embed":
            return f"[Embedded video]({res['url']})" if "youtube" in res["url"] else f"[Embedded content]({res['url']})"
        entry = res.get("entry") or {}
        target = _md_link_path(res["local_path"]) if entry.get("downloaded") else res["src"]
        if res["kind"] == "image":
            return f"![{res.get('alt') or res['filename']}]({target})"
        label = "Video" if res["kind"] == "video" else "File"
        return f"[{label}: {res['filename']}]({target})"

    def subst(text: str) -> str:
        return _PLACEHOLDER.sub(render, text or "")

    markdown = subst(parsed.markdown)
    for coll in (parsed.expands, parsed.panels):
        for item in coll:
            item["markdown"] = subst(item["markdown"])
    for t in parsed.tables:
        t["rows"] = [[_PLACEHOLDER.sub("", c) for c in row] for row in t["rows"]]

    history = data.get("history") or {}
    labels = [lb.get("name", "") for lb in
              (((data.get("metadata") or {}).get("labels") or {}).get("results") or [])]
    ancestors = [{"id": str(a.get("id", "")), "title": a.get("title", "")}
                 for a in data.get("ancestors") or []]

    def media(kind: str) -> list[dict]:
        out = []
        for res in parsed.resources:
            if res["kind"] != kind:
                continue
            entry = res.get("entry") or {}
            out.append({"filename": res.get("filename", ""), "alt": res.get("alt", ""),
                        "source_url": res.get("url") or res["src"],
                        "local_path": res.get("local_path") if entry.get("downloaded") else "",
                        "downloaded": bool(entry.get("downloaded")) if kind != "embed" else None})
        return out

    found = {"expands": len(parsed.expands), "code_blocks": len(parsed.code_blocks),
             "images": sum(1 for r in parsed.resources if r["kind"] == "image"),
             "videos": sum(1 for r in parsed.resources if r["kind"] == "video"),
             "embeds": sum(1 for r in parsed.resources if r["kind"] == "embed"),
             "tables": len(parsed.tables)}
    for key, label in (("expands", "dropdown(s)"), ("code_blocks", "code block(s)"),
                       ("images", "image(s)"), ("videos", "video(s)"),
                       ("embeds", "embedded video(s)")):
        if found[key] < expected[key]:
            issues.append(f"Page source has {expected[key]} {label} but only "
                          f"{found[key]} were captured")
    if not parsed.text.strip() and not parsed.resources:
        if re.sub(r"<[^>]+>|&nbsp;|\s", "", storage):
            issues.append("Rendered page is empty but the page source has content")
        else:
            notes.append("Article body is empty on the site itself")
    # Identity check: every attachment of THIS page that the source references must
    # have been captured (a count check alone can be masked by an extra image).
    captured_names = {e["filename"] for e in downloads if e["downloaded"]}
    for name in sorted({unescape(n) for n in _OWN_ATTACHMENT_REF.findall(storage)}):
        if name not in captured_names:
            issues.append(f"Page source references attachment '{name}' that was not captured"
                          + ("" if (pid, name) in by_ref else " (it does not exist on the site)"))
    if screenshots is not None and not shot_names and not any(i.startswith("Screenshot") for i in issues):
        issues.append("Screenshot was not produced")

    status = "warning" if issues else "done"
    article = {
        "page_id": pid,
        "title": data.get("title", rec["title"]),
        "type": data.get("type", rec.get("content_type", "page")),
        "url": rec["url"],
        "space": {"key": rec["space_key"], "name": rec.get("space_name", "")},
        "product": {"key": rec.get("product", ""), "label": rec.get("product_label", "")},
        "breadcrumb": [a["title"] for a in ancestors],
        "ancestors": ancestors,
        "version": (data.get("version") or {}).get("number"),
        "last_updated": (history.get("lastUpdated") or {}).get("when", ""),
        "labels": labels,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "folder": rec["folder"],
        "content": {
            "markdown": markdown,
            "text": parsed.text,
            "headings": parsed.headings,
            "dropdowns": parsed.expands,
            "code_blocks": parsed.code_blocks,
            "tables": parsed.tables,
            "panels": parsed.panels,
            "links": parsed.links,
        },
        "media": {"images": media("image"), "videos": media("video"),
                  "files": media("file"), "embeds": media("embed")},
        "attachments": [{k: v for k, v in e.items() if k != "url"} | {"source_url": e["url"]}
                        for e in att_entries],
        "screenshots": shot_names,
        "verification": {"status": status, "expected_from_source": expected,
                         "captured": found, "issues": issues, "notes": notes},
    }

    front = ["---", f"title: {json.dumps(article['title'], ensure_ascii=False)}",
             f"page_id: {pid}", f"url: {rec['url']}",
             f"space: {json.dumps(rec.get('space_name') or rec['space_key'], ensure_ascii=False)}",
             f"product: {json.dumps(rec.get('product_label', ''), ensure_ascii=False)}",
             f"breadcrumb: {json.dumps(article['breadcrumb'], ensure_ascii=False)}",
             f"version: {article['version']}", f"last_updated: {article['last_updated']}",
             f"labels: {json.dumps(labels, ensure_ascii=False)}",
             f"scraped_at: {article['scraped_at']}", "---", "",
             f"# {article['title']}", ""]
    if shot_names:
        front += [f"*Screenshot: {', '.join(_md_link_path(n) for n in shot_names)}*", ""]
    _write_atomic(folder / "article.md", "\n".join(front) + markdown + "\n")
    _write_atomic(folder / "article.json", json.dumps(article, indent=2, ensure_ascii=False))

    # Files that failed to download this time keep their previous copy (if any).
    _remove_stale_files(folder, {e["local_path"] for e in downloads}, shot_names)

    return {"status": status, "issues": issues, "notes": notes, "found": found, "expected": expected,
            "files": sum(1 for e in downloads if e["downloaded"]),
            "files_expected": len(downloads), "screenshots": len(shot_names),
            "title": article["title"]}


def _remove_stale_files(folder: Path, keep: set[str], shots: list[str]) -> None:
    """Delete files a previous scrape of this article left behind that the current
    version no longer has. Only touches the folders/files this tool owns — never
    child-article folders."""
    for sub in ("images", "attachments"):
        d = folder / sub
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f"{sub}/{f.name}" not in keep:
                try:
                    f.unlink()
                except OSError:
                    pass
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    if shots:
        for f in folder.glob("screenshot*.png"):
            if f.name not in shots:
                try:
                    f.unlink()
                except OSError:
                    pass
