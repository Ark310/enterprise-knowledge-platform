"""Library-wide index files and the completeness audit.

index.json / index.md     every article on disk, grouped by product → space → tree
<space>/_space.json       the space's articles with their folders
Audit compares the live site map with what is on disk:
  missing   on the site, no article.json on disk (or it is unreadable)
  warnings  on disk, but its own verification recorded gaps
  stale     article.json on disk whose page no longer exists on the site, or that
            sits in an old folder because the page was renamed/moved since
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from kbscraper.discovery import SiteMap
from kbscraper.settings import PRODUCTS


def _scan(output_dir: Path) -> dict[str, list[dict]]:
    """page_id -> [summary of each article.json found for it]."""
    found: dict[str, list[dict]] = defaultdict(list)
    for f in output_dir.rglob("article.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            found[f"unreadable:{f}"].append({"path": str(f), "error": type(exc).__name__})
            continue
        ver = d.get("verification") or {}
        found[str(d.get("page_id", ""))].append({
            "page_id": str(d.get("page_id", "")), "title": d.get("title", ""),
            "space_key": (d.get("space") or {}).get("key", ""),
            "product": (d.get("product") or {}).get("key", ""),
            "folder": f.parent.relative_to(output_dir).as_posix(),
            "url": d.get("url", ""), "version": d.get("version"),
            "last_updated": d.get("last_updated", ""), "scraped_at": d.get("scraped_at", ""),
            "status": ver.get("status", ""), "issues": ver.get("issues", []),
            "images": len((d.get("media") or {}).get("images", [])),
            "files": len(d.get("attachments") or []),
        })
    return found


def audit(output_dir: Path, sitemap: SiteMap, spaces: set[str] | None = None) -> dict:
    """spaces limits the audit to those space keys (None = the whole site)."""
    output_dir = Path(output_dir)
    on_disk = _scan(output_dir)
    live = {a.page_id: a for a in sitemap.articles if spaces is None or a.space_key in spaces}
    audited_spaces = {s.key for s in sitemap.spaces if spaces is None or s.key in spaces}
    missing, warnings, stale, unreadable = [], [], [], []
    for key, entries in on_disk.items():
        if key.startswith("unreadable:"):
            unreadable.extend(entries)
    for pid, a in live.items():
        entries = on_disk.get(pid, [])
        current = [e for e in entries if e["folder"] == a.folder]
        if not current:
            missing.append({"page_id": pid, "title": a.title, "space_key": a.space_key,
                            "folder": a.folder, "url": a.url})
        elif current[0]["status"] == "warning":
            warnings.append(current[0])
        for e in entries:
            if e["folder"] != a.folder:
                stale.append({**e, "reason": f"page moved/renamed; now at {a.folder}"})
    for pid, entries in on_disk.items():
        if pid and not pid.startswith("unreadable:") and pid not in live:
            for e in entries:
                if e["space_key"] in audited_spaces:
                    stale.append({**e, "reason": "page no longer exists on the site"})
    return {"checked_at": datetime.now().isoformat(timespec="seconds"),
            "scope": sorted(spaces) if spaces is not None else "all",
            "live_articles": len(live),
            "on_disk": sum(len(v) for k, v in on_disk.items() if not k.startswith("unreadable:")),
            "missing": missing, "warnings": warnings, "stale": stale, "unreadable": unreadable}


def write_indexes(output_dir: Path, sitemap: SiteMap) -> dict:
    output_dir = Path(output_dir)
    on_disk = _scan(output_dir)
    live = {a.page_id: a for a in sitemap.articles}
    rows = []
    for a in sitemap.articles:
        entry = next((e for e in on_disk.get(a.page_id, []) if e["folder"] == a.folder), None)
        rows.append({"page_id": a.page_id, "title": a.title, "space_key": a.space_key,
                     "folder": a.folder, "url": a.url, "breadcrumb": a.ancestors,
                     "scraped": entry is not None,
                     "status": entry["status"] if entry else "missing",
                     "version": entry["version"] if entry else a.version,
                     "last_updated": entry["last_updated"] if entry else "",
                     "images": entry["images"] if entry else 0,
                     "files": entry["files"] if entry else 0})
    spaces = {s.key: s for s in sitemap.spaces}
    index = {"generated_at": datetime.now().isoformat(timespec="seconds"),
             "source": "https://help.contoso.example",
             "total_articles": len(rows),
             "scraped": sum(r["scraped"] for r in rows),
             "spaces": [{"key": s.key, "name": s.name, "product": s.product,
                         "folder": s.folder, "articles": s.page_count} for s in sitemap.spaces],
             "articles": rows}
    _write(output_dir / "index.json", json.dumps(index, indent=1, ensure_ascii=False))

    by_space: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_space[r["space_key"]].append(r)
    for key, items in by_space.items():
        sp = spaces.get(key)
        if not sp:
            continue
        (output_dir / sp.folder).mkdir(parents=True, exist_ok=True)
        _write(output_dir / sp.folder / "_space.json", json.dumps(
            {"key": sp.key, "name": sp.name, "product": sp.product_label,
             "articles": sorted(items, key=lambda r: r["folder"].lower())},
            indent=1, ensure_ascii=False))

    lines = ["# Contoso Knowledge Base", "",
             f"Source: https://help.contoso.example — generated {index['generated_at']}", "",
             f"**{index['scraped']} of {index['total_articles']} articles scraped.**", ""]
    for product, label in PRODUCTS.items():
        sps = [s for s in sitemap.spaces if s.product == product]
        if not sps:
            continue
        lines += [f"## {label}", ""]
        for sp in sps:
            lines += [f"### {sp.name} (`{sp.key}`)", ""]
            for r in sorted(by_space.get(sp.key, []), key=lambda r: r["folder"].lower()):
                depth = len(r["breadcrumb"])
                rel = r["folder"] + "/article.md"
                mark = "" if r["scraped"] else " — *not scraped*"
                lines.append(f"{'  ' * depth}- [{r['title']}](<{rel}>){mark}")
            lines.append("")
    _write(output_dir / "index.md", "\n".join(lines))
    return index


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
