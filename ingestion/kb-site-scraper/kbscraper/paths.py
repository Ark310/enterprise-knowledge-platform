"""Windows-safe folder and file names for the library tree."""
from __future__ import annotations

import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
# Names an article folder uses for its own files; a child page may not take them.
OWNED_NAMES = {"images", "attachments", "article.json", "article.md"}

SEGMENT_MAX = 80
FILENAME_MAX = 100


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a word boundary when one is reasonably close to the limit.
    space = cut.rfind(" ")
    if space >= limit * 0.6:
        cut = cut[:space]
    return cut


def safe_segment(title: str, limit: int = SEGMENT_MAX) -> str:
    """A single path segment derived from a page title."""
    name = _INVALID.sub("-", title or "")
    name = re.sub(r"\s+", " ", name).strip()
    name = _truncate(name, limit).rstrip(" .")
    name = name.lstrip(" ")
    if not name or set(name) <= {"-", "."}:
        name = "untitled"
    if name.split(".")[0].upper() in _RESERVED:
        name = f"{name}_"
    return name


def safe_filename(filename: str, limit: int = FILENAME_MAX) -> str:
    """A file name safe for Windows, keeping the extension when truncating."""
    name = _INVALID.sub("_", filename or "").strip().rstrip(".")
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        ext = ext[:10]
    else:
        stem, ext = name, ""
    stem = stem.strip() or "file"
    room = limit - (len(ext) + 1 if ext else 0)
    stem = stem[:max(1, room)].rstrip(" .") or "file"
    if stem.upper() in _RESERVED:
        stem = f"{stem}_"
    return f"{stem}.{ext}" if ext else stem


def unique_name(name: str, taken: set[str], suffix: str) -> str:
    """Return name, or name + ' [suffix]' when it collides (case-insensitively, as
    Windows does) with an entry in `taken`. Adds the result to `taken`."""
    candidate = name
    if candidate.lower() in taken or candidate.lower() in OWNED_NAMES:
        candidate = f"{name} [{suffix}]"
    n = 2
    while candidate.lower() in taken:
        candidate = f"{name} [{suffix}-{n}]"
        n += 1
    taken.add(candidate.lower())
    return candidate


def unique_filename(name: str, taken: set[str], prefix: str) -> str:
    """Like unique_name for files: collisions get a prefix so the extension stays."""
    candidate = name
    n = 2
    while candidate.lower() in taken:
        candidate = safe_filename(f"{prefix}_{name}" if n == 2 else f"{prefix}_{n}_{name}")
        n += 1
    taken.add(candidate.lower())
    return candidate
