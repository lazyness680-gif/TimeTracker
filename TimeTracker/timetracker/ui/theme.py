# -*- coding: utf-8 -*-
"""Оформление TimeTracker: светлая и тёмная темы (QSS), переключатель в шапке.

Палитра: синий (основной), янтарь («В работе»), зелёный («Завершена»),
красный (высокий приоритет). Выбор темы хранится в settings (ключ theme).
"""

from __future__ import annotations

THEME_KEY = "theme"
DEFAULT_THEME = "light"
THEMES = {"light": "Светлая", "dark": "Тёмная"}

# ---------------------------------------------------------------- светлая

_LIGHT = """
/* ---------- база ---------- */
QMainWindow, QDialog {
    background: #f4f6fa;
    color: #243046;
}
QLabel { color: #243046; }
QLabel#teamLabel {
    color: #2f6fb2;
    font-size: 15px;
    font-weight: 700;
}
QLabel[colTitle="1"] { font-size: 13px; }

/* ---------- кнопки ---------- */
QPushButton {
    background: #2f6fb2;
    color: #ffffff;
    border: 1px solid #2f6fb2;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #3f83c8; border-color: #3f83c8; }
QPushButton:pressed { background: #245a94; border-color: #245a94; }
QPushButton:disabled {
    background: #c4ccd9; color: #f4f6fa; border-color: #c4ccd9;
}
QPushButton#secondary {
    background: #eef2f8; color: #44506a; border: 1px solid #ccd5e3;
    font-weight: 500;
}
QPushButton#secondary:hover { background: #e2e9f3; border-color: #b6c2d4; }
QPushButton#secondary:pressed { background: #d8e0ed; }
QPushButton#secondary:disabled { background: #f0f2f6; color: #a8b1c2; }
QPushButton#danger {
    background: #c0392b; border-color: #c0392b;
}
QPushButton#danger:hover { background: #d4483a; border-color: #d4483a; }
QPushButton#danger:pressed { background: #a93025; border-color: #a93025; }
QPushButton#danger:disabled {
    background: #dcb6b1; border-color: #dcb6b1; color: #fff5f4;
}

/* ---------- поля ввода ---------- */
QLineEdit, QPlainTextEdit, QDateEdit, QDateTimeEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #cbd4e2;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #2f6fb2;
    selection-color: #ffffff;
}
QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus,
QDateTimeEdit:focus, QComboBox:focus { border: 1px solid #2f6fb2; }
QLineEdit:disabled, QComboBox:disabled { background: #eef1f6; color: #97a1b3; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #cbd4e2;
    selection-background-color: #dceafa;
    selection-color: #243046;
}
QCheckBox { spacing: 6px; color: #243046; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #b6c2d4;
    border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:checked { background: #2f6fb2; border-color: #2f6fb2; }

/* ---------- таблицы ---------- */
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #dbe2ec;
    border-radius: 10px;
    gridline-color: #e7ecf4;
    selection-background-color: #dceafa;
    selection-color: #243046;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #eef2f8;
    color: #2f4a70;
    border: none;
    border-right: 1px solid #dbe2ec;
    border-bottom: 1px solid #dbe2ec;
    padding: 7px 8px;
    font-weight: 700;
}
QTableCornerButton::section { background: #eef2f8; border: none; }

/* ---------- вкладки ---------- */
QTabWidget::pane {
    border: 1px solid #dbe2ec;
    border-radius: 10px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: #e7ecf4;
    color: #4a5875;
    border: 1px solid #dbe2ec;
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    padding: 8px 20px;
    margin-right: 3px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #2f6fb2;
    border-top: 3px solid #2f6fb2;
}
QTabBar::tab:hover:!selected { background: #dfe7f2; }

/* ---------- панель «Мои активные» ---------- */
QGroupBox {
    background: #ffffff;
    border: 1px solid #dbe2ec;
    border-radius: 12px;
    margin-top: 10px;
    padding: 14px 10px 8px 10px;
    font-weight: 700;
    color: #2f6fb2;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}

/* ---------- канбан: колонки ---------- */
QFrame#col_new {
    background: #f4f6fa;
    border: 1px solid #d3dae6;
    border-radius: 12px;
}
QFrame#col_new QLabel[colTitle="1"] { color: #5b6b82; }
QFrame#col_in_progress {
    background: #fff6e0;
    border: 1px solid #f0cf8a;
    border-radius: 12px;
}
QFrame#col_in_progress QLabel[colTitle="1"] { color: #b47e00; }
QFrame#col_done {
    background: #eaf7f0;
    border: 1px solid #a8dcc1;
    border-radius: 12px;
}
QFrame#col_done QLabel[colTitle="1"] { color: #1e7d48; }
QFrame#col_new[drop="true"],
QFrame#col_in_progress[drop="true"],
QFrame#col_done[drop="true"] {
    background: #e3eefc;
    border: 2px dashed #2f6fb2;
}

/* ---------- канбан: карточки ---------- */
QFrame#card {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-left: 5px solid #8fa3bf;
    border-radius: 10px;
}
QFrame#card[prio="0"] { border-left: 5px solid #8fa3bf; }
QFrame#card[prio="1"] { border-left: 5px solid #2f6fb2; }
QFrame#card[prio="2"] { border-left: 5px solid #c0392b; }
QFrame#card[active="true"] {
    background: #fffdf6;
    border: 2px solid #f0a202;
    border-left: 5px solid #f0a202;
}
QLabel#prio { font-weight: 700; }
QLabel#prio[prio="0"] { color: #7a8699; }
QLabel#prio[prio="1"] { color: #2f6fb2; }
QLabel#prio[prio="2"] { color: #c0392b; }
QLabel#liveTimer { color: #1e7d48; font-weight: 700; }

/* ---------- служебное ---------- */
QToolTip {
    background: #243046; color: #ffffff;
    border: 1px solid #243046; padding: 4px;
}
QScrollBar:vertical {
    background: #eef1f6; width: 12px; border-radius: 6px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #b9c4d6; min-height: 28px; border-radius: 6px;
}
QScrollBar::handle:vertical:hover { background: #97a6bf; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #eef1f6; height: 12px; border-radius: 6px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #b9c4d6; min-width: 28px; border-radius: 6px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
QStatusBar { background: #eaeef5; color: #4a5875; }
QMessageBox { background: #f4f6fa; }
"""

