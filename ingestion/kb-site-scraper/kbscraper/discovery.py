"""Site map discovery: every space, every page/blog post, and its library folder.

Folder layout (one folder per article, mirroring Confluence's page tree):
    <output>/<product>/<space folder>/<root page>/<child page>/<grandchild>/...
Each article folder holds article.json, article.md, screenshot.png, images/ and
attachments/ next to its child-page folders.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from kbscraper.confluence import ConfluenceClient
from kbscraper.paths import safe_segment, unique_name
from kbscraper.settings import BASE_URL, PRODUCTS, SITEMAP_FILE, space_location


@dataclass
class SpaceInfo:
    key: str
    name: str
    product: str
    product_label: str
    folder: str           # "<product>/<space folder>" relative to the output dir
    homepage_id: str = ""
    page_count: int = 0
    error: str = ""


@dataclass
class ArticleInfo:
    page_id: str
    title: str
    content_type: str     # "page" | "blogpost"
    space_key: str
    url: str
    version: int
    parent_id: str = ""
    ancestors: list[str] = field(default_factory=list)   # ancestor titles, root first
    folder: str = ""      # relative to the output dir, POSIX separators
    position: int = 0


@dataclass
class SiteMap:
    spaces: list[SpaceInfo]
    articles: list[ArticleInfo]
    discovered_at: str = ""

    def to_json(self) -> dict:
        return {"discovered_at": self.discovered_at,
                "spaces": [asdict(s) for s in self.spaces],
                "articles": [asdict(a) for a in self.articles]}

    @classmethod
    def from_json(cls, data: dict) -> "SiteMap":
        return cls(spaces=[SpaceInfo(**s) for s in data.get("spaces", [])],
                   articles=[ArticleInfo(**a) for a in data.get("articles", [])],
                   discovered_at=data.get("discovered_at", ""))

    def save(self, path=SITEMAP_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_json(), indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path=SITEMAP_FILE) -> "SiteMap | None":
        try:
            return cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None


async def list_spaces(client: ConfluenceClient, excluded: list[str]) -> list[SpaceInfo]:
    spaces: list[SpaceInfo] = []
    excluded_lower = {e.lower() for e in excluded}
    async for s in client.paginate("/rest/api/space", {"limit": 100, "expand": "homepage"}):
        if s["key"].lower() in excluded_lower:
            continue
        product, space_folder = space_location(s["key"], s.get("name", s["key"]))
        spaces.append(SpaceInfo(
            key=s["key"], name=s.get("name", s["key"]), product=product,
            product_label=PRODUCTS.get(product, product),
            folder=f"{product}/{space_folder}",
            homepage_id=str((s.get("homepage") or {}).get("id", "")),
        ))
    order = list(PRODUCTS)
    spaces.sort(key=lambda sp: (order.index(sp.product) if sp.product in order else 99,
                                sp.name.lower()))
    return spaces


async def list_space_content(client: ConfluenceClient, space: SpaceInfo) -> list[ArticleInfo]:
    """All current pages and blog posts of one space (title, version, ancestry)."""
    out: list[ArticleInfo] = []
    seen: set[str] = set()
    for ctype in ("page", "blogpost"):
        params = {"spaceKey": space.key, "type": ctype, "status": "current",
                  "limit": 100, "expand": "ancestors,version"}
        async for item in client.paginate("/rest/api/content", params):
            pid = str(item["id"])
            if pid in seen:
                continue
            seen.add(pid)
            ancestors = item.get("ancestors") or []
            webui = (item.get("_links") or {}).get("webui", "")
            out.append(ArticleInfo(
                page_id=pid, title=item.get("title", "") or f"Untitled {pid}",
                content_type=ctype, space_key=space.key,
                url=f"{BASE_URL}{webui}" if webui else f"{BASE_URL}/pages/viewpage.action?pageId={pid}",
                version=int((item.get("version") or {}).get("number", 0)),
                parent_id=str(ancestors[-1]["id"]) if ancestors else "",
                ancestors=[a.get("title", "") for a in ancestors],
                position=len(out),
            ))
    return out


def assign_folders(space: SpaceInfo, articles: list[ArticleInfo]) -> None:
    """Give every article a unique folder that mirrors its place in the page tree.
    Pages whose parent is missing (restricted, or in another space) sit at the space
    root; blog posts go under 'Blog Posts/'."""
    by_id = {a.page_id: a for a in articles}
    children: dict[str, list[ArticleInfo]] = {}
    roots: list[ArticleInfo] = []
    blogs: list[ArticleInfo] = []
    for a in articles:
        if a.content_type == "blogpost":
            blogs.append(a)
        elif a.parent_id and a.parent_id in by_id:
            children.setdefault(a.parent_id, []).append(a)
        else:
            roots.append(a)

    placed: set[str] = set()

    def place(nodes: list[ArticleInfo], parent_folder: str, reserved=()) -> None:
        taken: set[str] = {r.lower() for r in reserved}
        for node in sorted(nodes, key=lambda n: (n.title.lower(), n.page_id)):
            if node.page_id in placed:      # guards against ancestry cycles
                continue
            placed.add(node.page_id)
            name = unique_name(safe_segment(node.title), taken, node.page_id)
            node.folder = str(PurePosixPath(parent_folder) / name)
            place(children.get(node.page_id, []), node.folder)

    place(roots, space.folder, reserved=("Blog Posts", "_unplaced"))
    if blogs:
        place(blogs, f"{space.folder}/Blog Posts")

    # A cycle in ancestry data would leave pages unplaced; put them at the root.
    unplaced = [a for a in articles if not a.folder]
    if unplaced:
        place(unplaced, f"{space.folder}/_unplaced")


async def discover(client: ConfluenceClient, excluded: list[str], log=None,
                   only_spaces: set[str] | None = None) -> SiteMap:
    """Full site map. A space whose listing fails is recorded with its error (and
    zero articles) rather than aborting the whole discovery."""
    from datetime import datetime
    log = log or (lambda level, msg: None)
    spaces = await list_spaces(client, excluded)
    if only_spaces:
        spaces = [s for s in spaces if s.key in only_spaces]
    all_articles: list[ArticleInfo] = []
    for sp in spaces:
        try:
            arts = await list_space_content(client, sp)
        except Exception as exc:  # recorded and surfaced; other spaces continue
            sp.error = f"{type(exc).__name__}: {exc}"
            log("error", f"Discovery failed for space {sp.key}: {sp.error}")
            continue
        assign_folders(sp, arts)
        sp.page_count = len(arts)
        all_articles.extend(arts)
        log("info", f"{sp.key} ({sp.name}): {len(arts)} article(s)")
    return SiteMap(spaces=spaces, articles=all_articles,
                   discovered_at=datetime.now().isoformat(timespec="seconds"))
