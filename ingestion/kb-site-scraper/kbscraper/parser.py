"""Convert a Confluence page's rendered body (REST body.view HTML) into Markdown plus
structured data: dropdown (expand) sections with their titles, tables as rows, code
blocks with language, info/note/warning panels, links, and every image / video /
file / embed the article shows.

Markdown references resources with {{res:N}} placeholders (N indexes `resources`);
the writer swaps them for local paths once the downloads are known.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from kbscraper.confluence import absolute

BLOCK_TAGS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table",
              "pre", "blockquote", "hr", "section", "article", "details", "dl", "form",
              "video", "iframe", "figure", "center", "header", "footer", "nav", "main",
              "audio", "embed", "object", "dt", "dd"}
# Dynamic / navigation macros that are not article content (search boxes, "create
# page" buttons, recently-updated feeds that list editors' names).
SKIP_MACROS = {"toc", "livesearch", "create-from-template", "recently-updated",
               "contributors", "pagetree", "pagetreesearch", "search"}
PANEL_TYPES = ("warning", "note", "tip", "info", "success", "error")
_WS = re.compile(r"[ \t\r\f\v ​]+")
_ATTACH_RE = re.compile(r"/download/(?:attachments|thumbnails)/(\d+)/([^?#]+)")
_YOUTUBE_RE = re.compile(r"youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)([\w-]{6,})|youtu\.be/([\w-]{6,})")


def clean(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


@dataclass
class ParseResult:
    markdown: str = ""
    text: str = ""
    headings: list[dict] = field(default_factory=list)
    expands: list[dict] = field(default_factory=list)
    code_blocks: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    panels: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    resources: list[dict] = field(default_factory=list)


def attachment_ref(url: str) -> tuple[str, str] | None:
    """(container page id, file name) for a /download/attachments|thumbnails URL."""
    m = _ATTACH_RE.search(urlparse(url).path)
    if not m:
        return None
    return m.group(1), unquote(m.group(2))


class _Converter:
    def __init__(self, page_id: str):
        self.page_id = page_id
        self.r = ParseResult()

    # ── resources ────────────────────────────────────────────────────────────
    def _resource(self, kind: str, src: str, name: str = "", alt: str = "",
                  el: Tag | None = None) -> str:
        src = absolute(src) if src and not src.startswith("data:") else src
        ref = attachment_ref(src) if src else None
        container = ""
        filename = name
        if el is not None:
            container = el.get("data-linked-resource-container-id") or ""
            filename = el.get("data-linked-resource-default-alias") or filename
        if ref:
            container = container or ref[0]
            filename = filename or ref[1]
        if not filename and src and not src.startswith("data:"):
            filename = unquote(urlparse(src).path.rsplit("/", 1)[-1]) or kind
        self.r.resources.append({
            "kind": kind, "src": src, "filename": filename, "alt": alt,
            "attachment_page_id": container,
            "is_attachment": bool(ref),
        })
        return "{{res:%d}}" % (len(self.r.resources) - 1)

    def _image(self, el: Tag) -> str:
        src = el.get("data-image-src") or el.get("src") or ""
        classes = el.get("class") or []
        if not src or "emoticon" in classes or "/images/icons/emoticons/" in src:
            return clean(el.get("alt", ""))
        alt = clean(el.get("alt") or el.get("title") or "")
        return self._resource("image", src, alt=alt, el=el)

    # ── inline ───────────────────────────────────────────────────────────────
    def inline(self, el) -> str:
        if isinstance(el, NavigableString):
            if el.__class__.__name__ in ("Comment", "CData", "ProcessingInstruction", "Doctype"):
                return ""
            return _WS.sub(" ", str(el))
        if not isinstance(el, Tag):
            return ""
        name = el.name
        if name in ("script", "style", "noscript", "button", "input", "select", "textarea"):
            return ""
        if self._skip(el):
            return ""
        if name == "br":
            return "\n"
        if name == "img":
            return self._image(el)
        if name in BLOCK_TAGS or self._has_block_child(el):
            return "\n\n" + "\n\n".join(self.blocks(el)) + "\n\n"
        if name == "a":
            return self._link(el)
        inner = "".join(self.inline(c) for c in el.children)
        if name in ("strong", "b"):
            return _wrap(inner, "**")
        if name in ("em", "i"):
            return _wrap(inner, "*")
        if name in ("s", "del", "strike"):
            return _wrap(inner, "~~")
        if name == "code":
            t = el.get_text()
            return f"`{t}`" if t.strip() else t
        if name == "sup":
            return f"^{inner}" if inner.strip() else inner
        if name == "time":
            return el.get("datetime") or inner
        return inner

    def _link(self, el: Tag) -> str:
        href = el.get("href") or ""
        classes = el.get("class") or []
        if "confluence-embedded-file" in classes or el.get("data-linked-resource-type") == "attachment":
            # Rendered as a file card with a placeholder thumbnail — the file is the content.
            src = el.get("data-file-src") or href
            name = el.get("data-linked-resource-default-alias") or clean(el.get_text())
            if src:
                return self._resource("file", src, name=name, alt=name, el=el)
        if el.find("img") is not None and href and attachment_ref(absolute(href)):
            # A thumbnail linking to its full-size attachment: keep the image.
            return "".join(self.inline(c) for c in el.children)
        inner = "".join(self.inline(c) for c in el.children)
        text = clean(inner) or clean(el.get_text())
        if not href or href.startswith(("#", "javascript:")):
            return inner
        url = absolute(href) if not href.startswith(("mailto:", "tel:")) else href
        if not href.startswith(("mailto:", "tel:")):
            ref = attachment_ref(url)
            if ref:
                return self._resource("file", url, name=ref[1], alt=text, el=el)
        linked_id = el.get("data-linked-resource-id") or ""
        if not linked_id and "pageId=" in url:
            linked_id = (parse_qs(urlparse(url).query).get("pageId") or [""])[0]
        self.r.links.append({"text": text, "url": url, "page_id": linked_id,
                             "internal": url.startswith(absolute("/"))})
        if "\n" in inner.strip() or "{{res:" in inner:
            return f"{inner} ({url})"
        return f"[{text or url}]({url})"

    # ── blocks ───────────────────────────────────────────────────────────────
    def _skip(self, el: Tag) -> bool:
        macro = el.get("data-macro-name")
        if macro in SKIP_MACROS:
            return True
        classes = el.get("class") or []
        return "toc-macro" in classes or "search-macro" in classes

    @staticmethod
    def _has_block_child(el: Tag) -> bool:
        return any(isinstance(c, Tag) and c.name in BLOCK_TAGS for c in el.descendants)

    def blocks(self, el: Tag, depth: int = 0) -> list[str]:
        """Render el's children as a list of Markdown blocks. Consecutive inline
        children are gathered into one paragraph."""
        out: list[str] = []
        buf: list[str] = []

        def flush():
            text = _tidy_inline("".join(buf))
            buf.clear()
            if text:
                out.append(text)

        for child in el.children:
            if isinstance(child, Tag) and (child.name in BLOCK_TAGS or
                                           (child.name not in ("a",) and self._has_block_child(child))):
                flush()
                out.extend(b for b in self.block(child, depth) if b.strip())
            else:
                buf.append(self.inline(child))
        flush()
        return out

    def block(self, el: Tag, depth: int = 0) -> list[str]:
        name = el.name
        classes = el.get("class") or []
        macro = el.get("data-macro-name") or ""
        if name in ("script", "style", "noscript", "form") or self._skip(el):
            return []

        if macro == "expand" or "expand-container" in classes:
            return [self._expand(el, depth)]
        if macro in ("code", "noformat") or ("code" in classes and "panel" in classes) \
                or "preformatted" in classes:
            return [self._code(el)]
        if "confluence-information-macro" in classes or macro in PANEL_TYPES:
            return [self._panel(el, depth)]
        if "panel" in classes and el.find(class_="panelContent"):
            return [self._titled_panel(el, depth)]

        if re.fullmatch(r"h[1-6]", name or ""):
            text = _tidy_inline(self.inline_children(el)).replace("\n", " ")
            if not text:
                return []
            text = re.sub(r"^\*\*([^*]+)\*\*$", r"\1", text)
            level = int(name[1])
            self.r.headings.append({"level": level, "text": _strip_md(text),
                                    "anchor": el.get("id", "")})
            return [f"{'#' * level} {text}"]
        if name == "p":
            text = _tidy_inline(self.inline_children(el))
            return [text] if text else []
        if name in ("ul", "ol"):
            return [self._list(el, depth)]
        if name == "table":
            return [self._table(el)]
        if name == "pre":
            code = el.get_text()
            lang = _brush(el.get("data-syntaxhighlighter-params", ""))
            self.r.code_blocks.append({"title": "", "language": lang, "code": code.rstrip("\n")})
            return [f"```{lang}\n{code.rstrip()}\n```"]
        if name == "blockquote":
            inner = "\n\n".join(self.blocks(el, depth))
            return ["\n".join(f"> {ln}" if ln else ">" for ln in inner.splitlines())]
        if name == "hr":
            return ["---"]
        if name == "video" or name == "audio":
            src = el.get("src") or ""
            if not src and el.find("source") is not None:
                src = el.find("source").get("src", "")
            if src:
                return [self._resource("video" if name == "video" else "file", src)]
            return []
        if name in ("iframe", "embed", "object"):
            src = el.get("src") or el.get("data") or ""
            if not src:
                return []
            src = absolute(src)
            if attachment_ref(src):
                return [self._resource("file", src)]
            return [self._resource("embed", src, alt=el.get("title", ""))]
        if name == "img":
            return [self._image(el)]
        if name == "dt":
            text = _tidy_inline(self.inline_children(el))
            return [f"**{text}**"] if text else []
        # Generic container (div, section, layout cells, li-less wrappers, spans
        # wrapping blocks): recurse.
        return self.blocks(el, depth)

    def inline_children(self, el: Tag) -> str:
        return "".join(self.inline(c) for c in el.children)

    def _expand(self, el: Tag, depth: int) -> str:
        ctrl = el.find(class_="expand-control-text")
        title = clean(ctrl.get_text()) if ctrl else ""
        body = el.find(class_="expand-content")
        record = {"title": title or "Expand", "markdown": "", "text": ""}
        self.r.expands.append(record)   # appended first so nested expands follow their parent
        inner = "\n\n".join(self.blocks(body, depth)) if body else ""
        record["markdown"] = inner
        record["text"] = clean(body.get_text(" ")) if body else ""
        return f"<details>\n<summary>{record['title']}</summary>\n\n{inner}\n\n</details>"

    def _code(self, el: Tag) -> str:
        header = el.find(class_="codeHeader")
        title = clean(header.get_text()) if header else ""
        pre = el.find("pre")
        code = pre.get_text() if pre else el.get_text()
        lang = _brush(pre.get("data-syntaxhighlighter-params", "")) if pre else ""
        code = code.strip("\n")
        self.r.code_blocks.append({"title": title, "language": lang, "code": code})
        head = f"**{title}**\n\n" if title else ""
        return f"{head}```{lang}\n{code}\n```"

    def _panel(self, el: Tag, depth: int) -> str:
        classes = " ".join(el.get("class") or [])
        kind = next((t for t in PANEL_TYPES if t in classes), el.get("data-macro-name") or "info")
        title_el = el.find(class_="title")
        title = clean(title_el.get_text()) if title_el else ""
        body = el.find(class_="confluence-information-macro-body") or el
        inner = "\n\n".join(self.blocks(body, depth))
        self.r.panels.append({"type": kind, "title": title, "markdown": inner})
        label = kind.capitalize() + (f": {title}" if title else "")
        lines = [f"> **{label}**"] + [f"> {ln}" if ln else ">" for ln in inner.splitlines()]
        return "\n".join(lines)

    def _titled_panel(self, el: Tag, depth: int) -> str:
        header = el.find(class_="panelHeader")
        title = clean(header.get_text()) if header else ""
        body = el.find(class_="panelContent")
        inner = "\n\n".join(self.blocks(body, depth)) if body else ""
        self.r.panels.append({"type": "panel", "title": title, "markdown": inner})
        return (f"**{title}**\n\n" if title else "") + inner

    def _list(self, el: Tag, depth: int) -> str:
        lines: list[str] = []
        n = 0
        start = int(el.get("start", 1) or 1) if el.name == "ol" else 1
        for li in el.find_all("li", recursive=False):
            n += 1
            marker = f"{start + n - 1}." if el.name == "ol" else "-"
            indent = "   " * depth
            parts: list[str] = []
            nested: list[str] = []
            buf: list[str] = []
            for child in li.children:
                if isinstance(child, Tag) and child.name in ("ul", "ol"):
                    nested.append(self._list(child, depth + 1))
                elif isinstance(child, Tag) and (child.name in BLOCK_TAGS or self._has_block_child(child)):
                    if buf:
                        parts.append(_tidy_inline("".join(buf))); buf.clear()
                    parts.extend(self.block(child, depth + 1))
                else:
                    buf.append(self.inline(child))
            if buf:
                parts.append(_tidy_inline("".join(buf)))
            parts = [p for p in parts if p.strip()]
            body = ("\n" + indent + "   ").join(p.replace("\n", "\n" + indent + "   ") for p in parts)
            lines.append(f"{indent}{marker} {body}".rstrip())
            lines.extend(nested)
        return "\n".join(lines)

    def _cell(self, cell: Tag) -> tuple[str, str]:
        """(markdown for a table cell, plain text). Nested tables flatten to text."""
        parts: list[str] = []
        for b in self.blocks(cell):
            parts.append(b)
        md = "<br>".join(p.replace("\n", "<br>") for p in parts if p.strip())
        md = md.replace("|", "\\|")
        return md, clean(cell.get_text(" "))

    def _table(self, table: Tag) -> str:
        rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
        grid: list[list[tuple[str, str] | None]] = []
        header_flags: list[bool] = []
        pending: dict[int, list] = {}   # column -> [remaining rowspan, value]
        for tr in rows:
            cells = [c for c in tr.find_all(["td", "th"], recursive=False)]
            row: list = []
            col = 0
            ci = 0
            while ci < len(cells) or any(c >= col for c in pending):
                if col in pending:
                    left, val = pending[col]
                    row.append(val)
                    if left <= 1:
                        del pending[col]
                    else:
                        pending[col][0] = left - 1
                    col += 1
                    continue
                if ci >= len(cells):
                    break
                cell = cells[ci]
                ci += 1
                val = self._cell(cell)
                span = _int(cell.get("colspan"), 1)
                rspan = _int(cell.get("rowspan"), 1)
                for k in range(span):
                    row.append(val if k == 0 else ("", ""))
                    if rspan > 1:
                        pending[col] = [rspan - 1, ("", "")]
                    col += 1
            if row:
                grid.append(row)
                header_flags.append(all(c.name == "th" for c in cells) and bool(cells))
        if not grid:
            return ""
        width = max(len(r) for r in grid)
        for r in grid:
            r.extend([("", "")] * (width - len(r)))

        has_header = header_flags[0] or not any(header_flags)
        header = grid[0] if has_header else [(f"Column {i + 1}", f"Column {i + 1}") for i in range(width)]
        body = grid[1:] if has_header else grid
        headers_text = [h[1] for h in header]
        record = {"headers": headers_text, "rows": [[c[1] for c in r] for r in body]}
        if len(set(headers_text)) == len(headers_text) and all(headers_text):
            record["records"] = [dict(zip(headers_text, (c[1] for c in r))) for r in body]
        self.r.tables.append(record)

        def line(cells):
            return "| " + " | ".join(c[0] or " " for c in cells) + " |"
        out = [line(header), "| " + " | ".join("---" for _ in range(width)) + " |"]
        out += [line(r) for r in body]
        return "\n".join(out)


def _int(v, default: int) -> int:
    try:
        return max(1, min(50, int(v)))
    except (TypeError, ValueError):
        return default


def _brush(params: str) -> str:
    m = re.search(r"brush:\s*([\w#+-]+)", params or "")
    return m.group(1) if m else ""


def _wrap(inner: str, mark: str) -> str:
    if not inner.strip():
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    return f"{lead}{mark}{inner.strip()}{mark}{trail}"


def _tidy_inline(text: str) -> str:
    lines = [_WS.sub(" ", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    s = "\n".join(out).strip()
    s = re.sub(r"\*\*\s*\*\*", "", s)
    return re.sub(r"\n{3,}", "\n\n", s)


def _strip_md(text: str) -> str:
    return re.sub(r"[*_`~]|\{\{res:\d+\}\}", "", text).strip()


def parse_body(html: str, page_id: str) -> ParseResult:
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.body or soup
    conv = _Converter(page_id)
    md = "\n\n".join(b for b in conv.blocks(root) if b.strip())
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    conv.r.markdown = md
    for s in root.select("script, style"):
        s.decompose()
    text = root.get_text("\n")
    conv.r.text = re.sub(r"\n\s*\n+", "\n\n", "\n".join(clean(t) for t in text.splitlines())).strip()
    return conv.r


def youtube_watch_url(src: str) -> str:
    m = _YOUTUBE_RE.search(src or "")
    if not m:
        return src
    return f"https://www.youtube.com/watch?v={m.group(1) or m.group(2)}"


def storage_counts(storage: str) -> dict:
    """What the page's source says it contains — used to verify the capture."""
    s = storage or ""
    return {
        "expands": len(re.findall(r'<ac:(?:structured-)?macro[^>]*ac:name="expand"', s)),
        "code_blocks": len(re.findall(r'<ac:(?:structured-)?macro[^>]*ac:name="(?:code|noformat)"', s)),
        "images": len(re.findall(r"<ac:image\b", s)),
        "videos": len(re.findall(r'<ac:(?:structured-)?macro[^>]*ac:name="multimedia"', s)),
        "embeds": len(re.findall(r'<ac:(?:structured-)?macro[^>]*ac:name="widget"', s)),
        "tables": len(re.findall(r"<table\b", s)),
    }
