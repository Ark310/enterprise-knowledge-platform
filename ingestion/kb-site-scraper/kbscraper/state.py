"""Crash-safe run tracking.

Each run lives in state/runs/<run_id>/: manifest.json (compacted snapshot) plus
journal.jsonl (one line per article status change, appended immediately). Loading a
run replays the journal over the manifest, so a crash or a killed process loses at
most the line being written. Resume = continue a run's pending articles; Retry =
re-queue its failed (and optionally warning) articles in the same run record.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from kbscraper.settings import RUNS_DIR

PENDING, RUNNING, DONE, WARNING, FAILED = "pending", "running", "done", "warning", "failed"
FINAL = {DONE, WARNING, FAILED}


class RunState:
    def __init__(self, run_id: str, folder: Path):
        self.run_id = run_id
        self.folder = folder
        self.meta: dict = {}
        self.articles: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._journal_fh = None
        self._since_compact = 0
        self._last_compact = time.monotonic()

    # ── creation / loading ───────────────────────────────────────────────────
    @classmethod
    def create(cls, articles: list[dict], meta: dict, runs_dir: Path = RUNS_DIR) -> "RunState":
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = runs_dir / run_id
        n = 2
        while folder.exists():
            folder = runs_dir / f"{run_id}-{n}"
            n += 1
        folder.mkdir(parents=True)
        st = cls(folder.name, folder)
        st.meta = {"run_id": st.run_id, "created_at": datetime.now().isoformat(timespec="seconds"),
                   "status": "running", **meta}
        for a in articles:
            st.articles[a["page_id"]] = {**a, "status": PENDING, "attempts": 0,
                                         "issues": [], "error": ""}
        st.compact()
        (runs_dir / "latest.txt").write_text(st.run_id, encoding="utf-8")
        return st

    @classmethod
    def load(cls, run_id: str, runs_dir: Path = RUNS_DIR) -> "RunState":
        folder = runs_dir / run_id
        st = cls(run_id, folder)
        data = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        st.meta = data.get("meta", {})
        st.articles = data.get("articles", {})
        journal = folder / "journal.jsonl"
        if journal.exists():
            for line in journal.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue      # a torn final line from a hard kill
                if entry.get("_meta"):
                    st.meta.update(entry["_meta"])
                    continue
                pid = entry.pop("page_id", None)
                if pid in st.articles:
                    st.articles[pid].update(entry)
                elif pid:
                    st.articles[pid] = entry
        return st

    @staticmethod
    def latest_id(runs_dir: Path = RUNS_DIR) -> str | None:
        try:
            rid = (runs_dir / "latest.txt").read_text(encoding="utf-8").strip()
            return rid if (runs_dir / rid / "manifest.json").exists() else None
        except OSError:
            return None

    # ── updates ──────────────────────────────────────────────────────────────
    def update(self, page_id: str, **fields) -> dict:
        with self._lock:
            rec = self.articles.setdefault(page_id, {"page_id": page_id})
            rec.update(fields)
            self._append({"page_id": page_id, **fields})
            self._since_compact += 1
            if self._since_compact >= 100 or time.monotonic() - self._last_compact > 30:
                self._compact_locked()
            return dict(rec)

    def set_meta(self, **fields) -> None:
        with self._lock:
            self.meta.update(fields)
            self._append({"_meta": fields})

    def _append(self, entry: dict) -> None:
        try:
            if self._journal_fh is None:
                self._journal_fh = open(self.folder / "journal.jsonl", "a", encoding="utf-8")
            self._journal_fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._journal_fh.flush()
            os.fsync(self._journal_fh.fileno())
        except OSError:
            # Keep the in-memory record; the next successful compaction persists it.
            self._journal_fh = None

    def compact(self) -> None:
        with self._lock:
            self._compact_locked()

    def _compact_locked(self) -> None:
        """Write the manifest durably, THEN truncate the journal. Never raises: a
        failed compaction (e.g. antivirus holding the file) just keeps the journal,
        which load() replays."""
        tmp = self.folder / "manifest.json.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"meta": self.meta, "articles": self.articles}, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(5):
                try:
                    os.replace(tmp, self.folder / "manifest.json")
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.2 * (attempt + 1))
            if self._journal_fh is not None:
                self._journal_fh.close()
                self._journal_fh = None
            (self.folder / "journal.jsonl").write_text("", encoding="utf-8")
        except OSError:
            return
        self._since_compact = 0
        self._last_compact = time.monotonic()

    def close(self) -> None:
        self.compact()

    # ── queries ──────────────────────────────────────────────────────────────
    def ids_with_status(self, *statuses: str) -> list[str]:
        return [pid for pid, r in self.articles.items() if r.get("status") in statuses]

    def counts(self) -> dict:
        c = {PENDING: 0, RUNNING: 0, DONE: 0, WARNING: 0, FAILED: 0}
        for r in self.articles.values():
            c[r.get("status", PENDING)] = c.get(r.get("status", PENDING), 0) + 1
        c["total"] = len(self.articles)
        return c
