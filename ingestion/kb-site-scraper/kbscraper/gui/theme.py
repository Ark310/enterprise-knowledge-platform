"""Contoso brand palette + app stylesheet (ported from the Knowledge Base scraper)."""
from __future__ import annotations

import sys
from pathlib import Path

PALETTE = {
    "brand": "#51639e",
    "brand_deep": "#3f4f82",
    "bg": "#eef1f7",
    "surface": "#ffffff",
    "surface_2": "#f6f8fc",
    "border": "#dfe4ee",
    "text": "#1e2536",
    "muted": "#6b7480",
}

STATUS_COLORS = {
    "pending": "#8a93a3",
    "running": "#1f6fd1",
    "done": "#2e7d32",
    "warning": "#c77700",
    "failed": "#c62828",
    "missing": "#8e24aa",
}
STATUS_LABELS = {
    "pending": "Pending", "running": "Running…", "done": "Done",
    "warning": "Warning", "failed": "Failed", "missing": "Not scraped",
}
FONT_STACK = "'Segoe UI', system-ui, Arial, sans-serif"


def asset_path(name: str) -> Path | None:
    base = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]) / "assets"
    p = base / name
    return p if p.exists() else None


def app_stylesheet() -> str:
    P = PALETTE
    return f"""
    QWidget {{ background: {P['bg']}; color: {P['text']}; font-family: {FONT_STACK}; font-size: 13px; }}
    QTabWidget::pane {{ border: 1px solid {P['border']}; background: {P['surface']}; }}
    QTabBar::tab {{ background: {P['surface_2']}; color: {P['muted']}; padding: 7px 16px; border: 0; }}
    QTabBar::tab:selected {{ color: {P['brand']}; border-bottom: 2px solid {P['brand']}; background: {P['surface']}; }}
    QGroupBox {{ background: {P['surface']}; border: 1px solid {P['border']}; border-radius: 8px;
                 margin-top: 14px; padding: 8px; font-weight: 600; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {P['muted']}; }}
    QPlainTextEdit, QLineEdit, QTableView, QTreeWidget, QTextBrowser, QSpinBox, QComboBox {{
        background: {P['surface']}; border: 1px solid {P['border']}; border-radius: 6px; }}
    QTableView {{ gridline-color: {P['border']}; selection-background-color: #dfe6f7; selection-color: {P['text']}; }}
    QTreeWidget {{ selection-background-color: #dfe6f7; selection-color: {P['text']}; }}
    QHeaderView::section {{ background: {P['surface_2']}; color: {P['muted']}; border: 0;
                            border-bottom: 1px solid {P['border']}; padding: 5px; }}
    QPushButton {{ background: {P['surface']}; border: 1px solid {P['border']}; border-radius: 6px; padding: 6px 12px; }}
    QPushButton:hover {{ border-color: {P['brand']}; }}
    QPushButton:disabled {{ color: #a8aebb; background: {P['surface_2']}; }}
    QPushButton#Primary {{ background: {P['brand']}; color: white; border: 0; font-weight: bold; }}
    QPushButton#Primary:hover {{ background: {P['brand_deep']}; }}
    QPushButton#Primary:disabled {{ background: #a9b3d1; }}
    QPushButton#Danger {{ color: #c62828; }}
    QProgressBar {{ border: 0; background: #e4e8f2; border-radius: 6px; height: 14px; text-align: center; }}
    QProgressBar::chunk {{ background: {P['brand']}; border-radius: 6px; }}
    QLabel#Muted {{ color: {P['muted']}; }}
    QFrame#Header {{ background: {P['surface']}; border-bottom: 2px solid {P['brand']}; }}
    """
