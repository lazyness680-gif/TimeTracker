# -*- coding: utf-8 -*-
"""Вкладка «Отчёты» (только админ): суммарное время по пользователям за период (п.5.5 ТЗ)."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from .. import services
from ..services import fmt_dur


class ReportsTab(QWidget):
    COLS = ["Пользователь", "Задача", "Суммарное время"]

    def __init__(self, db, user):
        super().__init__()
        self.db, self.user = db, user

        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)

        self.cmb_user = QComboBox()
        self.cmb_task = QComboBox()

        self.btn_build = QPushButton("Построить")
        self.btn_build.clicked.connect(self._build)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Период с:"))
        filters.addWidget(self.date_from)
        filters.addWidget(QLabel("по:"))
        filters.addWidget(self.date_to)
        filters.addWidget(QLabel("Пользователь:"))
        filters.addWidget(self.cmb_user)
        filters.addWidget(QLabel("Задача:"))
        filters.addWidget(self.cmb_task)
        filters.addWidget(self.btn_build)
        filters.addStretch(1)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.lbl_total = QLabel("Итого: —")

        lay = QVBoxLayout(self)
        lay.addLayout(filters)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.lbl_total)

        self._load_combos()
        self._build()

    def _load_combos(self):
        self.cmb_user.clear()
        self.cmb_user.addItem("Все пользователи", None)
        for u in services.list_users(self.db):
            label = u["login"] + (" (удалён)" if u["is_deleted"] else "")
            self.cmb_user.addItem(label, u["id"])

        self.cmb_task.clear()
        self.cmb_task.addItem("Все задачи", None)
        for t in self.db.query_all(
                "SELECT id, title, is_archived, is_hidden FROM tasks ORDER BY title"):
            marks = []
            if t["is_archived"]:
                marks.append("архив")
            if t["is_hidden"]:
                marks.append("скрыта")
            label = t["title"] + (f" ({', '.join(marks)})" if marks else "")
            self.cmb_task.addItem(label, t["id"])

    def refresh(self):
        self._load_combos()
        self._build()

    def _build(self):
        d_from = self.date_from.date().toPython()
        d_to = self.date_to.date().toPython()
        if d_from > d_to:
            self.lbl_total.setText("Итого: — (дата «с» больше даты «по»)")
            self.table.setRowCount(0)
            return
        rows = services.report_by_users(
            self.db, d_from, d_to,
            user_id=self.cmb_user.currentData(),
            task_id=self.cmb_task.currentData())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        total = 0
        for i, r in enumerate(rows):
            user_label = r["login"] + (" (удалён)" if r["user_deleted"] else "")
            task_label = r["title"]
            marks = []
            if r["archived"]:
                marks.append("архив")
            if r["hidden"]:
                marks.append("скрыта")
            if marks:
                task_label += f" ({', '.join(marks)})"
            self.table.setItem(i, 0, QTableWidgetItem(user_label))
            self.table.setItem(i, 1, QTableWidgetItem(task_label))
            self.table.setItem(i, 2, QTableWidgetItem(fmt_dur(r["seconds"])))
            total += r["seconds"]
        self.table.setSortingEnabled(True)
        self.lbl_total.setText(
            f"Итого: {fmt_dur(total)}   •   строк: {len(rows)}   "
            f"•   период: {d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}")