# ---------------------------------------------------------------- тёмная

_DARK = """
/* ---------- база ---------- */
QMainWindow, QDialog {
    background: #1b1f2a;
    color: #e8ecf5;
}
QLabel { color: #e8ecf5; }
QLabel#teamLabel {
    color: #6fa8f0;
    font-size: 15px;
    font-weight: 700;
}

/* ---------- кнопки ---------- */
QPushButton {
    background: #3d7fd0;
    color: #ffffff;
    border: 1px solid #3d7fd0;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover { background: #4f8fe0; border-color: #4f8fe0; }
QPushButton:pressed { background: #2f66ad; border-color: #2f66ad; }
QPushButton:disabled {
    background: #2d3346; color: #767f95; border-color: #2d3346;
}
QPushButton#secondary {
    background: #262b3b; color: #b8c2d8; border: 1px solid #3a4258;
    font-weight: 500;
}
QPushButton#secondary:hover { background: #2f3547; border-color: #4a5470; }
QPushButton#secondary:pressed { background: #232838; }
QPushButton#secondary:disabled { background: #222634; color: #6a7288; }
QPushButton#danger {
    background: #c94b3f; border-color: #c94b3f;
}
QPushButton#danger:hover { background: #dc5b4e; border-color: #dc5b4e; }
QPushButton#danger:pressed { background: #a93a30; border-color: #a93a30; }
QPushButton#danger:disabled {
    background: #4a2f2c; border-color: #4a2f2c; color: #9a8079;
}

/* ---------- поля ввода ---------- */
QLineEdit, QPlainTextEdit, QDateEdit, QDateTimeEdit, QComboBox {
    background: #232838;
    border: 1px solid #3a4258;
    border-radius: 8px;
    padding: 5px 8px;
    color: #e8ecf5;
    selection-background-color: #3d7fd0;
    selection-color: #ffffff;
}
QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus,
QDateTimeEdit:focus, QComboBox:focus { border: 1px solid #4f8fe0; }
QLineEdit:disabled, QComboBox:disabled { background: #1f2330; color: #6a7288; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #232838;
    border: 1px solid #3a4258;
    color: #e8ecf5;
    selection-background-color: #31456b;
    selection-color: #ffffff;
}
QCheckBox { spacing: 6px; color: #e8ecf5; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #4a5470;
    border-radius: 4px;
    background: #232838;
}
QCheckBox::indicator:checked { background: #3d7fd0; border-color: #3d7fd0; }

/* ---------- таблицы ---------- */
QTableWidget {
    background: #20242f;
    alternate-background-color: #252a38;
    border: 1px solid #333a4f;
    border-radius: 10px;
    gridline-color: #2e3446;
    color: #e8ecf5;
    selection-background-color: #31456b;
    selection-color: #ffffff;
}
QTableWidget::item { padding: 4px 6px; }
QHeaderView::section {
    background: #2a2f40;
    color: #aebbd6;
    border: none;
    border-right: 1px solid #333a4f;
    border-bottom: 1px solid #333a4f;
    padding: 7px 8px;
    font-weight: 700;
}
QTableCornerButton::section { background: #2a2f40; border: none; }

/* ---------- вкладки ---------- */
QTabWidget::pane {
    border: 1px solid #333a4f;
    border-radius: 10px;
    background: #20242f;
    top: -1px;
}
QTabBar::tab {
    background: #262b3b;
    color: #9aa7c2;
    border: 1px solid #333a4f;
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    padding: 8px 20px;
    margin-right: 3px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #20242f;
    color: #6fa8f0;
    border-top: 3px solid #3d7fd0;
}
QTabBar::tab:hover:!selected { background: #2f3547; }

/* ---------- панель «Мои активные» ---------- */
QGroupBox {
    background: #20242f;
    border: 1px solid #333a4f;
    border-radius: 12px;
    margin-top: 10px;
    padding: 14px 10px 8px 10px;
    font-weight: 700;
    color: #6fa8f0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}

/* ---------- канбан: колонки ---------- */
QFrame#col_new {
    background: #262b3b;
    border: 1px solid #3a4258;
    border-radius: 12px;
}
QFrame#col_new QLabel[colTitle="1"] { color: #9aa7c2; }
QFrame#col_in_progress {
    background: #35301c;
    border: 1px solid #7a6018;
    border-radius: 12px;
}
QFrame#col_in_progress QLabel[colTitle="1"] { color: #f2b134; }
QFrame#col_done {
    background: #1e3328;
    border: 1px solid #2f6b48;
    border-radius: 12px;
}
QFrame#col_done QLabel[colTitle="1"] { color: #52c98b; }
QFrame#col_new[drop="true"],
QFrame#col_in_progress[drop="true"],
QFrame#col_done[drop="true"] {
    background: #2c3a52;
    border: 2px dashed #4f8fe0;
}

/* ---------- канбан: карточки ---------- */
QFrame#card {
    background: #262b3b;
    border: 1px solid #39415a;
    border-left: 5px solid #77839e;
    border-radius: 10px;
    color: #e8ecf5;
}
QFrame#card[prio="0"] { border-left: 5px solid #77839e; }
QFrame#card[prio="1"] { border-left: 5px solid #4f8fe0; }
QFrame#card[prio="2"] { border-left: 5px solid #e05f52; }
QFrame#card[active="true"] {
    background: #2d2c1e;
    border: 2px solid #d99a1f;
    border-left: 5px solid #d99a1f;
}
QLabel#prio { font-weight: 700; }
QLabel#prio[prio="0"] { color: #9aa7c2; }
QLabel#prio[prio="1"] { color: #6fa8f0; }
QLabel#prio[prio="2"] { color: #ff8a7a; }
QLabel#liveTimer { color: #52c98b; font-weight: 700; }

/* ---------- служебное ---------- */
QToolTip {
    background: #e8ecf5; color: #1b1f2a;
    border: 1px solid #e8ecf5; padding: 4px;
}
QScrollBar:vertical {
    background: #20242f; width: 12px; border-radius: 6px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #3d4560; min-height: 28px; border-radius: 6px;
}
QScrollBar::handle:vertical:hover { background: #4f5a7a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #20242f; height: 12px; border-radius: 6px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3d4560; min-width: 28px; border-radius: 6px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
QStatusBar { background: #171b24; color: #9aa7c2; }
QMessageBox { background: #1b1f2a; }
"""

_QSS = {"light": _LIGHT, "dark": _DARK}


# ---------------------------------------------------------------- API

def qss_for(name: str) -> str:
    """Стиль QSS для темы; неизвестное имя → светлая тема."""
    return _QSS.get(name, _QSS[DEFAULT_THEME])


def current_theme(db) -> str:
    """Сохранённая тема ('light'/'dark'); некорректное значение → light."""
    from .. import services
    v = services.get_setting(db, THEME_KEY)
    return v if v in _QSS else DEFAULT_THEME


def save_theme(db, name: str):
    """Сохранить выбор темы в settings (без применения к QApplication)."""
    from .. import services
    services.set_setting(db, THEME_KEY, name if name in _QSS else DEFAULT_THEME)


def apply(app, name: str) -> str:
    """Применить тему к QApplication; возвращает применённое имя."""
    resolved = name if name in _QSS else DEFAULT_THEME
    app.setStyleSheet(qss_for(resolved))
    return resolved
