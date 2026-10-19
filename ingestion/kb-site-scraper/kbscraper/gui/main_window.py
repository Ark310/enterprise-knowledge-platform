"""Main window: space picker, live article table, issues, log, and run controls."""
from __future__ import annotations

import json
import os
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from kbscraper import __version__
from kbscraper.control import RunControl
from kbscraper.discovery import SiteMap
from kbscraper.gui.log_pane import LogPane
from kbscraper.gui.models import ArticleFilter, ArticleModel, COLUMNS, C_PROBLEM, C_TITLE
from kbscraper.gui.theme import PALETTE, STATUS_COLORS, STATUS_LABELS, asset_path
from kbscraper.gui.workers import AuditThread, DiscoverThread, ScrapeThread
from kbscraper.settings import PRODUCTS, Settings
from kbscraper.state import DONE, FAILED, PENDING, RUNNING, WARNING, RunState

ROLE_KEYS = Qt.UserRole + 1


def records_from_sitemap(sitemap: SiteMap, space_keys: set[str] | None = None,
                         page_ids: set[str] | None = None) -> list[dict]:
    spaces = {s.key: s for s in sitemap.spaces}
    out = []
    for a in sitemap.articles:
        if space_keys is not None and a.space_key not in space_keys:
            continue
        if page_ids is not None and a.page_id not in page_ids:
            continue
        sp = spaces[a.space_key]
        out.append({"page_id": a.page_id, "title": a.title, "space_key": a.space_key,
                    "space_name": sp.name, "product": sp.product,
                    "product_label": sp.product_label, "folder": a.folder, "url": a.url,
                    "content_type": a.content_type, "version": a.version})
    return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.sitemap: SiteMap | None = SiteMap.load()
        self.state: RunState | None = None
        state_error = ""
        rid = RunState.latest_id()
        if rid:
            try:
                self.state = RunState.load(rid)
            except Exception as exc:
                state_error = f"Could not read the last run ({rid}): {type(exc).__name__}: {exc}"
        self.control = RunControl()
        self.thread = None
        self._pending_updates: dict[str, dict] = {}
        self._counts_dirty = True
        self._run_started = 0.0
        self._run_done_at_start = 0
        self._last_audit: dict | None = None
        self._alerts: list[QMessageBox] = []

        self.setWindowTitle(f"Contoso KB Site Scraper v{__version__}")
        self.resize(1400, 880)
        ico = asset_path("scraper_icon.ico")
        if ico:
            self.setWindowIcon(QIcon(str(ico)))
        self._build_ui()
        self._populate()
        self._set_running(False)

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(300)
        self._flush_timer.timeout.connect(self._flush_updates)
        self._flush_timer.start()

        if self.sitemap is None:
            self.log("info", "No site map cached yet — loading the list of articles from help.contoso.example…")
            QTimer.singleShot(200, self.refresh_sitemap)
        else:
            self.log("info", f"Site map from {self.sitemap.discovered_at}: {len(self.sitemap.articles)} "
                             "articles. Press 'Refresh site map' to re-check the site.")
        if state_error:
            self.log("error", state_error)
            QTimer.singleShot(500, lambda: self.alert(
                "warning", "Last run could not be loaded",
                f"{state_error}\n\nResume is unavailable for that run. Use 'Audit library' to "
                "find anything missing, then 'Scrape missing from audit'."))
        if self.state and self.state.ids_with_status(PENDING, RUNNING):
            n = len(self.state.ids_with_status(PENDING, RUNNING))
            self.log("warning", f"The last run ({self.state.run_id}) did not finish — {n} article(s) "
                                "left. Press 'Resume last run' to continue it.")

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        self.setMenuWidget(self._header())
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        # Row 1: run actions
        row = QHBoxLayout()
        self.btn_start = QPushButton("▶  Start scrape")
        self.btn_start.setObjectName("Primary")
        self.btn_start.setToolTip("Re-check the site for every article, then scrape all articles "
                                  "of the ticked spaces (always a fresh copy).")
        self.btn_resume = QPushButton("⟳  Resume last run")
        self.btn_resume.setToolTip("Continue the last run from where it stopped (crash, Stop, or close).")
        self.btn_retry = QPushButton("↻  Retry problems")
        self.btn_retry.setToolTip("Re-scrape every article of the last run that failed or has warnings.")
        self.btn_pause = QPushButton("⏸  Pause")
        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("Danger")
        self.btn_audit = QPushButton("✔  Audit library")
        self.btn_audit.setToolTip("Compare the live site with the files on disk: missing articles, "
                                  "articles with warnings, and stale folders.")
        self.btn_refresh = QPushButton("Refresh site map")
        for b in (self.btn_start, self.btn_resume, self.btn_retry, self.btn_pause, self.btn_stop):
            row.addWidget(b)
        row.addSpacing(16)
        row.addWidget(self.btn_audit)
        row.addWidget(self.btn_refresh)
        row.addStretch()
        outer.addLayout(row)

        # Row 2: settings
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Workers:"))
        self.spn_workers = QSpinBox()
        self.spn_workers.setRange(1, 10)
        self.spn_workers.setValue(self.settings.workers)
        self.spn_workers.setToolTip("Parallel articles (1–10). Lowering it during a run takes effect "
                                    "immediately; raising above the run's starting count applies next run.")
        row2.addWidget(self.spn_workers)
        row2.addSpacing(12)
        self.chk_shots = QCheckBox("Screenshots (dropdowns opened)")
        self.chk_shots.setChecked(self.settings.screenshots)
        self.chk_headless = QCheckBox("Hide browser")
        self.chk_headless.setChecked(self.settings.headless)
        self.chk_headless.setToolTip("Untick to watch Chrome take the screenshots.")
        row2.addWidget(self.chk_shots)
        row2.addWidget(self.chk_headless)
        row2.addSpacing(12)
        row2.addWidget(QLabel("Output:"))
        self.txt_output = QLineEdit(self.settings.output_dir)
        self.txt_output.setReadOnly(True)
        self.txt_output.setMinimumWidth(380)
        row2.addWidget(self.txt_output, stretch=1)
        self.btn_browse = QPushButton("Change…")
        self.btn_open_out = QPushButton("Open folder")
        row2.addWidget(self.btn_browse)
        row2.addWidget(self.btn_open_out)
        outer.addLayout(row2)

        # Main split: spaces tree | tabs
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        tl = QHBoxLayout()
        lbl = QLabel("<b>Spaces</b> — tick what to scrape, click to filter")
        tl.addWidget(lbl)
        tl.addStretch()
        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        for b in (self.btn_all, self.btn_none):
            b.setFixedWidth(64)
            tl.addWidget(b)
        lv.addLayout(tl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Space", "#", "Done", "Warn", "Fail"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 5):
            self.tree.header().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lv.addWidget(self.tree)
        split.addWidget(left)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._articles_tab(), "Articles")
        self.tabs.addTab(self._issues_tab(), "Issues")
        self.log_pane = LogPane()
        self.tabs.addTab(self.log_pane, "Log")
        split.addWidget(self.tabs)
        split.setSizes([440, 960])
        outer.addWidget(split, stretch=1)

        # Progress
        prow = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.lbl_counts = QLabel("Idle")
        self.lbl_counts.setTextFormat(Qt.RichText)
        prow.addWidget(self.progress, stretch=2)
        prow.addWidget(self.lbl_counts, stretch=3)
        outer.addLayout(prow)

        # Signals
        self.btn_start.clicked.connect(self.start_scrape)
        self.btn_resume.clicked.connect(self.resume_run)
        self.btn_retry.clicked.connect(self.retry_problems)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.stop_run)
        self.btn_audit.clicked.connect(self.run_audit)
        self.btn_refresh.clicked.connect(self.refresh_sitemap)
        self.btn_browse.clicked.connect(self.change_output)
        self.btn_open_out.clicked.connect(lambda: self._open_path(Path(self.settings.output_dir)))
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        self.spn_workers.valueChanged.connect(self._workers_changed)
        self.chk_shots.toggled.connect(self._save_settings)
        self.chk_headless.toggled.connect(self._save_settings)
        self.tree.itemSelectionChanged.connect(self._tree_filter)
        self.tree.itemChanged.connect(self._tree_item_changed)

    def _header(self) -> QWidget:
        h = QFrame()
        h.setObjectName("Header")
        row = QHBoxLayout(h)
        row.setContentsMargins(12, 6, 12, 6)
        logo = asset_path("contoso_logo.png")
        if logo:
            pm = QPixmap(str(logo))
            if not pm.isNull():
                lbl = QLabel()
                lbl.setPixmap(pm.scaledToHeight(26, Qt.SmoothTransformation))
                row.addWidget(lbl)
        t = QLabel("KB Site Scraper — help.contoso.example")
        t.setStyleSheet(f"font-size:12pt; font-weight:600; color:{PALETTE['text']}; background:transparent;")
        row.addWidget(t)
        row.addStretch()
        v = QLabel(f"v{__version__}")
        v.setStyleSheet(f"color:white; background:{PALETTE['brand']}; border-radius:8px; padding:2px 8px;")
        row.addWidget(v)
        return h

    def _articles_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Show:"))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(list(ArticleFilter.STATUS_FILTERS))
        fr.addWidget(self.cmb_status)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search title, folder or error…")
        fr.addWidget(self.txt_search, stretch=1)
        self.lbl_shown = QLabel("")
        self.lbl_shown.setObjectName("Muted")
        fr.addWidget(self.lbl_shown)
        v.addLayout(fr)

        self.model = ArticleModel(self)
        self.proxy = ArticleFilter(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        for c in range(len(COLUMNS)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(C_TITLE, QHeaderView.Interactive)
        hh.setSectionResizeMode(C_PROBLEM, QHeaderView.Stretch)
        self.table.setColumnWidth(C_TITLE, 320)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.table.doubleClicked.connect(lambda idx: self._open_selected("folder"))
        self.table.selectionModel().selectionChanged.connect(self._show_details)

        self.details = QTextBrowser()
        self.details.setOpenLinks(False)
        self.details.anchorClicked.connect(self._detail_link)
        self.details.setMaximumHeight(170)

        sp = QSplitter(Qt.Vertical)
        sp.addWidget(self.table)
        sp.addWidget(self.details)
        sp.setSizes([600, 150])
        v.addWidget(sp, stretch=1)

        self.cmb_status.currentTextChanged.connect(
            lambda t: (self.proxy.set_statuses(ArticleFilter.STATUS_FILTERS[t]), self._update_shown()))
        self.txt_search.textChanged.connect(lambda t: (self.proxy.set_text(t), self._update_shown()))
        return w

    def _issues_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        top = QHBoxLayout()
        self.lbl_issues = QLabel("Every failure, warning, note and audit finding. Double-click a row "
                                 "to jump to the article.")
        self.lbl_issues.setObjectName("Muted")
        top.addWidget(self.lbl_issues, stretch=1)
        self.btn_scrape_missing = QPushButton("Scrape missing from audit")
        self.btn_scrape_missing.setEnabled(False)
        self.btn_scrape_missing.clicked.connect(self.scrape_missing)
        self.btn_export = QPushButton("Export issues…")
        self.btn_export.clicked.connect(self.export_issues)
        top.addWidget(self.btn_scrape_missing)
        top.addWidget(self.btn_export)
        v.addLayout(top)
        self.issues = QTableWidget(0, 4)
        self.issues.setHorizontalHeaderLabels(["Kind", "Space", "Article", "Detail"])
        self.issues.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.issues.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.issues.setColumnWidth(2, 300)
        self.issues.verticalHeader().setVisible(False)
        self.issues.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.issues.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.issues.setSortingEnabled(True)
        self.issues.cellDoubleClicked.connect(self._issue_jump)
        v.addWidget(self.issues)
        self.tabs_issue_dirty = True
        return w

    # ── population ───────────────────────────────────────────────────────────
    def _populate(self):
        """(Re)build tree + table from the site map, overlaying the latest run."""
        rows: list[dict] = []
        out = Path(self.settings.output_dir)
        # Only overlay a run that wrote into the output folder currently selected.
        run = {}
        if self.state and Path(self.state.meta.get("output_dir", self.settings.output_dir)) == out:
            run = self.state.articles
        if self.sitemap:
            for rec in records_from_sitemap(self.sitemap):
                r = dict(rec)
                if rec["page_id"] in run:
                    prev = run[rec["page_id"]]
                    r.update({k: v for k, v in prev.items() if k not in ("folder", "title", "url")})
                    if prev.get("folder") != rec["folder"]:
                        r["status"] = "missing" if not (out / rec["folder"] / "article.json").exists() \
                            else r.get("status", PENDING)
                else:
                    r["status"] = "done" if (out / rec["folder"] / "article.json").exists() else "missing"
                    if r["status"] == "done":
                        r["notes"] = ["Saved by an earlier run"]
                rows.append(r)
        self.model.reset(rows)
        self._build_tree()
        self._counts_dirty = True
        self._refresh_counts()
        self._update_shown()
        self.tabs_issue_dirty = True
        self._rebuild_issues()

    def _build_tree(self):
        self.tree.blockSignals(True)
        checked_before = self._checked_spaces() if self.tree.topLevelItemCount() else None
        self.tree.clear()
        root = QTreeWidgetItem(["All spaces"])
        root.setData(0, ROLE_KEYS, None)
        root.setFlags(root.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
        root.setCheckState(0, Qt.Checked)
        self.tree.addTopLevelItem(root)
        self._space_items: dict[str, QTreeWidgetItem] = {}
        self._product_items: dict[str, QTreeWidgetItem] = {}
        if self.sitemap:
            for product, label in PRODUCTS.items():
                spaces = [s for s in self.sitemap.spaces if s.product == product]
                if not spaces:
                    continue
                pi = QTreeWidgetItem([label])
                pi.setData(0, ROLE_KEYS, {s.key for s in spaces})
                pi.setFlags(pi.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                root.addChild(pi)
                self._product_items[product] = pi
                for s in spaces:
                    si = QTreeWidgetItem([f"{s.name}  ({s.key})"])
                    si.setData(0, ROLE_KEYS, {s.key})
                    si.setFlags(si.flags() | Qt.ItemIsUserCheckable)
                    on = checked_before is None or s.key in checked_before
                    si.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
                    if s.error:
                        si.setForeground(0, Qt.red)
                        si.setToolTip(0, f"Discovery failed: {s.error}")
                    pi.addChild(si)
                    self._space_items[s.key] = si
        root.setExpanded(True)
        self.tree.blockSignals(False)

    def _checked_spaces(self) -> set[str]:
        return {k for k, it in getattr(self, "_space_items", {}).items()
                if it.checkState(0) == Qt.Checked}

    def _check_all(self, on: bool):
        root = self.tree.topLevelItem(0)
        if root:
            root.setCheckState(0, Qt.Checked if on else Qt.Unchecked)

    def _tree_item_changed(self, item, col):
        self._update_buttons()

    def _tree_filter(self):
        items = self.tree.selectedItems()
        keys = items[0].data(0, ROLE_KEYS) if items else None
        self.proxy.set_spaces(set(keys) if keys else None)
        self._update_shown()

    def _update_shown(self):
        self.lbl_shown.setText(f"{self.proxy.rowCount()} of {self.model.rowCount()} shown")

    # ── counts / progress ────────────────────────────────────────────────────
    def _refresh_counts(self):
        if not self._counts_dirty:
            return
        self._counts_dirty = False
        per: dict[str, dict] = {}
        tot = {"done": 0, "warning": 0, "failed": 0, "pending": 0, "running": 0, "missing": 0}
        for r in self.model.rows():
            st = r.get("status", PENDING)
            c = per.setdefault(r["space_key"], {"n": 0, "done": 0, "warning": 0, "failed": 0})
            c["n"] += 1
            if st in c:
                c[st] += 1
            tot[st] = tot.get(st, 0) + 1
        for key, it in getattr(self, "_space_items", {}).items():
            c = per.get(key, {"n": 0, "done": 0, "warning": 0, "failed": 0})
            self._set_tree_counts(it, c)
        for product, pi in getattr(self, "_product_items", {}).items():
            agg = {"n": 0, "done": 0, "warning": 0, "failed": 0}
            for i in range(pi.childCount()):
                for k in agg:
                    agg[k] += per.get(next(iter(pi.child(i).data(0, ROLE_KEYS))), {}).get(k, 0)
            self._set_tree_counts(pi, agg)
        root = self.tree.topLevelItem(0)
        if root:
            self._set_tree_counts(root, {"n": self.model.rowCount(), "done": tot["done"],
                                         "warning": tot["warning"], "failed": tot["failed"]})

        running = self._is_running()
        if running and self.state:
            c = self.state.counts()
            total = c["total"]
            finished = c[DONE] + c[WARNING] + c[FAILED]
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(finished)
            rate = ""
            elapsed = time.monotonic() - self._run_started
            made = finished - self._run_done_at_start
            if made > 0 and elapsed > 5:
                per_min = made / (elapsed / 60)
                left = (total - finished) / per_min if per_min else 0
                rate = f" · {per_min:.1f}/min · ETA {_fmt_minutes(left)}"
            state = "PAUSED · " if self.control.paused else ""
            self.lbl_counts.setText(
                f"<b>{state}{finished}/{total}</b> · "
                f"<span style='color:{STATUS_COLORS['done']}'>done {c[DONE]}</span> · "
                f"<span style='color:{STATUS_COLORS['warning']}'>warnings {c[WARNING]}</span> · "
                f"<span style='color:{STATUS_COLORS['failed']}'>failed {c[FAILED]}</span> · "
                f"running {c[RUNNING]} · pending {c[PENDING]}{rate}")
        else:
            self.progress.setRange(0, max(1, self.model.rowCount()))
            self.progress.setValue(tot["done"] + tot["warning"])
            self.lbl_counts.setText(
                f"Library: <b>{tot['done'] + tot['warning']}/{self.model.rowCount()}</b> scraped · "
                f"<span style='color:{STATUS_COLORS['warning']}'>warnings {tot['warning']}</span> · "
                f"<span style='color:{STATUS_COLORS['failed']}'>failed {tot['failed']}</span> · "
                f"not scraped {tot['missing'] + tot['pending']}")
        self._update_buttons()

    @staticmethod
    def _set_tree_counts(item, c):
        item.setText(1, str(c["n"]))
        item.setText(2, str(c["done"]))
        item.setText(3, str(c["warning"]) if c["warning"] else "")
        item.setText(4, str(c["failed"]) if c["failed"] else "")
        item.setForeground(3, Qt.darkYellow)
        item.setForeground(4, Qt.red)

    def _flush_updates(self):
        if self._pending_updates:
            updates, self._pending_updates = self._pending_updates, {}
            self.model.update_many(updates)
            self._counts_dirty = True
            self.tabs_issue_dirty = True
            self._show_details()
        if self._counts_dirty:
            self._refresh_counts()

    # ── run lifecycle ────────────────────────────────────────────────────────
    def _is_running(self) -> bool:
        return self.thread is not None and self.thread.isRunning()

    def _set_running(self, running: bool):
        for w in (self.btn_audit, self.btn_refresh, self.btn_browse, self.chk_shots,
                  self.chk_headless):
            w.setEnabled(not running)
        self.btn_pause.setEnabled(running and isinstance(self.thread, ScrapeThread))
        self.btn_stop.setEnabled(running and isinstance(self.thread, ScrapeThread))
        self.btn_pause.setText("⏸  Pause")
        self._update_buttons()

    def _update_buttons(self):
        running = self._is_running()
        has_pending = bool(self.state and self.state.ids_with_status(PENDING, RUNNING))
        has_problems = bool(self.state and self.state.ids_with_status(FAILED, WARNING))
        self.btn_start.setEnabled(not running and bool(self._checked_spaces()))
        self.btn_resume.setEnabled(not running and has_pending)
        self.btn_retry.setEnabled(not running and has_problems)
        self.btn_scrape_missing.setEnabled(not running and bool(
            self._last_audit and self._last_audit.get("missing")))

    def refresh_sitemap(self, then=None):
        if self._is_running():
            return
        self.log("info", "Discovering every space and article on help.contoso.example…")
        t = DiscoverThread(self._settings_from_ui())
        t.log.connect(self.log)
        t.failed.connect(lambda e: self.alert("error", "Could not load the site map",
                                              f"{e}\n\nCheck the network connection and try again."))

        def done(sm):
            self.thread = None
            self._set_running(False)
            if sm is None:
                return
            self.sitemap = sm
            failed = [s for s in sm.spaces if s.error]
            self.log("info", f"Site map: {len(sm.spaces)} spaces, {len(sm.articles)} articles"
                             + (f" — {len(failed)} space(s) FAILED to list" if failed else ""))
            if failed:
                self.alert("warning", "Some spaces could not be listed",
                           "\n".join(f"{s.key}: {s.error}" for s in failed) +
                           "\n\nTheir articles are not in the list. Press 'Refresh site map' to try again.")
            self._populate()
            if then:
                then(sm)
        t.done.connect(done)
        self.thread = t
        self._set_running(True)
        self.lbl_counts.setText("Loading the site map…")
        t.start()

    def start_scrape(self):
        spaces = self._checked_spaces()
        if not spaces:
            return
        est = sum(1 for r in self.model.rows() if r["space_key"] in spaces)
        if QMessageBox.question(
                self, "Start scrape",
                f"Scrape {len(spaces)} space(s) — about {est} articles — into\n{self.settings.output_dir}\n\n"
                "The site is re-checked first so new articles are included. Existing article files "
                "are overwritten with a fresh copy.") != QMessageBox.Yes:
            return
        if self.state and self.state.ids_with_status(PENDING, RUNNING):
            if QMessageBox.question(
                    self, "Unfinished run",
                    "The last run still has unfinished articles. Start a NEW run anyway?\n\n"
                    "(Choose No and press 'Resume last run' to continue the old one.)") != QMessageBox.Yes:
                return

        def go(sm: SiteMap):
            records = records_from_sitemap(sm, space_keys=spaces)
            if not records:
                self.alert("warning", "Nothing to scrape", "The selected spaces have no articles.")
                return
            s = self._settings_from_ui()
            self.state = RunState.create(records, {"spaces": sorted(spaces), "output_dir": s.output_dir,
                                                   "kind": "full"})
            self._populate()
            self._launch([r["page_id"] for r in records])
        self.refresh_sitemap(then=go)

    def resume_run(self):
        if not self.state:
            return
        ids = self.state.ids_with_status(PENDING, RUNNING)
        for pid in ids:
            self.state.update(pid, status=PENDING)
        self.log("info", f"Resuming run {self.state.run_id}: {len(ids)} article(s) left.")
        self._launch(ids)

    def retry_problems(self):
        if not self.state:
            return
        ids = self.state.ids_with_status(FAILED, WARNING) + self.state.ids_with_status(PENDING, RUNNING)
        self._retry_ids(ids)

    def _retry_ids(self, ids: list[str]):
        if not ids or self._is_running():
            return
        if self.state is None:
            self.state = RunState.create([], {"kind": "retry", "output_dir": self.settings.output_dir})
        missing = [pid for pid in ids if pid not in self.state.articles]
        if missing and self.sitemap:
            for rec in records_from_sitemap(self.sitemap, page_ids=set(missing)):
                self.state.update(rec["page_id"], **rec)
        for pid in ids:
            if pid in self.state.articles:
                self.state.update(pid, status=PENDING, attempts=0, error="", issues=[])
        ids = [pid for pid in ids if pid in self.state.articles]
        self.log("info", f"Retrying {len(ids)} article(s) in run {self.state.run_id}.")
        self._pending_updates.update({pid: dict(self.state.articles[pid]) for pid in ids})
        self._launch(ids)

    def _launch(self, ids: list[str]):
        if not ids:
            self.alert("info", "Nothing to do", "There are no articles left to scrape in this run.")
            return
        s = self._settings_from_ui()
        s.save()
        self.settings = s
        self.control = RunControl()
        c = self.state.counts()
        self._run_done_at_start = c[DONE] + c[WARNING] + c[FAILED]
        self._run_started = time.monotonic()
        t = ScrapeThread(self.state, ids, s, self.control, self.sitemap)
        t.log.connect(self.log)
        t.article.connect(self._on_article)
        t.progress.connect(lambda _c: setattr(self, "_counts_dirty", True))
        t.alert.connect(self._on_engine_alert)
        t.finished_report.connect(self._on_finished)
        self.thread = t
        self._set_running(True)
        self.tabs.setCurrentIndex(0)
        t.start()

    def _on_article(self, rec: dict):
        self._pending_updates[rec["page_id"]] = rec

    def _on_engine_alert(self, severity, title, body):
        if self.control.paused:
            self.btn_pause.setText("▶  Resume")
        self.alert(severity, title, body)

    def _on_finished(self, report: dict):
        self._flush_updates()
        if self.thread is not None:
            self.thread.wait(3000)
        self.thread = None
        self._set_running(False)
        self._counts_dirty = True
        self._refresh_counts()
        if report.get("aborted") or report.get("crashed"):
            return
        c = report.get("counts") or (self.state.counts() if self.state else {})
        audit = report.get("audit")
        if audit:
            self._last_audit = audit
        self.tabs_issue_dirty = True
        self._rebuild_issues()
        if self.control.cancelled:
            self.log("warning", f"Run stopped. {c.get(PENDING, 0)} article(s) left — "
                                "'Resume last run' continues it.")
            return
        left = c.get(PENDING, 0) + c.get(RUNNING, 0)
        problems = c.get(FAILED, 0) + c.get(WARNING, 0) + left
        msg = (f"Done: {c.get(DONE, 0)}   Warnings: {c.get(WARNING, 0)}   Failed: {c.get(FAILED, 0)}"
               + (f"   NOT FINISHED: {left}" if left else "")
               + f"   (in {_fmt_minutes(report.get('elapsed_s', 0) / 60)})")
        if left:
            msg += "\n\nSome articles were never finished — press 'Resume last run'."
        if audit:
            msg += (f"\n\nLibrary audit: {audit['on_disk']} article(s) on disk for "
                    f"{audit['live_articles']} live — {len(audit['missing'])} missing, "
                    f"{len(audit['stale'])} stale folder(s).")
        if problems or (audit and audit["missing"]):
            msg += "\n\nSee the Issues tab for every problem. 'Retry problems' re-scrapes them."
            self.alert("warning", "Scrape finished — some items need attention", msg)
        else:
            self.alert("info", "Scrape finished — everything captured", msg)

    def toggle_pause(self):
        if not isinstance(self.thread, ScrapeThread):
            return
        if self.control.paused:
            self.control.resume()
            self.btn_pause.setText("⏸  Pause")
            self.log("info", "Resumed.")
        else:
            self.control.pause()
            self.btn_pause.setText("▶  Resume")
            self.log("info", "Paused — articles already in progress will finish first.")
        self._counts_dirty = True

    def stop_run(self):
        if isinstance(self.thread, ScrapeThread) and self.thread.isRunning():
            self.log("warning", "Stopping — in-progress articles are put back to pending.")
            self.control.cancel()
            self.btn_stop.setEnabled(False)
            self.btn_pause.setEnabled(False)

    def run_audit(self):
        if self._is_running():
            return
        self.log("info", "Auditing the library against the live site…")
        t = AuditThread(self._settings_from_ui())
        t.log.connect(self.log)

        def done(sm, result):
            self.thread = None
            self._set_running(False)
            if sm is None:
                self.alert("error", "Audit failed", str(result))
                return
            self.sitemap = sm
            self._last_audit = result
            self._populate()
            a = result
            self.log("info", f"Audit: {a['on_disk']} on disk / {a['live_articles']} live · "
                             f"{len(a['missing'])} missing · {len(a['warnings'])} with warnings · "
                             f"{len(a['stale'])} stale · {len(a['unreadable'])} unreadable")
            self.tabs.setCurrentIndex(1)
            bad = len(a["missing"]) + len(a["warnings"]) + len(a["unreadable"])
            self.alert("warning" if bad else "info", "Library audit",
                       f"Live articles: {a['live_articles']}\nOn disk: {a['on_disk']}\n"
                       f"Missing: {len(a['missing'])}\nWith warnings: {len(a['warnings'])}\n"
                       f"Stale folders (page moved/renamed/deleted): {len(a['stale'])}\n"
                       f"Unreadable article.json: {len(a['unreadable'])}"
                       + ("\n\nUse 'Scrape missing from audit' on the Issues tab." if a["missing"] else ""))
        t.done.connect(done)
        self.thread = t
        self._set_running(True)
        self.lbl_counts.setText("Auditing…")
        t.start()

    def scrape_missing(self):
        if not self._last_audit:
            return
        self._retry_ids([m["page_id"] for m in self._last_audit.get("missing", [])])

    # ── issues tab ───────────────────────────────────────────────────────────
    def _issue_rows(self) -> list[tuple[str, str, str, str, str]]:
        rows = []
        for r in self.model.rows():
            st = r.get("status")
            space = r.get("space_name") or r.get("space_key", "")
            if st == FAILED:
                rows.append(("Failed", space, r.get("title", ""), r.get("error", ""), r["page_id"]))
            elif st == PENDING and r.get("error"):
                rows.append(("Retrying", space, r.get("title", ""), r["error"], r["page_id"]))
            for i in r.get("issues") or []:
                rows.append(("Warning", space, r.get("title", ""), i, r["page_id"]))
            for n in r.get("notes") or []:
                if n != "Saved by an earlier run":
                    rows.append(("Note", space, r.get("title", ""), n, r["page_id"]))
        a = self._last_audit or {}
        for m in a.get("missing", []):
            rows.append(("Audit: missing", m.get("space_key", ""), m.get("title", ""),
                         f"Not on disk at {m.get('folder')}", m.get("page_id", "")))
        for s in a.get("stale", []):
            rows.append(("Audit: stale", s.get("space_key", ""), s.get("title", ""),
                         f"{s.get('folder')} — {s.get('reason')}", s.get("page_id", "")))
        for u in a.get("unreadable", []):
            rows.append(("Audit: unreadable", "", u.get("path", ""), u.get("error", ""), ""))
        return rows

    def _rebuild_issues(self):
        if not self.tabs_issue_dirty:
            return
        self.tabs_issue_dirty = False
        rows = self._issue_rows()
        self.issues.setSortingEnabled(False)
        self.issues.setRowCount(len(rows))
        colors = {"Failed": STATUS_COLORS["failed"], "Warning": STATUS_COLORS["warning"],
                  "Retrying": STATUS_COLORS["running"]}
        for i, (kind, space, title, detail, pid) in enumerate(rows):
            for j, val in enumerate((kind, space, title, detail)):
                it = QTableWidgetItem(val)
                it.setData(Qt.UserRole, pid)
                it.setToolTip(detail if j == 3 else val)
                if j == 0:
                    it.setForeground(Qt.GlobalColor.black)
                    if kind in colors:
                        from PySide6.QtGui import QColor
                        it.setForeground(QColor(colors[kind]))
                self.issues.setItem(i, j, it)
        self.issues.setSortingEnabled(True)
        n_fail = sum(1 for r in rows if r[0] == "Failed")
        n_warn = sum(1 for r in rows if r[0] == "Warning")
        self.tabs.setTabText(1, f"Issues ({len(rows)})" if rows else "Issues")
        self.lbl_issues.setText(f"{n_fail} failed · {n_warn} warning(s) · {len(rows)} row(s) total. "
                                "Double-click a row to jump to the article.")

    def _issue_jump(self, row, col):
        pid = self.issues.item(row, 0).data(Qt.UserRole)
        if not pid:
            return
        self.cmb_status.setCurrentIndex(0)
        self.txt_search.clear()
        self.tree.clearSelection()
        src = self.model._index.get(pid)
        if src is None:
            return
        idx = self.proxy.mapFromSource(self.model.index(src, 0))
        self.tabs.setCurrentIndex(0)
        self.table.selectRow(idx.row())
        self.table.scrollTo(idx)

    def export_issues(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export issues", str(Path.home() / "kb_issues.csv"),
                                              "CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Kind", "Space", "Article", "Detail", "Page ID"])
            w.writerows(self._issue_rows())
        self.log("info", f"Issues exported to {path}")

    # ── details / context menu ───────────────────────────────────────────────
    def _selected_rows(self) -> list[dict]:
        rows = []
        for idx in self.table.selectionModel().selectedRows():
            src = self.proxy.mapToSource(idx)
            rows.append(self.model.row(src.row()))
        return rows

    def _show_details(self, *_):
        rows = self._selected_rows()
        if not rows:
            self.details.setHtml("<span style='color:#6b7480'>Select an article to see its details.</span>")
            return
        r = rows[0]
        folder = Path(self.settings.output_dir) / r.get("folder", "")
        st = r.get("status", PENDING)
        html = [f"<b>{_esc(r.get('title', ''))}</b> &nbsp; "
                f"<span style='color:{STATUS_COLORS.get(st, '#000')}'><b>{STATUS_LABELS.get(st, st)}</b></span>"
                f" &nbsp; <a href='open:folder'>Open folder</a> · <a href='open:md'>Open article.md</a>"
                f" · <a href='open:site'>Open on site</a> · <a href='open:retry'>Retry this article</a>",
                f"<br><span style='color:#6b7480'>{_esc(str(folder))}</span>"]
        if r.get("error"):
            html.append(f"<br><span style='color:{STATUS_COLORS['failed']}'>Error: {_esc(r['error'])}</span>")
        for i in r.get("issues") or []:
            html.append(f"<br><span style='color:{STATUS_COLORS['warning']}'>• {_esc(i)}</span>")
        for n in r.get("notes") or []:
            html.append(f"<br><span style='color:#6b7480'>Note: {_esc(n)}</span>")
        if r.get("found"):
            f, e = r["found"], r.get("expected") or {}
            html.append(f"<br>Captured: {f.get('expands', 0)}/{e.get('expands', 0)} dropdowns · "
                        f"{f.get('code_blocks', 0)}/{e.get('code_blocks', 0)} code blocks · "
                        f"{f.get('images', 0)}/{e.get('images', 0)} images · "
                        f"{f.get('videos', 0)}/{e.get('videos', 0)} videos · {f.get('tables', 0)} tables · "
                        f"{r.get('files', 0)}/{r.get('files_expected', 0)} files downloaded · "
                        f"{r.get('screenshots', 0)} screenshot(s) · {r.get('attempts', 0)} attempt(s)")
        self.details.setHtml("".join(html))

    def _detail_link(self, url: QUrl):
        self._open_selected(url.toString().split(":", 1)[1])

    def _open_selected(self, what: str):
        rows = self._selected_rows()
        if not rows:
            return
        r = rows[0]
        folder = Path(self.settings.output_dir) / r.get("folder", "")
        if what == "folder":
            self._open_path(folder if folder.exists() else folder.parent)
        elif what == "md":
            self._open_path(folder / "article.md")
        elif what == "site":
            webbrowser.open(r.get("url", ""))
        elif what == "retry":
            self._retry_ids([x["page_id"] for x in rows])

    def _table_menu(self, pos):
        rows = self._selected_rows()
        if not rows:
            return
        m = QMenu(self)
        m.addAction("Open folder", lambda: self._open_selected("folder"))
        m.addAction("Open article.md", lambda: self._open_selected("md"))
        m.addAction("Open on site", lambda: self._open_selected("site"))
        m.addSeparator()
        a = m.addAction(f"Retry {len(rows)} selected article(s)", lambda: self._open_selected("retry"))
        a.setEnabled(not self._is_running())
        m.addAction("Copy problem text", lambda: self._copy_problem(rows))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_problem(self, rows):
        from PySide6.QtWidgets import QApplication
        lines = []
        for r in rows:
            lines.append(f"{r.get('title')} ({r.get('url')})")
            if r.get("error"):
                lines.append("  Error: " + r["error"])
            lines += [f"  - {i}" for i in r.get("issues") or []]
        QApplication.clipboard().setText("\n".join(lines))

    # ── settings ─────────────────────────────────────────────────────────────
    def _settings_from_ui(self) -> Settings:
        s = Settings.load()
        s.workers = self.spn_workers.value()
        s.screenshots = self.chk_shots.isChecked()
        s.headless = self.chk_headless.isChecked()
        s.output_dir = self.txt_output.text()
        return s

    def _save_settings(self, *_):
        self.settings = self._settings_from_ui()
        self.settings.save()

    def _workers_changed(self, v: int):
        self._save_settings()
        if isinstance(self.thread, ScrapeThread) and self.thread.isRunning():
            self.control.target_workers = v
            started = self.thread.settings.workers
            eff = min(v, started)
            self.log("info", f"Workers set to {eff} (live)" +
                     (f" — this run started with {started}, more apply next run" if v > started else ""))

    def change_output(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.settings.output_dir)
        if d:
            self.txt_output.setText(str(Path(d)))
            self._save_settings()
            self._populate()

    # ── misc ─────────────────────────────────────────────────────────────────
    def log(self, level: str, msg: str):
        self.log_pane.emit_log(level, msg)

    def alert(self, severity: str, title: str, body: str):
        icon = {"error": QMessageBox.Critical, "warning": QMessageBox.Warning}.get(
            severity, QMessageBox.Information)
        box = QMessageBox(icon, title, body, QMessageBox.Ok, self)
        box.setWindowModality(Qt.NonModal)
        box.show()
        self._alerts = [b for b in self._alerts if b.isVisible()] + [box]
        self.log("error" if severity == "error" else "warning" if severity == "warning" else "info",
                 f"[{title}] {body.splitlines()[0] if body else ''}")

    @staticmethod
    def _open_path(p: Path):
        if p.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def closeEvent(self, event):
        if self._is_running():
            if QMessageBox.question(self, "Quit?", "A job is running. Stop it and quit?\n\n"
                                    "Progress is saved — 'Resume last run' continues it next time.") \
                    != QMessageBox.Yes:
                event.ignore()
                return
            self.control.cancel()
            self.thread.wait(20000)
        if self.state:
            try:
                self.state.compact()
            except Exception:
                pass
        event.accept()


def _esc(s: str) -> str:
    import html
    return html.escape(s or "")


def _fmt_minutes(m: float) -> str:
    if m < 1:
        return f"{max(0, int(m * 60))}s"
    h, mm = divmod(int(m), 60)
    return f"{h}h {mm}m" if h else f"{mm}m"
