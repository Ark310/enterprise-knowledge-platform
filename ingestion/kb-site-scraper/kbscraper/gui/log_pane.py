"""Buffered, colorized log widget (ported from the Knowledge Base scraper, bug-144 fix).

emit_log() only buffers; a 250ms timer flushes with repaints disabled, so a fast run
can never freeze the window with per-line appends. Every line is also written to
the 'kbscraper' logger (and from there to state/logs/).
"""
from __future__ import annotations

import html
import logging
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit

log = logging.getLogger("kbscraper")
_COLORS = {"error": "#c62828", "warning": "#c77700", "info": "#1e2536"}


class LogPane(QPlainTextEdit):
    def __init__(self, max_lines: int = 5000, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)
        self.setFont(QFont("Consolas", 9))
        self._buf: list[tuple[str, str, str]] = []
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.flush)
        self._timer.start()

    def emit_log(self, level: str, msg: str) -> None:
        self._buf.append((datetime.now().strftime("%H:%M:%S"), level, msg))
        getattr(log, level if level in ("debug", "info", "warning", "error") else "info")(msg)

    def flush(self) -> None:
        if not self._buf:
            return
        buf, self._buf = self._buf, []
        bar = self.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        self.setUpdatesEnabled(False)
        try:
            for ts, level, msg in buf:
                color = _COLORS.get(level, "#616161")
                lvl = f"{level.upper():7s}".replace(" ", "&nbsp;")
                text = html.escape(msg).replace("\n", "<br>")
                self.appendHtml(f'<span style="color:{color}">{ts} {lvl} {text}</span>')
        finally:
            self.setUpdatesEnabled(True)
        if at_bottom:
            bar.setValue(bar.maximum())
