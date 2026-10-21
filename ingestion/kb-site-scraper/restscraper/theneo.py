"""Reading Theneo's published data: the page's __NEXT_DATA__ (menu + section JSON) and llms.txt.

Pure functions, no I/O. The same parsing serves discovery (menu) and the per-page
capture (the page's own transformedSection entry gives the expected counts).
"""
from __future__ import annotations

import json
import re

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_LLMS_LINK = re.compile(r"\]\(https?://[^/]+/([^)\s]+?)\.md\)")
_IMG = re.compile(r"<img\b", re.I)


def next_data(html: str) -> dict:
    """pageProps of a Theneo page. ValueError when the page carries no data (e.g. a 403 page)."""
    m = _NEXT_DATA.search(html or "")
    if not m:
        raise ValueError("page has no __NEXT_DATA__")
    data = json.loads(m.group(1))
    pp = (data.get("props") or {}).get("pageProps") or {}
    if "documentMenu" not in ((pp.get("documents") or {}).get("data") or {}):
        raise ValueError("page data has no documentMenu")
    return pp


def _doc(pp: dict) -> dict:
    return pp["documents"]["data"]


def menu_items(pp: dict) -> list[dict]:
    return list(_doc(pp)["documentMenu"].get("items") or [])


def slug_aliases(pp: dict) -> dict[str, str]:
    """Every slug Theneo knows (current and former) -> sectionId."""
    return dict(_doc(pp)["documentMenu"].get("slugs") or {})


def section_entry(pp: dict, section_id: str) -> dict | None:
    for s in _doc(pp).get("transformedSection") or []:
        if s.get("_id") == section_id or s.get("sectionId") == section_id:
            return s
    return None


def normalize_params(items: list | None) -> list[dict]:
    out = []
    for it in items or []:
        children = normalize_params((it.get("items") or []) + (it.get("complexItems") or []))
        out.append({
            "name": it.get("name") or "",
            "type": it.get("valueType") or "",
            "required": bool(it.get("isRequired")),
            "description": it.get("description") or "",
            "example": it.get("value", ""),
            "children": children,
        })
    return out


def example_from_params(params: list[dict]):
    """Rebuild the example JSON value the docs show from a parameter tree."""
    obj = {}
    for p in params:
        obj[p["name"]] = _example_value(p)
    return obj


def _example_value(p: dict):
    kids = p["children"]
    if p["type"] == "object":
        return example_from_params(kids) if kids else (p["example"] or {})
    if p["type"] == "array":
        if not kids:
            return p["example"] if isinstance(p["example"], list) else []
        if len(kids) == 1 and not kids[0]["name"]:
            return [_example_value(kids[0])]
        return [example_from_params(kids)]
    return p["example"]


def _status(code):
    try:
        return int(code)
    except (TypeError, ValueError):
        return code


def endpoint_info(entry: dict) -> dict:
    ep = entry.get("endpoints") or {}
    req = entry.get("request") or {}
    responses = []
    for r in entry.get("responses") or []:
        body = normalize_params(r.get("body"))
        responses.append({
            "status": _status(r.get("statusCode")),
            "description": r.get("description") or "",
            "content_type": r.get("contentType") or "",
            "params": body,
            "example": json.dumps(example_from_params(body), indent=2, ensure_ascii=False),
        })
    return {
        "method": (ep.get("method") or "").upper(),
        "path": ep.get("path") or "",
        "headers": normalize_params(req.get("header")),
        "path_params": normalize_params(req.get("path")),
        "query": normalize_params(req.get("query")),
        "body": normalize_params(req.get("body")),
        "code_examples": req.get("codeExamples") or [],
        "responses": responses,
    }


def is_endpoint(entry: dict | None) -> bool:
    """True when the entry documents a callable endpoint (has a request definition).
    Some endpoints have an empty path in Theneo but still render a snippet card and
    a Try-it button, so the path is not required."""
    return bool(entry and entry.get("request") is not None)


def expected_counts(entry: dict) -> dict:
    req = entry.get("request") or {}
    return {
        "header": len(req.get("header") or []),
        "query": len(req.get("query") or []),
        "path": len(req.get("path") or []),
        "body": len(req.get("body") or []),
        "responses": len(entry.get("responses") or []),
        "images": len(_IMG.findall(entry.get("description") or "")),
    }


def parse_llms(text: str) -> list[str]:
    return _LLMS_LINK.findall(text or "")
