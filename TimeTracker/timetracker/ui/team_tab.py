# -*- coding: utf-8 -*-
"""Вкладка «Профиль команды»: название команды, участники (без паролей)
и суммарное время за период."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QAbstractItemView, QDateEdit, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QInputDialog, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import services
from ..services import fmt_dt, fmt_dur
from .util import run_action


class TeamTab(QWidget):
    COLS = ["Участник", "Добавлен", "Время за период", "Действия"]

    def __init__(self, db, user, notify_changed):
        super().__init__()
        self.db, self.user, self.notify = db, user, notify_changed
        self._rows = []

        # --- название команды ---
        self.ed_team = QLineEdit()
        self.ed_team.setMaxLength(64)
        self.ed_team.editingFinished.connect(self._on_team_name)
        btn_team = QPushButton("Сохранить название")
        btn_team.clicked.connect(self._on_team_name)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Команда:"))
        name_row.addWidget(self.ed_team, 1)
        name_row.addWidget(btn_team)

        # --- период статистики ---
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)
        btn_stats = QPushButton("Обновить статистику")
        btn_stats.clicked.connect(self.refresh)

        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel("Статистика с:"))
        stats_row.addWidget(self.date_from)
        stats_row.addWidget(QLabel("по:"))
        stats_row.addWidget(self.date_to)
        stats_row.addWidget(btn_stats)
        stats_row.addStretch(1)

        # --- участники ---
        self.btn_add = QPushButton("Добавить участника")
        self.btn_add.clicked.connect(self._on_add)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.btn_add)
        toolbar.addStretch(1)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self.lbl_note = QLabel("")
        self.lbl_note.setStyleSheet("color: gray;")

        lay = QVBoxLayout(self)
        lay.addLayout(name_row)
        lay.addLayout(stats_row)
        lay.addLayout(toolbar)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.lbl_note)

        self.refresh()

    # ---------- данные ----------

    def refresh(self):
        # название команды (не затираем то, что пользователь печатает)
        if not self.ed_team.hasFocus():
            self.ed_team.setText(services.get_team_name(self.db))

        d_from = self.date_from.date().toPython()
        d_to = self.date_to.date().toPython()
        if d_from > d_to:
            self.table.setRowCount(0)
            self.lbl_note.setText("Дата «с» больше даты «по».")
            return
        stats = services.member_stats(self.db, d_from, d_to)
        members = services.list_members(self.db)
        self._rows = members
        self.table.setRowCount(len(members))
        current_id = self.user["id"]
        for i, m in enumerate(members):
            name = m["login"] + ("  ← текущий" if m["id"] == current_id else "")
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_dt(m["created_at"])))
            self.table.setItem(i, 2, QTableWidgetItem(
                fmt_dur(stats.get(m["id"], 0))))
            self.table.setCellWidget(i, 3, self._actions_widget(m))

        total = sum(stats.get(m["id"], 0) for m in members)
        period = f"{d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}"
        self.lbl_note.setText(
            f"Участников: {len(members)}   •   Итого за период: {fmt_dur(total)}   "
            f"•   период: {period}   •   "
            "Удаление участника сохраняет его задачи и интервалы.")

    def _actions_widget(self, m) -> QWidget:
        is_current = m["id"] == self.user["id"]
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        btn_rename = QPushButton("Переименовать…")
        btn_rename.clicked.connect(lambda _=False, uid=m["id"]: self._on_rename(uid))

        btn_delete = QPushButton("Удалить")
        btn_delete.setObjectName("danger")
        btn_delete.setEnabled(not is_current)
        btn_delete.setToolTip(
            "Сначала переключитесь на другого участника" if is_current else "")
        btn_delete.clicked.connect(lambda _=False, uid=m["id"]: self._on_delete(uid))

        lay.addWidget(btn_rename)
        lay.addWidget(btn_delete)
        return w

    # ---------- команды ----------

    def _on_team_name(self):
        name = self.ed_team.text().strip()
        if name == services.get_team_name(self.db):
            return
        run_action(self, services.set_team_name, self.db, self.user["id"],
                   name, refresh=self.refresh)

    def _on_add(self):
        name, ok = QInputDialog.getText(self, "Новый участник", "Имя участника:")
        if not ok or not name.strip():
            return
        run_action(self, services.create_member, self.db, self.user["id"],
                   name.strip(), refresh=self.notify)

    def _on_rename(self, member_id):
        target = services.get_user(self.db, member_id)
        if target is None:
            return
        name, ok = QInputDialog.getText(
            self, "Переименование", "Новое имя участника:",
            text=target["login"])
        if not ok or not name.strip() or name.strip() == target["login"]:
            return
        run_action(self, services.rename_member, self.db, self.user["id"],
                   member_id, name.strip(), refresh=self.notify)

    def _on_delete(self, member_id):
        target = services.get_user(self.db, member_id)
        if target is None:
            return
        if not QMessageBox.question(
                self, "Удаление участника",
                f"Удалить участника «{target['login']}»?\n\n"
                "Его задачи и интервалы сохранятся (пометка «удалённый участник»), "
                "личные задачи скроются из списков и останутся в отчётах.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            return
        run_action(self, services.delete_member, self.db, self.user["id"],
                   member_id, refresh=self.notify)
