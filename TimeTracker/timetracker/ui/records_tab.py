# -*- coding: utf-8 -*-
"""Вкладка «Мои записи»: просмотр своих записей времени за период
(п.2 ТЗ — право «Пользователь»; видна и админу, т.к. его права — надмножество)."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit,
                               QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from .. import services
from ..services import fmt_dt, fmt_dur


class RecordsTab(QWidget):
    COLS = ["Задача", "Начало", "Окончание", "Длительность", "Как закрыт"]

    def __init__(self, db, user):
        super().__init__()
        self.db, self.user = db, user

        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setCalendarPopup(True)

        self.cmb_task = QComboBox()

        self.btn_build = QPushButton("Показать")
        self.btn_build.clicked.connect(self._build)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Период с:"))
        filters.addWidget(self.date_from)
        filters.addWidget(QLabel("по:"))
        filters.addWidget(self.date_to)
        filters.addWidget(QLabel("Задача:"))
        filters.addWidget(self.cmb_task)
        filters.addWidget(self.btn_build)
        filters.addStretch(1)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        self.lbl_total = QLabel("Итого: —")

        lay = QVBoxLayout(self)
        lay.addLayout(filters)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.lbl_total)

        self._open_cells = []  # [(row_index, started_at)] — открытые интервалы
        self._load_tasks()
        self._build()

    # ---------- данные ----------

    def _load_tasks(self):
        current = self.cmb_task.currentData()
        self.cmb_task.clear()
        self.cmb_task.addItem("Все задачи", None)
        for t in services.list_tasks_for_user_combobox(self.db, self.user["id"]):
            label = t["title"] + (" (архив)" if t["is_archived"] else "")
            self.cmb_task.addItem(label, t["id"])
        idx = self.cmb_task.findData(current)
        if idx >= 0:
            self.cmb_task.setCurrentIndex(idx)

    def refresh(self):
        self._load_tasks()
        self._build()

    def _build(self):
        d_from = self.date_from.date().toPython()
        d_to = self.date_to.date().toPython()
        if d_from > d_to:
            self.lbl_total.setText("Итого: — (дата «с» больше даты «по»)")
            self.table.setRowCount(0)
            return
        rows = services.list_my_entries(
            self.db, self.user["id"], d_from, d_to,
            task_id=self.cmb_task.currentData())

        self.table.setRowCount(len(rows))
        self._open_cells = []
        total = 0.0
        open_count = 0
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["title"]))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_dt(r["started_at"])))
            self.table.setItem(i, 2, QTableWidgetItem(fmt_dt(r["finished_at"])))
            self.table.setItem(i, 3, QTableWidgetItem(fmt_dur(r["seconds"])))
            if r["finished_at"]:
                closed_label = services.CLOSED_BY_LABELS.get(
                    r["closed_by"], r["closed_by"] or "—")
                total += r["seconds"]
            else:
                closed_label = "— (открыт)"
                self._open_cells.append((i, r["started_at"]))
                open_count += 1
            self.table.setItem(i, 4, QTableWidgetItem(closed_label))

        period = f"{d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}"
        extra = f"   •   открытых: {open_count}" if open_count else ""
        self.lbl_total.setText(
            f"Итого (закрытые): {fmt_dur(total)}   •   строк: {len(rows)}"
            f"{extra}   •   период: {period}")

    def tick(self):
        """Ежесекундное обновление длительностей открытых интервалов."""
        for row, started in self._open_cells:
            item = self.table.item(row, 3)
            if item is not None:
                item.setText(fmt_dur(services.elapsed_since(started)))
