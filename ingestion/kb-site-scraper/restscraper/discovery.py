"""Site discovery from Theneo's own menu: every section and endpoint page, plus folder names.

The menu in __NEXT_DATA__ is the source of truth. llms.txt is fetched only to
cross-check (it lists some pages under former slugs, which documentMenu.slugs maps
back to the same section id).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from kbscraper.paths import safe_segment, unique_name
from restscraper import theneo
from restscraper.settings import BASE_URL, SITEMAP_FILE, START_SLUG

# Names a page folder uses for its own content; a child page may not take them.
RESERVED = {"images", "snippets", "responses", "tryit", "page.json", "page.md", "page.html",
            "source.md", "_section.json"}


@dataclass
class SectionInfo:
    key: str
    name: str
    page_id: str
    order: int
    folder: str


@dataclass
class PageInfo:
    page_id: str
    slug: str
    title: str
    section_key: str
    section_name: str
    url: str
    kind: str               # "section" | "endpoint"
    order: int
    folder: str = ""
    parent_id: str = ""
    external: str = ""      # external link target (not scraped)


@dataclass
class SiteMap:
    sections: list[SectionInfo]
    pages: list[PageInfo]
    discovered_at: str = ""
    report: dict = field(default_factory=dict)

    def page(self, pid: str) -> PageInfo | None:
        return next((p for p in self.pages if p.page_id == pid), None)

    def records(self, section_keys: set[str] | None = None,
                page_ids: set[str] | None = None) -> list[dict]:
        out = []
        for p in self.pages:
            if section_keys is not None and p.section_key not in section_keys:
                continue
            if page_ids is not None and p.page_id not in page_ids:
                continue
            out.append({"page_id": p.page_id, "title": p.title, "slug": p.slug, "kind": p.kind,
                        "space_key": p.section_key, "space_name": p.section_name,
                        "folder": p.folder, "url": p.url, "order": p.order})
        return out

    def save(self, path: Path = SITEMAP_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"discovered_at": self.discovered_at, "report": self.report,
                                   "sections": [asdict(s) for s in self.sections],
                                   "pages": [asdict(p) for p in self.pages]},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path = SITEMAP_FILE) -> "SiteMap | None":
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return cls([SectionInfo(**s) for s in d["sections"]], [PageInfo(**p) for p in d["pages"]],
                       d.get("discovered_at", ""), d.get("report", {}))
        except (OSError, ValueError, KeyError, TypeError):
            return None


def _unique(name: str, taken: set[str], suffix: str) -> str:
    if name.lower() in RESERVED:
        name = f"{name} [{suffix}]"
    return unique_name(name, taken, suffix)


def build_sitemap(pp: dict, llms_slugs: list[str]) -> SiteMap:
    sections: list[SectionInfo] = []
    pages: list[PageInfo] = []
    order = 0
    for n, item in enumerate(theneo.menu_items(pp), start=1):
        key, name = item["slug"], item.get("name") or item["slug"]
        folder = f"{n:02d} {safe_segment(name, 70)}"
        sections.append(SectionInfo(key, name, item["sectionId"], n, folder))
        order += 1
        pages.append(PageInfo(item["sectionId"], key, name, key, name, f"{BASE_URL}/{key}",
                              "section", order, folder, external=item.get("externalPageLink") or ""))
        taken: set[str] = set()
        for sub in item.get("subItems") or []:
            order += 1
            slug = f"{key}/{sub['slug']}"
            title = sub.get("name") or sub["slug"]
            child = _unique(safe_segment(title), taken, sub["slug"])
            pages.append(PageInfo(sub["sectionId"], slug, title, key, name, f"{BASE_URL}/{slug}",
                                  "endpoint", order, f"{folder}/{child}", parent_id=item["sectionId"],
                                  external=sub.get("externalPageLink") or ""))
            # Deeper levels have not been seen on this site; flatten them under the section.
            for deep in sub.get("subItems") or []:
                order += 1
                dslug = f"{key}/{deep['slug']}"
                dtitle = deep.get("name") or deep["slug"]
                dchild = _unique(safe_segment(dtitle), taken, deep["slug"])
                pages.append(PageInfo(deep["sectionId"], dslug, dtitle, key, name,
                                      f"{BASE_URL}/{dslug}", "endpoint", order, f"{folder}/{dchild}",
                                      parent_id=sub["sectionId"]))
    sm = SiteMap(sections, pages, datetime.now().isoformat(timespec="seconds"))
    sm.report = crosscheck(pp, llms_slugs)
    return sm


def crosscheck(pp: dict, llms_slugs: list[str]) -> dict:
    aliases = theneo.slug_aliases(pp)
    menu: dict[str, str] = {}          # slug -> section id
    for item in theneo.menu_items(pp):
        menu[item["slug"]] = item["sectionId"]
        for sub in item.get("subItems") or []:
            menu[f"{item['slug']}/{sub['slug']}"] = sub["sectionId"]
    menu_ids = set(menu.values())
    llms_ids = set()
    missing_from_menu = []
    for slug in llms_slugs:
        sid = menu.get(slug) or aliases.get(slug.rsplit("/", 1)[-1])
        if sid in menu_ids:
            llms_ids.add(sid)
        else:
            missing_from_menu.append(slug)
    missing_from_llms = [s for s, sid in menu.items() if sid not in llms_ids] if llms_slugs else []
    # llms.txt keeps some pages under their former slug; pair those with the renamed menu page
    # in the same section so only real gaps remain.
    renamed = {}
    for old in list(missing_from_menu):
        section = old.split("/", 1)[0]
        candidates = [m for m in missing_from_llms if "/" in old and m.startswith(section + "/")]
        best = max(candidates, key=lambda m: SequenceMatcher(None, old, m).ratio(), default=None)
        if best and SequenceMatcher(None, old, best).ratio() >= 0.8:
            renamed[old] = best
            missing_from_menu.remove(old)
            missing_from_llms.remove(best)
    return {"menu": len(menu), "llms": len(llms_slugs), "missing_from_menu": missing_from_menu,
            "missing_from_llms": missing_from_llms, "renamed": renamed}


async def discover(client, log=None) -> tuple[SiteMap, dict, str]:
    """Fetch the start page + llms.txt. Returns (sitemap, pageProps, llms text)."""
    log = log or (lambda level, msg: None)
    html = await client.get_text(f"/{START_SLUG}")
    pp = theneo.next_data(html)
    try:
        llms = await client.get_text("/llms.txt")
    except Exception as exc:      # cross-check only; discovery stands on the menu
        log("warning", f"llms.txt could not be read ({type(exc).__name__}); skipping the cross-check")
        llms = ""
    sm = build_sitemap(pp, theneo.parse_llms(llms))
    r = sm.report
    log("info", f"Site map: {len(sm.sections)} sections, {len(sm.pages)} pages "
                f"(llms.txt lists {r['llms']}; {len(r['missing_from_menu'])} not in the menu, "
                f"{len(r['missing_from_llms'])} not in llms.txt, {len(r['renamed'])} renamed)")
    return sm, pp, llms
