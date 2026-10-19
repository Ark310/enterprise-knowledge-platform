"""Article table model + filter proxy for the main window."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont

from kbscraper.gui.theme import STATUS_COLORS, STATUS_LABELS

COLUMNS = ["Status", "Space", "Title", "Files", "Dropdowns", "Code", "Images",
           "Tries", "Time", "Problem"]
(C_STATUS, C_SPACE, C_TITLE, C_FILES, C_DROPS, C_CODE, C_IMAGES,
 C_TRIES, C_TIME, C_PROBLEM) = range(len(COLUMNS))


def _ratio(found, expected) -> str:
    if found is None and expected is None:
        return ""
    if expected in (None, ""):
        return str(found)
    return f"{found}/{expected}"


class ArticleModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._index: dict[str, int] = {}

    # ── data management ──────────────────────────────────────────────────────
    def reset(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self._index = {r["page_id"]: i for i, r in enumerate(rows)}
        self.endResetModel()

    def update_many(self, updates: dict[str, dict]) -> None:
        first = last = None
        for pid, fields in updates.items():
            i = self._index.get(pid)
            if i is None:
                self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
                self._rows.append({"page_id": pid, **fields})
                self._index[pid] = len(self._rows) - 1
                self.endInsertRows()
                continue
            self._rows[i].update(fields)
            first = i if first is None else min(first, i)
            last = i if last is None else max(last, i)
        if first is not None:
            self.dataChanged.emit(self.index(first, 0), self.index(last, len(COLUMNS) - 1))

    def row(self, i: int) -> dict:
        return self._rows[i]

    def rows(self) -> list[dict]:
        return self._rows

    def get(self, pid: str) -> dict | None:
        i = self._index.get(pid)
        return self._rows[i] if i is not None else None

    # ── Qt model API ─────────────────────────────────────────────────────────
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        col = index.column()
        status = r.get("status", "pending")
        if role == Qt.DisplayRole:
            found = r.get("found") or {}
            expected = r.get("expected") or {}
            if col == C_STATUS:
                return STATUS_LABELS.get(status, status)
            if col == C_SPACE:
                return r.get("space_name") or r.get("space_key", "")
            if col == C_TITLE:
                return r.get("title", "")
            if col == C_FILES:
                return _ratio(r.get("files"), r.get("files_expected")) if "files" in r else ""
            if col == C_DROPS:
                return _ratio(found.get("expands"), expected.get("expands")) if found else ""
            if col == C_CODE:
                return _ratio(found.get("code_blocks"), expected.get("code_blocks")) if found else ""
            if col == C_IMAGES:
                return _ratio(found.get("images"), expected.get("images")) if found else ""
            if col == C_TRIES:
                return str(r.get("attempts") or "")
            if col == C_TIME:
                d = r.get("duration_s")
                return f"{d:.1f}s" if isinstance(d, (int, float)) else ""
            if col == C_PROBLEM:
                if r.get("error") and status in ("failed", "pending"):
                    return r["error"]
                issues = r.get("issues") or []
                if issues:
                    return issues[0] + (f"  (+{len(issues) - 1} more)" if len(issues) > 1 else "")
                notes = r.get("notes") or []
                return f"Note: {notes[0]}" if notes else ""
        if role == Qt.ForegroundRole and col in (C_STATUS, C_PROBLEM):
            return QColor(STATUS_COLORS.get(status, "#1e2536"))
        if role == Qt.FontRole and col == C_STATUS:
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ToolTipRole:
            parts = [r.get("title", ""), r.get("url", ""), r.get("folder", "")]
            if r.get("error"):
                parts.append("Error: " + r["error"])
            parts += [f"• {i}" for i in r.get("issues") or []]
            parts += [f"Note: {n}" for n in r.get("notes") or []]
            return "\n".join(p for p in parts if p)
        if role == Qt.UserRole:
            return r.get("page_id")
        return None


class ArticleFilter(QSortFilterProxyModel):
    STATUS_FILTERS = {
        "All articles": None,
        "Problems (failed + warnings)": {"failed", "warning"},
        "Failed": {"failed"},
        "Warnings": {"warning"},
        "Pending / not scraped": {"pending", "missing"},
        "Running": {"running"},
        "Done": {"done"},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._statuses: set[str] | None = None
        self._spaces: set[str] | None = None
        self._text = ""
        self.setSortRole(Qt.DisplayRole)

    def set_statuses(self, statuses):
        self._statuses = statuses
        self.invalidateFilter()

    def set_spaces(self, spaces):
        self._spaces = spaces
        self.invalidateFilter()

    def set_text(self, text: str):
        self._text = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        r = self.sourceModel().row(source_row)
        if self._statuses is not None and r.get("status", "pending") not in self._statuses:
            return False
        if self._spaces is not None and r.get("space_key") not in self._spaces:
            return False
        if self._text:
            hay = " ".join([r.get("title", ""), r.get("folder", ""), r.get("error", ""),
                            " ".join(r.get("issues") or [])]).lower()
            return self._text in hay
        return True
