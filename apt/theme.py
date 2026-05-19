"""AIVEX black-and-orange theme.

The QSS is intentionally a single string instead of per-widget stylesheets so
that the UI stays consistent and individual dialogs can stay free of styling
noise.
"""

from __future__ import annotations

from PyQt5.QtGui import QColor, QPalette

# Brand palette
ORANGE = "#FF7029"
ORANGE_HOVER = "#FF8C4A"
ORANGE_DARK = "#C8501A"
BLACK = "#0B0B0E"
PANEL = "#15161B"
PANEL_2 = "#1D1F26"
BORDER = "#2A2D35"
TEXT = "#EDEDEF"
TEXT_DIM = "#9A9CA3"
DANGER = "#E5484D"
SUCCESS = "#33B66B"


QSS = f"""
QWidget {{
    background-color: {BLACK};
    color: {TEXT};
    font-family: "Segoe UI", "Noto Sans KR", sans-serif;
    font-size: 13px;
}}

QFrame#Sidebar {{
    background-color: {PANEL};
    border-right: 1px solid {BORDER};
}}

QLabel#BrandLabel {{
    color: {ORANGE};
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 4px;
    padding: 18px 16px 4px 16px;
}}
QLabel#BrandSub {{
    color: {TEXT_DIM};
    font-size: 10px;
    letter-spacing: 2px;
    padding: 0 16px 18px 16px;
}}

QLabel#SectionLabel {{
    color: {TEXT_DIM};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 14px 16px 6px 16px;
}}

QPushButton#NavButton {{
    text-align: left;
    padding: 10px 16px;
    background-color: transparent;
    border: none;
    color: {TEXT};
    border-left: 3px solid transparent;
}}
QPushButton#NavButton:hover {{
    background-color: {PANEL_2};
}}
QPushButton#NavButton:checked {{
    background-color: {PANEL_2};
    border-left: 3px solid {ORANGE};
    color: {ORANGE};
    font-weight: 600;
}}

QLabel#PageTitle {{
    color: {TEXT};
    font-size: 20px;
    font-weight: 700;
    padding-bottom: 4px;
}}
QLabel#PageSubtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
    padding-bottom: 14px;
}}

QGroupBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 8px;
    color: {ORANGE};
}}

QLineEdit, QSpinBox, QDateTimeEdit, QComboBox, QTextEdit {{
    background-color: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ORANGE_DARK};
}}
QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {ORANGE};
}}
QLineEdit:read-only {{
    color: {TEXT_DIM};
}}

QPushButton {{
    background-color: {PANEL_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    border: 1px solid {ORANGE};
    color: {ORANGE};
}}
QPushButton:pressed {{
    background-color: {BLACK};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}

QPushButton#PrimaryButton {{
    background-color: {ORANGE};
    color: {BLACK};
    border: 1px solid {ORANGE};
    font-weight: 700;
    padding: 8px 18px;
}}
QPushButton#PrimaryButton:hover {{
    background-color: {ORANGE_HOVER};
    border: 1px solid {ORANGE_HOVER};
    color: {BLACK};
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {PANEL_2};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}

QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
    font-weight: 600;
    padding: 8px 18px;
}}
QPushButton#DangerButton:hover {{
    background-color: {DANGER};
    color: {BLACK};
}}
QPushButton#DangerButton:disabled {{
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
}}

QCheckBox {{
    spacing: 6px;
    color: {TEXT};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {PANEL_2};
}}
QCheckBox::indicator:checked {{
    background-color: {ORANGE};
    border: 1px solid {ORANGE};
}}

QProgressBar {{
    background-color: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT};
    height: 22px;
}}
QProgressBar::chunk {{
    background-color: {ORANGE};
    border-radius: 3px;
}}

QTextEdit#LogConsole {{
    background-color: #08080A;
    color: #E0E0E0;
    font-family: Consolas, "Cascadia Mono", "D2Coding", monospace;
    font-size: 12px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 8px;
}}

QListWidget, QTableWidget {{
    background-color: {PANEL_2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT};
    gridline-color: {BORDER};
    alternate-background-color: {PANEL};
}}
QHeaderView::section {{
    background-color: {PANEL};
    color: {TEXT_DIM};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: 600;
}}
QTableWidget::item:selected,
QListWidget::item:selected {{
    background-color: {ORANGE_DARK};
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: {PANEL};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {PANEL_2};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ORANGE_DARK};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def apply_palette(app) -> None:
    """Set a baseline dark palette so native widgets render reasonably even
    before the QSS kicks in (e.g. file dialogs)."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BLACK))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(PANEL_2))
    palette.setColor(QPalette.AlternateBase, QColor(PANEL))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(PANEL_2))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ORANGE))
    palette.setColor(QPalette.HighlightedText, QColor(BLACK))
    palette.setColor(QPalette.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
