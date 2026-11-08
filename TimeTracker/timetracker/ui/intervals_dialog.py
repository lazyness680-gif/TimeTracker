# -*- coding: utf-8 -*-
"""Диалог «Интервалы задачи»: список всех интервалов; админ может их редактировать."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout,
                               QHeaderView, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from .. import services
from ..services import fmt_dt, fmt_dur
from .dialogs import EditIntervalDialog
from .util import run_action


class IntervalsDialog(QDialog):
    COLS = ["Пользователь", "Начало", "Окончание", "Длительность", "Как закрыт"]

    def __init__(self, parent, db, user, task_id):
        super().__init__(parent)
        self.db, self.user, self.task_id = db, user, task_id
        task = services.get_task(db, task_id)
        self.setWindowTitle(f"Интервалы — «{task['title'] if task else '?'}»")
        self.setMinimumSize(720, 420)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit() if self._is_admin else None)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.reload)
        self.btn_edit = QPushButton("Редактировать…")
        self.btn_edit.clicked.connect(self._edit)
        self.btn_close = QPushButton("Закрыть")
        self.btn_close.setObjectName("secondary")
        self.btn_close.clicked.connect(self.accept)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_refresh)
        btns.addWidget(self.btn_edit)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)

        lay = QVBoxLayout(self)
        lay.addWidget(self.table)
        lay.addLayout(btns)

        self._is_admin = user["role"] == "admin"
        self.btn_edit.setVisible(self._is_admin)

        # живое обновление длительностей открытых интервалов — раз в секунду
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        self.reload()

    def reload(self):
        rows = services.list_intervals(self.db, self.task_id)
        self._rows = rows
        self.table.setRowCount(len(rows))
        self._open_cells = []  # (row_index, started_at)
        for i, r in enumerate(rows):
            login = r["login"] + (" (удалённый пользователь)" if r["user_deleted"] else "")
            self.table.setItem(i, 0, QTableWidgetItem(login))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_dt(r["started_at"])))
            self.table.setItem(i, 2, QTableWidgetItem(fmt_dt(r["finished_at"])))
            if r["finished_at"]:
                dur = (services.parse_ts(r["finished_at"])
                       - services.parse_ts(r["started_at"])).total_seconds()
                self.table.setItem(i, 3, QTableWidgetItem(fmt_dur(dur)))
                closed_label = services.CLOSED_BY_LABELS.get(r["closed_by"], r["closed_by"] or "—")
            else:
                self._open_cells.append((i, r["started_at"]))
                self.table.setItem(i, 3, QTableWidgetItem(fmt_dur(
                    services.open_interval_seconds(r))))
                closed_label = "— (открыт)"
            self.table.setItem(i, 4, QTableWidgetItem(closed_label))

    def _tick(self):
        """Пересчёт длительностей открытых интервалов раз в секунду."""
        if not getattr(self, "_open_cells", None):
            return
        for row, started in self._open_cells:
            elapsed = services.elapsed_since(started)
            item = self.table.item(row, 3)
            if item is not None:
                item.setText(fmt_dur(elapsed))

    def _edit(self):
        row = self.table.currentRow()
        if row < 0 or not getattr(self, "_rows", None):
            return
        entry = self._rows[row]
        dlg = EditIntervalDialog(self, entry)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            started, finished = dlg.values()
            run_action(self, services.update_interval,
                       self.db, self.user["id"], entry["id"], started, finished,
                       refresh=self.reload)
