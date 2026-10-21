"""Library index (index.json / index.md), the _site/ discovery files, and the audit
(live site vs. disk), with the same audit keys as the KB scraper so the GUI can share code."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from restscraper.discovery import SiteMap


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_site_files(output_dir: Path, pp: dict, llms: str, report: dict) -> None:
    site = Path(output_dir) / "_site"
    menu = pp["documents"]["data"]["documentMenu"]
    _write(site / "menu.json", json.dumps({"items": menu.get("items"), "slugs": menu.get("slugs")},
                                          ensure_ascii=False, indent=1))
    if llms:
        _write(site / "llms.txt", llms)
    _write(site / "discovery_report.json", json.dumps(report, ensure_ascii=False, indent=2))


def _read_page(folder: Path) -> dict | None:
    try:
        return json.loads((folder / "page.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _scan(output_dir: Path) -> tuple[dict[str, list[Path]], list[dict]]:
    found: dict[str, list[Path]] = {}
    unreadable = []
    for p in Path(output_dir).rglob("page.json"):
        if "_site" in p.parts:
            continue
        try:
            pid = json.loads(p.read_text(encoding="utf-8")).get("page_id", "")
        except (OSError, ValueError) as exc:
            unreadable.append({"path": str(p), "error": f"{type(exc).__name__}: {exc}"})
            continue
        found.setdefault(pid, []).append(p.parent)
    return found, unreadable


def audit(output_dir: Path, sitemap: SiteMap) -> dict:
    output_dir = Path(output_dir)
    on_disk, unreadable = _scan(output_dir)
    live = [p for p in sitemap.pages if not p.external]
    missing, warnings, stale = [], [], []
    live_ids = {p.page_id: p for p in live}
    for p in live:
        expected = (output_dir / p.folder).resolve()
        folders = on_disk.get(p.page_id, [])
        if not any(f.resolve() == expected for f in folders):
            missing.append({"page_id": p.page_id, "title": p.title, "space_key": p.section_key,
                            "folder": p.folder})
            continue
        doc = _read_page(output_dir / p.folder) or {}
        issues = (doc.get("verification") or {}).get("issues") or []
        if issues:
            warnings.append({"page_id": p.page_id, "title": p.title, "issues": issues})
    for pid, folders in on_disk.items():
        for f in folders:
            rel = f.relative_to(output_dir).as_posix()
            page = live_ids.get(pid)
            if page is None:
                stale.append({"page_id": pid, "title": f.name, "folder": rel,
                              "reason": "no longer on the site"})
            elif rel != page.folder:
                stale.append({"page_id": pid, "title": page.title, "folder": rel,
                              "reason": f"moved/renamed to {page.folder}"})
    return {"live_articles": len(live), "on_disk": sum(len(v) for v in on_disk.values()),
            "missing": missing, "warnings": warnings, "stale": stale, "unreadable": unreadable}


def write_indexes(output_dir: Path, sitemap: SiteMap) -> dict:
    output_dir = Path(output_dir)
    sections = []
    lines = ["# Contoso REST API documentation", "",
             f"Scraped from https://apidocs.contoso.example, indexed "
             f"{datetime.now():%Y-%m-%d %H:%M}.", ""]
    for s in sitemap.sections:
        pages = [p for p in sitemap.pages if p.section_key == s.key]
        entries = []
        lines += [f"## {s.name}", ""]
        for p in pages:
            doc = _read_page(output_dir / p.folder) or {}
            ver = doc.get("verification") or {}
            ep = doc.get("endpoint") or {}
            status = "missing" if not doc else ("warning" if ver.get("issues") else "done")
            entries.append({"page_id": p.page_id, "title": p.title, "slug": p.slug, "url": p.url,
                            "folder": p.folder, "kind": doc.get("kind", p.kind), "status": status,
                            "method": ep.get("method", ""), "path": ep.get("path", ""),
                            "issues": ver.get("issues", [])})
            if p.kind == "section":
                continue
            label = f"`{ep['method']}` " if ep.get("method") else ""
            rel = (p.folder + "/page.md").replace(" ", "%20")
            flag = "" if status == "done" else f" — **{status}**"
            lines.append(f"- {label}[{p.title}]({rel}){flag}")
        lines.append("")
        sections.append({"key": s.key, "name": s.name, "folder": s.folder, "pages": entries})
    index = {"generated_at": datetime.now().isoformat(timespec="seconds"),
             "site": "https://apidocs.contoso.example", "sections": sections,
             "discovery": sitemap.report}
    _write(output_dir / "index.json", json.dumps(index, ensure_ascii=False, indent=1))
    _write(output_dir / "index.md", "\n".join(lines))
    return index
