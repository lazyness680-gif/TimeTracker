# -*- coding: utf-8 -*-
"""Вкладка «Шаблоны»: CRUD + «Создать задачу» и «Быстрый старт» (п.5.3 ТЗ)."""

from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from .. import services
from ..services import VISIBILITY_LABELS, fmt_dt
from .dialogs import TaskDialog, TemplateDialog
from .util import ask, run_action


class TemplatesTab(QWidget):
    COLS = ["Название", "Задача по умолчанию", "Приоритет", "Видимость",
            "Владелец", "Создан", "Действия"]

    def __init__(self, db, user, notify_changed):
        super().__init__()
        self.db, self.user, self.notify = db, user, notify_changed
        self._rows = []

        self.btn_new = QPushButton("Создать шаблон")
        self.btn_new.clicked.connect(self._on_new)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.btn_new)
        toolbar.addStretch(1)

        lay = QVBoxLayout(self)
        lay.addLayout(toolbar)
        lay.addWidget(self.table, 1)

        self.refresh()

    def refresh(self):
        rows = services.list_templates(self.db, self.user["id"])
        self._rows = rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["default_title"]))
            self.table.setItem(i, 2, QTableWidgetItem(
                services.PRIORITY_LABELS[r["default_priority"]]))
            self.table.setItem(i, 3, QTableWidgetItem(
                VISIBILITY_LABELS[r["visibility"]]))
            owner = r["owner_login"] + (" (удалённый пользователь)" if r["owner_deleted"] else "")
            self.table.setItem(i, 4, QTableWidgetItem(owner))
            self.table.setItem(i, 5, QTableWidgetItem(fmt_dt(r["created_at"])))
            self.table.setCellWidget(i, 6, self._actions_widget(r))

    def _actions_widget(self, r) -> QWidget:
        is_admin = self.user["role"] == "admin"
        can_edit = is_admin or r["owner_id"] == self.user["id"]

        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        btn_create = QPushButton("Создать задачу")
        btn_create.clicked.connect(
            lambda _=False, tid=r["id"]: self._on_create_task(tid))
        btn_quick = QPushButton("Быстрый старт")
        btn_quick.clicked.connect(
            lambda _=False, tid=r["id"]: self._on_quick_start(tid))
        btn_edit = QPushButton("Изменить")
        btn_edit.setEnabled(can_edit)
        btn_edit.clicked.connect(
            lambda _=False, tid=r["id"]: self._on_edit(tid))
        btn_delete = QPushButton("Удалить")
        btn_delete.setEnabled(can_edit)
        btn_delete.clicked.connect(
            lambda _=False, tid=r["id"]: self._on_delete(tid))

        for b in (btn_create, btn_quick, btn_edit, btn_delete):
            lay.addWidget(b)
        return w

    def _row_by_id(self, template_id):
        for r in self._rows:
            if r["id"] == template_id:
                return r
        return services.get_template(self.db, template_id)

    def _on_new(self):
        dlg = TemplateDialog(self)
        if dlg.exec() == TemplateDialog.DialogCode.Accepted:
            v = dlg.values()
            run_action(self, services.create_template, self.db, self.user["id"],
                       v["name"], v["default_title"], v["default_description"],
                       v["default_priority"], v["visibility"], refresh=self.notify)

    def _on_edit(self, template_id):
        tpl = services.get_template(self.db, template_id)
        if tpl is None:
            return
        dlg = TemplateDialog(self, template=tpl)
        if dlg.exec() == TemplateDialog.DialogCode.Accepted:
            v = dlg.values()
            run_action(self, services.update_template, self.db, self.user["id"],
                       template_id, v["name"], v["default_title"],
                       v["default_description"], v["default_priority"],
                       v["visibility"], refresh=self.notify)

    def _on_double_clicked(self, item):
        row = item.row()
        if row < len(self._rows):
            r = self._rows[row]
            if self.user["role"] == "admin" or r["owner_id"] == self.user["id"]:
                self._on_edit(r["id"])

    def _on_delete(self, template_id):
        tpl = services.get_template(self.db, template_id)
        if tpl is None:
            return
        if not ask(self, "Удаление",
                   f"Удалить шаблон «{tpl['name']}»?"):
            return
        run_action(self, services.delete_template, self.db, self.user["id"],
                   template_id, refresh=self.notify)

    def _on_create_task(self, template_id):
        """Заполняет поля диалога задачи из шаблона (без старта)."""
        tpl = services.get_template(self.db, template_id)
        if tpl is None:
            return
        dlg = TaskDialog(self, self.db, self.user, preset={
            "title": tpl["default_title"],
            "description": tpl["default_description"] or "",
            "priority": tpl["default_priority"],
            "visibility": tpl["visibility"],
        })
        if dlg.exec() == TaskDialog.DialogCode.Accepted:
            v = dlg.values()
            run_action(self, services.create_task, self.db, self.user["id"],
                       v["title"], v["description"], v["priority"],
                       v["visibility"], v["owner_id"], refresh=self.notify)

    def _on_quick_start(self, template_id):
        """Одной кнопкой создаёт задачу и сразу открывает интервал."""
        run_action(self, services.quick_start, self.db, self.user["id"],
                   template_id, refresh=self.notify)
