# -*- coding: utf-8 -*-
"""Главное окно: шапка (команда + переключатель участника без пароля),
панель «Мои активные», вкладки, таймеры 1 с / heartbeat 30 с,
закрытие приложения (п.5.4 ТЗ)."""

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

from .. import services
from ..services import fmt_dur
from .board_tab import BoardTab
from .records_tab import RecordsTab
from .reports_tab import ReportsTab
from .team_tab import TeamTab
from .templates_tab import TemplatesTab
from .theme import THEMES, apply as apply_theme, current_theme, save_theme
from .util import ask


class MainWindow(QMainWindow):
    def __init__(self, db, user, status_note: str = ""):
        super().__init__()
        self.db = db
        self.user = user
        self.setWindowTitle("TimeTracker")

        # --- шапка: команда + тема + переключатель участника (без авторизации) ---
        self.lbl_team = QLabel()
        self.lbl_team.setObjectName("teamLabel")
        font = QFont()
        font.setBold(True)
        self.lbl_team.setFont(font)

        lbl_theme = QLabel("Тема:")
        self.cmb_theme = QComboBox()
        for key, label in THEMES.items():
            self.cmb_theme.addItem(label, key)
        idx = self.cmb_theme.findData(current_theme(db))
        if idx >= 0:
            self.cmb_theme.setCurrentIndex(idx)
        self.cmb_theme.currentIndexChanged.connect(self._on_theme_changed)

        lbl_member = QLabel("Участник:")
        self.cmb_member = QComboBox()
        self.cmb_member.currentIndexChanged.connect(self._on_member_changed)

        header = QHBoxLayout()
        header.addWidget(self.lbl_team)
        header.addStretch(1)
        header.addWidget(lbl_theme)
        header.addWidget(self.cmb_theme)
        header.addSpacing(12)
        header.addWidget(lbl_member)
        header.addWidget(self.cmb_member)

        # --- панель «Мои активные» ---
        self.grp_active = QGroupBox("Мои активные")
        self.panel_layout = QHBoxLayout()
        self.grp_active.setLayout(self.panel_layout)
        self._panel_timer_labels = []  # [(started_at, QLabel)]

        # --- вкладки ---
        self.tabs = QTabWidget()
        self._build_tabs()

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addLayout(header)
        lay.addWidget(self.grp_active)
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.resize(1200, 700)

        self.statusBar().showMessage(f"БД: {db.path}")
        if status_note:
            self.statusBar().showMessage(f"БД: {db.path}  •  {status_note}", 15000)

        # --- таймеры ---
        self._timer_ui = QTimer(self)          # таймеры UI — раз в секунду
        self._timer_ui.timeout.connect(self._tick)
        self._timer_ui.start(1000)
        self._timer_heartbeat = QTimer(self)   # heartbeat — каждые 30 секунд
        self._timer_heartbeat.timeout.connect(lambda: services.write_heartbeat(db))
        self._timer_heartbeat.start(30_000)
        services.write_heartbeat(db)  # первая запись — сразу после восстановления

        self._load_members()
        self._rebuild_panel()

    # ---------- вкладки и участники ----------

    def _build_tabs(self):
        """Создаёт вкладки для текущего участника (пересоздаются при переключении)."""
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

        db, user = self.db, self.user
        self.board_tab = BoardTab(db, user, self._data_changed)
        self.tabs.addTab(self.board_tab, "Доска")
        self.templates_tab = TemplatesTab(db, user, self._data_changed)
        self.tabs.addTab(self.templates_tab, "Шаблоны")
        # просмотр своих записей времени — право участника (п.2 ТЗ)
        self.records_tab = RecordsTab(db, user)
        self.tabs.addTab(self.records_tab, "Мои записи")
        self.team_tab = TeamTab(db, user, self._data_changed)
        self.tabs.addTab(self.team_tab, "Профиль команды")
        self.reports_tab = ReportsTab(db, user)
        self.tabs.addTab(self.reports_tab, "Отчёты")

    def _on_theme_changed(self, _index):
        """Переключение светлой/тёмной темы (выбор сохраняется в settings)."""
        name = self.cmb_theme.currentData()
        save_theme(self.db, name)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, name)
        self.statusBar().showMessage(f"Тема: {THEMES.get(name, name)}", 3000)

    def _load_members(self):
        """Список участников в переключателе шапки."""
        current = self.user["id"]
        self.cmb_member.blockSignals(True)
        self.cmb_member.clear()
        for m in services.list_members(self.db):
            self.cmb_member.addItem(m["login"], m["id"])
        idx = self.cmb_member.findData(current)
        if idx >= 0:
            self.cmb_member.setCurrentIndex(idx)
        self.cmb_member.blockSignals(False)
        self.lbl_team.setText(f"Команда: {services.get_team_name(self.db)}")

    def _on_member_changed(self, _index):
        """Переключение участника: без пароля, открытые интервалы не трогаем."""
        member_id = self.cmb_member.currentData()
        if member_id is None or member_id == self.user["id"]:
            return
        member = services.get_user(self.db, member_id)
        if member is None or member["is_deleted"] or not member["is_active"]:
            return
        services.set_current_member(self.db, member_id)
        self.user = member
        self._build_tabs()
        self._rebuild_panel()
        self.statusBar().showMessage(
            f"Текущий участник: {member['login']} (переключено без пароля)", 5000)

    # ---------- обновление данных ----------

    def _data_changed(self):
        """Вызывается вкладками после любого изменения данных."""
        self._load_members()
        self.board_tab.refresh()
        self.templates_tab.refresh()
        self.records_tab.refresh()
        self.team_tab.refresh()
        self.reports_tab.refresh()
        self._rebuild_panel()

    def _rebuild_panel(self):
        """Панель «Мои активные»: чип на каждый открытый интервал участника."""
        self._panel_timer_labels = []
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        rows = services.open_intervals_for_user(self.db, self.user["id"])
        if not rows:
            empty = QLabel("Нет активных интервалов")
            empty.setStyleSheet("color: gray;")
            self.panel_layout.addWidget(empty)
            self.panel_layout.addStretch(1)
            return
        for r in rows:
            self.panel_layout.addWidget(self._panel_chip(r), 1)

    def _panel_chip(self, r) -> QFrame:
        chip = QFrame()
        chip.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        lbl_title = QLabel(r["title"])
        font = QFont()
        font.setBold(True)
        lbl_title.setFont(font)
        lbl_timer = QLabel("00:00")
        timer_font = QFont("Consolas")
        timer_font.setStyleHint(QFont.StyleHint.Monospace)
        timer_font.setPointSize(11)
        lbl_timer.setFont(timer_font)
        lbl_timer.setText(fmt_dur(services.elapsed_since(r["started_at"])))
        self._panel_timer_labels.append((r["started_at"], lbl_timer))

        btn_stop = QPushButton("Завершить")
        btn_stop.clicked.connect(
            lambda _=False, tid=r["task_id"], title=r["title"]:
                self._stop_from_panel(tid, title, r["started_at"]))

        lay.addWidget(lbl_title)
        lay.addWidget(lbl_timer)
        lay.addWidget(btn_stop)
        return chip

    def _stop_from_panel(self, task_id, title, started_at):
        if not ask(self, "Завершение",
                   f"Завершить задачу «{title}»? "
                   f"Длительность: {fmt_dur(services.elapsed_since(started_at))}"):
            return
        try:
            services.stop_interval(self.db, self.user["id"], task_id, "user")
        except services.ServiceError as exc:
            QMessageBox.warning(self, "TimeTracker", str(exc))
            return
        self._data_changed()

    # ---------- таймеры ----------

    def _tick(self):
        """Раз в секунду: обновление живых таймеров (панель, доска, записи)."""
        now = datetime.now()
        for started_at, label in self._panel_timer_labels:
            elapsed = max(0, int((now - services.parse_ts(started_at)).total_seconds()))
            label.setText(fmt_dur(elapsed))
        self.board_tab.tick()
        self.records_tab.tick()

    # ---------- закрытие ----------

    def closeEvent(self, event):
        """Закрытие окна: при открытых интервалах — предупреждение (п.5.4 ТЗ).

        Без авторизации закрываются интервалы всех участников.
        """
        opens = services.open_intervals_all(self.db)
        if opens:
            ret = QMessageBox.question(
                self, "Подтверждение",
                f"Будут закрыты {len(opens)} активных интервалов текущим временем. "
                "Закрыть приложение?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            services.stop_all_open(self.db, "app_close")
        event.accept()
