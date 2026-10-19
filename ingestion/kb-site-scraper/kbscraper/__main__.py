"""Launch the GUI:  python -m kbscraper"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _setup_logging() -> None:
    from kbscraper.settings import LOG_DIR
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / f"scraper_{datetime.now():%Y%m%d}.log",
                                  maxBytes=20_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger("kbscraper")
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _excepthook(exc_type, exc, tb):
    import traceback
    logging.getLogger("kbscraper").error("Unhandled GUI error:\n%s",
                                         "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


def main() -> None:
    _setup_logging()
    sys.excepthook = _excepthook
    from PySide6.QtWidgets import QApplication
    from kbscraper.gui.theme import app_stylesheet
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Contoso KB Site Scraper")
    app.setStyleSheet(app_stylesheet())
    from kbscraper.gui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
