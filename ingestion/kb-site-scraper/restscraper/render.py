"""Markdown rendering: Theneo description HTML -> Markdown, and the readable page.md."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from restscraper.settings import LANGUAGES

_FENCE_LANG = {"cURL": "bash", "Ruby": "ruby", "Python": "python", "PHP": "php", "Java": "java",
               "Node.js": "javascript", "Go": "go", ".NET": "csharp"}


def _cell(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().replace("|", "\\|")


def _hidden(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    return "visibility:hidden" in style or "display:none" in style


def _inline(node) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag) or _hidden(node):
        return ""
    inner = "".join(_inline(c) for c in node.children)
    name = node.name
    if name in ("strong", "b"):
        return f"**{inner.strip()}**" if inner.strip() else ""
    if name in ("em", "i"):
        return f"*{inner.strip()}*" if inner.strip() else ""
    if name == "code":
        return f"`{inner}`"
    if name == "a":
        href = node.get("href") or ""
        return f"[{inner.strip()}]({href})" if href else inner
    if name == "img":
        return f"![{node.get('alt') or ''}]({node.get('src') or ''})"
    if name == "br":
        return "\n"
    return inner


def _table(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [_cell(_inline(td)) for td in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    has_head = bool(table.find("th"))
    head = rows[0] if has_head else [""] * width
    body = rows[1:] if has_head else rows
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _blocks(node: Tag, out: list[str], depth: int = 0) -> None:
    for child in node.children:
        if isinstance(child, NavigableString):
            if child.strip():
                out.append(child.strip())
            continue
        if not isinstance(child, Tag) or _hidden(child):
            continue
        name = child.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            out.append("#" * int(name[1]) + " " + _inline(child).strip())
        elif name == "p":
            text = _inline(child).strip()
            if text:
                out.append(text)
        elif name in ("ul", "ol"):
            items = []
            for n, li in enumerate(child.find_all("li", recursive=False), start=1):
                mark = f"{n}." if name == "ol" else "-"
                items.append("  " * depth + f"{mark} {_inline(li).strip()}")
            out.append("\n".join(items))
        elif name == "table":
            t = _table(child)
            if t:
                out.append(t)
        elif name == "pre":
            out.append("```\n" + child.get_text() + "\n```")
        elif name == "blockquote":
            out.append("\n".join("> " + line for line in _inline(child).strip().splitlines()))
        elif name in ("colgroup", "script", "style", "svg", "button"):
            continue
        else:
            _blocks(child, out, depth)


def html_to_md(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    out: list[str] = []
    _blocks(soup, out)
    return "\n\n".join(b for b in out if b.strip()) + ("\n" if out else "")


def flatten_params(params: list[dict], prefix: str = "") -> list[dict]:
    rows = []
    for p in params:
        name = f"{prefix}.{p['name']}" if prefix and p["name"] else (p["name"] or prefix + "[]")
        rows.append({**p, "name": name})
        rows += flatten_params(p.get("children") or [], name)
    return rows


def _param_table(title: str, params: list[dict]) -> list[str]:
    if not params:
        return []
    lines = [f"### {title}", "", "| Name | Type | Required | Description | Example |",
             "|---|---|---|---|---|"]
    for p in flatten_params(params):
        ex = p.get("example")
        ex = "" if ex in (None, "") or isinstance(ex, (dict, list)) else str(ex)
        lines.append(f"| {_cell(p['name'])} | {_cell(p['type'])} | {'yes' if p['required'] else ''} "
                     f"| {_cell(p['description'])} | {_cell(ex)} |")
    return lines + [""]


def page_markdown(doc: dict) -> str:
    lines = [f"# {doc['title']}", ""]
    if doc.get("breadcrumb"):
        lines += [" > ".join(doc["breadcrumb"]), ""]
    lines += [f"Source: {doc['url']}", ""]
    ep = doc.get("endpoint")
    if ep:
        target = ep.get("request_url") or ep.get("path")
        lines += [f"`{ep['method']}` `{target}`", ""]
    md = (doc.get("content") or {}).get("markdown", "").strip()
    if md:
        lines += [md, ""]
    if ep:
        lines += _param_table("Header Parameters", ep["headers"])
        lines += _param_table("Path Parameters", ep["path_params"])
        lines += _param_table("Query Parameters", ep["query"])
        lines += _param_table("Body Parameters", ep["body"])
    snippets = doc.get("snippets") or []
    if snippets:
        lines += ["## Code snippets", ""]
        for s in snippets:
            lines += [f"### {s['language']}", "", f"```{_FENCE_LANG.get(s['language'], '')}",
                      s["code"].rstrip("\n"), "```", ""]
    rendered = doc.get("responses_rendered") or {}
    if ep and (ep["responses"] or rendered):
        lines += ["## Responses", ""]
        described = {str(r["status"]): r for r in ep["responses"]}
        for status in list(rendered) + [s for s in described if s not in rendered]:
            lines += [f"### {status}", ""]
            if described.get(status, {}).get("description"):
                lines += [described[status]["description"], ""]
            body = rendered.get(status) or described.get(status, {}).get("example", "")
            lines += ["```json", body.rstrip("\n"), "```", ""]
    tryit = doc.get("tryit")
    if tryit:
        lines += ["## Try it (API Explorer)", "", f"Explorer: {tryit['url']}", "",
                  "| Group | Field | Default value |", "|---|---|---|"]
        for f in tryit.get("fields") or []:
            lines.append(f"| {_cell(f.get('group', ''))} | {_cell(f['name'])} | {_cell(str(f.get('value', '')))} |")
        lines.append("")
        if tryit.get("body_code"):
            lines += ["Request body (Code view):", "", "```json", tryit["body_code"].rstrip("\n"), "```", ""]
    return "\n".join(lines).rstrip() + "\n"


LANG_FILES = {label: f"{key}.{ext}" for label, key, ext in LANGUAGES}
