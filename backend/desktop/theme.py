from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BG_DEFAULT = "#0f1115"
BG_PAPER = "#171a21"
BG_ELEVATED = "#1e222b"
BG_INPUT = "#12151c"
PRIMARY = "#7c9cff"
PRIMARY_DIM = "#5a7fd4"
SECONDARY = "#64d4b0"
TEXT_PRIMARY = "#e8eaed"
TEXT_SECONDARY = "#9aa0a6"
TEXT_MUTED = "#6b7280"
BORDER = "#2a2e38"
BORDER_FOCUS = "#7c9cff"
SUCCESS = "#4caf50"
WARNING = "#ff9800"
INFO = "#29b6f6"
SCROLL_TRACK = "#12151c"
SCROLL_THUMB = "#44506a"
SCROLL_THUMB_HOVER = "#7c9cff"
RADIUS = "12px"
RADIUS_SM = "8px"


def build_stylesheet() -> str:
    return f"""
QMainWindow, QWidget {{
    background-color: {BG_DEFAULT};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}}

#AppHeader {{
    background-color: {BG_DEFAULT};
    border: none;
    border-bottom: 1px solid {BORDER};
}}

#AppTitle {{
    color: {TEXT_PRIMARY};
    font-size: 22px;
    font-weight: 700;
    padding: 14px 20px;
    background: transparent;
}}

QTabWidget::pane {{
    border: none;
    background: {BG_DEFAULT};
    top: -1px;
}}

QTabBar {{
    background: transparent;
    border-bottom: 1px solid {BORDER};
    padding: 0 12px;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 12px 22px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}

QTabBar::tab:selected {{
    color: {PRIMARY};
    border-bottom: 2px solid {PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
}}

#Card {{
    background-color: {BG_PAPER};
    border: 1px solid {BORDER};
    border-radius: {RADIUS};
}}

#CardTitle {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}}

#CardSubtitle, #MutedLabel {{
    color: {TEXT_SECONDARY};
    background: transparent;
}}

#Badge {{
    color: {TEXT_SECONDARY};
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}}

#BadgeSuccess {{
    color: {SUCCESS};
    background-color: rgba(76, 175, 80, 0.12);
    border: 1px solid rgba(76, 175, 80, 0.35);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 600;
}}

#BadgeWarning {{
    color: {WARNING};
    background-color: rgba(255, 152, 0, 0.12);
    border: 1px solid rgba(255, 152, 0, 0.35);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 600;
}}

#BadgeInfo {{
    color: {INFO};
    background-color: rgba(41, 182, 246, 0.12);
    border: 1px solid rgba(41, 182, 246, 0.35);
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 600;
}}

#PrimaryButton {{
    background-color: {PRIMARY};
    color: #0f1115;
    border: none;
    border-radius: {RADIUS_SM};
    padding: 8px 16px;
    font-weight: 600;
}}

#PrimaryButton:hover {{
    background-color: #96adff;
}}

#PrimaryButton:pressed {{
    background-color: {PRIMARY_DIM};
}}

#PrimaryButton:disabled {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
}}

#SecondaryButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 8px 16px;
    font-weight: 600;
}}

#SecondaryButton:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}

#GhostButton {{
    background-color: rgba(15, 17, 21, 0.65);
    color: {TEXT_SECONDARY};
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: {RADIUS_SM};
    padding: 6px 12px;
    font-weight: 600;
}}

#GhostButton:hover {{
    background-color: rgba(15, 17, 21, 0.9);
    color: {TEXT_PRIMARY};
}}

#DangerGhostButton {{
    background-color: rgba(244, 67, 54, 0.07);
    color: #ff6b6b;
    border: 1px solid rgba(244, 67, 54, 0.3);
    border-radius: {RADIUS_SM};
    padding: 6px 12px;
    font-weight: 600;
}}

#DangerGhostButton:hover {{
    background-color: rgba(244, 67, 54, 0.11);
    border-color: rgba(244, 67, 54, 0.45);
}}

#ToggleButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 14px;
    font-weight: 600;
}}

#ToggleButton:checked {{
    background-color: rgba(124, 156, 255, 0.15);
    color: {PRIMARY};
    border-color: {PRIMARY};
}}

#FieldLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    background: transparent;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 8px 10px;
    selection-background-color: {PRIMARY_DIM};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_PAPER};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: rgba(124, 156, 255, 0.2);
}}

QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background: {BG_INPUT};
}}

QCheckBox::indicator:checked {{
    background: {PRIMARY};
    border-color: {PRIMARY};
}}

QListWidget {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    border-radius: 6px;
    padding: 8px 10px;
    margin: 2px 0;
}}

QListWidget::item:selected {{
    background-color: rgba(124, 156, 255, 0.15);
    color: {TEXT_PRIMARY};
}}

QListWidget::item:hover:!selected {{
    background-color: {BG_ELEVATED};
}}

#CoveragePanel {{
    background-color: {BG_PAPER};
    border: none;
    border-right: 1px solid {BORDER};
}}

#DayCard {{
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    border-left: 3px solid {BORDER};
}}

#DayCard[selected="true"] {{
    background-color: rgba(124, 156, 255, 0.08);
    border-color: rgba(124, 156, 255, 0.5);
    border-left: 3px solid {PRIMARY};
}}

#DayCard[status="complete"] {{
    border-left-color: {SUCCESS};
}}

#DayCard[status="parsed"] {{
    border-left-color: {WARNING};
}}

#DayCard[status="ready"] {{
    border-left-color: {INFO};
}}

QTableWidget {{
    background-color: {BG_INPUT};
    alternate-background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    gridline-color: {BORDER};
    selection-background-color: rgba(124, 156, 255, 0.2);
    selection-color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: rgba(124, 156, 255, 0.1);
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid rgba(124, 156, 255, 0.25);
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}}

QProgressBar {{
    background-color: {BG_ELEVATED};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: 4px;
}}

QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}

QScrollBar:vertical {{
    background: {SCROLL_TRACK};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {SCROLL_THUMB};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {SCROLL_THUMB_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}

QScrollBar:horizontal {{
    background: {SCROLL_TRACK};
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: {SCROLL_THUMB};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {SCROLL_THUMB_HOVER};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}

QToolButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    padding: 4px;
    border-radius: 6px;
}}

QToolButton:hover {{
    background: {BG_ELEVATED};
    color: {PRIMARY};
}}

QMessageBox {{
    background-color: {BG_PAPER};
}}

QDialog {{
    background-color: {BG_PAPER};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_DEFAULT))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f1115"))
    app.setPalette(palette)
