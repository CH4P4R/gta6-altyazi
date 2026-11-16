"""Tasarım sistemi: Vice City gün batımı tonlarında koyu tema."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QLinearGradient

BG = "#0d0b13"
SIDEBAR = "#110e18"
SURFACE = "#17131f"
SURFACE2 = "#1e1928"
SURFACE3 = "#272133"
BORDER = "#2a2335"
BORDER_HI = "#3a3148"
TEXT = "#f4f1fa"
MUTED = "#9d93b0"
FAINT = "#6c6380"
A1 = "#ff4fa3"   # pembe
A2 = "#ff9f43"   # turuncu
A3 = "#8b5cf6"   # mor (ikincil)
OK = "#3ddc97"
WARN = "#ffb547"
BAD = "#ff5c7a"
INFO = "#5cc8ff"

FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "Roboto", "DejaVu Sans"]
DISPLAY = ["Segoe UI Variable Display", "Segoe UI", "Inter", "DejaVu Sans"]


def font(size: int = 10, weight: QFont.Weight = QFont.Normal, display: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(DISPLAY if display else FAMILIES)
    f.setPointSizeF(size)
    f.setWeight(weight)
    return f


def accent_gradient(x0: float, y0: float, x1: float, y1: float) -> QLinearGradient:
    g = QLinearGradient(x0, y0, x1, y1)
    g.setColorAt(0, QColor(A1))
    g.setColorAt(1, QColor(A2))
    return g


QSS = f"""
* {{ outline: 0; }}
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QDialog, #page {{ background: {BG}; }}
QToolTip {{ background: {SURFACE3}; color: {TEXT}; border: 1px solid {BORDER_HI}; padding: 6px 8px; border-radius: 6px; }}

#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
#navButton {{ text-align: left; padding: 11px 14px 11px 44px; border: 0; border-radius: 10px; color: {MUTED};
              font-size: 10.5pt; font-weight: 600; background: transparent; }}
#navButton:hover {{ background: {SURFACE}; color: {TEXT}; }}
#navButton:checked {{ background: {SURFACE2}; color: {TEXT}; }}

#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; }}
#cardInner {{ background: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 12px; }}
#h1 {{ font-size: 20pt; font-weight: 700; }}
#h2 {{ font-size: 13pt; font-weight: 700; }}
#h3 {{ font-size: 10.5pt; font-weight: 700; }}
#muted {{ color: {MUTED}; }}
#faint {{ color: {FAINT}; font-size: 9pt; }}
#tag {{ color: {A2}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }}
#big {{ font-size: 26pt; font-weight: 700; }}
#display {{ font-size: 22pt; font-weight: 700; }}
#stateTitle {{ font-size: 18pt; font-weight: 700; }}
#feedTr {{ font-size: 12.5pt; font-weight: 600; }}

QPushButton {{ background: {SURFACE2}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 9px 16px;
               font-weight: 600; color: {TEXT}; }}
QPushButton:hover {{ background: {SURFACE3}; border-color: #4a3f5c; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {FAINT}; border-color: {BORDER}; }}
QPushButton#primary {{ border: 0; color: white;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {A1}, stop:1 {A2}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff66b0, stop:1 #ffb066); }}
QPushButton#primary:disabled {{ background: {SURFACE3}; color: {FAINT}; }}
QPushButton#ghost {{ background: transparent; border: 0; color: {MUTED}; padding: 6px 10px; }}
QPushButton#ghost:hover {{ color: {TEXT}; background: {SURFACE2}; }}
QPushButton#danger {{ background: transparent; border: 1px solid #5a2a38; color: {BAD}; }}
QPushButton#link {{ background: transparent; border: 0; color: {A2}; padding: 0; text-align: left; }}
QPushButton#link:hover {{ color: {A1}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {SURFACE2}; border: 1px solid {BORDER_HI}; border-radius: 9px; padding: 8px 10px;
    selection-background-color: {A1}; color: {TEXT}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {A1}; }}
QComboBox::drop-down {{ border: 0; width: 26px; }}
QComboBox QAbstractItemView {{ background: {SURFACE2}; border: 1px solid {BORDER_HI}; selection-background-color: {SURFACE3};
    padding: 4px; outline: 0; }}

QSlider::groove:horizontal {{ height: 6px; background: {SURFACE3}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {A1}, stop:1 {A2}); }}
QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; background: white; }}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {BORDER_HI}; background: {SURFACE2}; }}
QCheckBox::indicator:checked {{ border: 0; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {A1}, stop:1 {A2}); }}

QScrollArea {{ border: 0; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {SURFACE3}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QTableWidget {{ background: {SURFACE}; border: 0; gridline-color: {BORDER}; selection-background-color: {SURFACE3}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: 0; border-bottom: 1px solid {BORDER};
    padding: 8px; font-weight: 600; }}
QListWidget {{ background: {SURFACE2}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 7px; color: {MUTED}; }}
QListWidget::item:hover {{ background: {SURFACE3}; color: {TEXT}; }}
QListWidget::item:selected {{ background: {SURFACE3}; color: {TEXT}; border-left: 3px solid {A1}; }}
"""
