# -*- coding: utf-8 -*-
"""Диалоги: задача (и её карточка), шаблон, редактирование интервала."""

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout,
                               QDateTimeEdit)

from .. import services
from .util import ask, run_action


class TaskDialog(QDialog):
    """Создание/редактирование задачи. Владельца меняет только администратор."""

    def __init__(self, parent, db, user, task=None, preset: dict | None = None):
        super().__init__(parent)
        self.db, self.user, self.task = db, user, task
        self.setWindowTitle("Редактирование задачи" if task else "Новая задача")
        self.setMinimumWidth(460)

        self.ed_title = QLineEdit()
        self.ed_title.setMaxLength(200)
        self.ed_description = QPlainTextEdit()
        self.ed_description.setMaximumHeight(100)
        self.cmb_priority = QComboBox()
        for key, label in services.PRIORITY_LABELS.items():
            self.cmb_priority.addItem(label, key)
        self.cmb_visibility = QComboBox()
        self.cmb_visibility.addItem(services.VISIBILITY_LABELS["private"], "private")
        self.cmb_visibility.addItem(services.VISIBILITY_LABELS["shared"], "shared")

        form = QFormLayout()
        form.addRow("Название*:", self.ed_title)
        form.addRow("Описание:", self.ed_description)
        form.addRow("Приоритет:", self.cmb_priority)
        form.addRow("Видимость:", self.cmb_visibility)

        self.cmb_owner = None
        if user["role"] == "admin":
            self.cmb_owner = QComboBox()
            for u in services.list_users(db):
                if u["is_deleted"]:
                    continue
                self.cmb_owner.addItem(u["login"], u["id"])
            form.addRow("Владелец:", self.cmb_owner)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Сохранить")
        _cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        _cancel.setText("Отмена")
        _cancel.setObjectName("secondary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

        if task is not None:
            self.ed_title.setText(task["title"])
            self.ed_description.setPlainText(task["description"] or "")
            self.cmb_priority.setCurrentIndex(task["priority"])
            self.cmb_visibility.setCurrentIndex(
                0 if task["visibility"] == "private" else 1)
            if self.cmb_owner is not None:
                idx = self.cmb_owner.findData(task["owner_id"])
                if idx < 0:  # владелец удалён — добавляем помеченным
                    owner = services.get_user(db, task["owner_id"])
                    login = owner["login"] if owner else "?"
                    self.cmb_owner.addItem(f"{login} (удалённый пользователь)", task["owner_id"])
                    idx = self.cmb_owner.count() - 1
                self.cmb_owner.setCurrentIndex(idx)
        elif preset:
            self.ed_title.setText(preset.get("title", ""))
            self.ed_description.setPlainText(preset.get("description", ""))
            self.cmb_priority.setCurrentIndex(preset.get("priority", 1))
            self.cmb_visibility.setCurrentIndex(
                0 if preset.get("visibility", "private") == "private" else 1)

    def values(self) -> dict:
        owner_id = self.user["id"]
        if self.cmb_owner is not None and self.cmb_owner.currentData() is not None:
            owner_id = self.cmb_owner.currentData()
        return {
            "title": self.ed_title.text().strip(),
            "description": self.ed_description.toPlainText().strip(),
            "priority": self.cmb_priority.currentData(),
            "visibility": self.cmb_visibility.currentData(),
            "owner_id": owner_id,
        }


class TemplateDialog(QDialog):
    """Создание/редактирование шаблона задачи."""

    def __init__(self, parent, template=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование шаблона" if template else "Новый шаблон")
        self.setMinimumWidth(460)

        self.ed_name = QLineEdit()
        self.ed_title = QLineEdit()
        self.ed_title.setMaxLength(200)
        self.ed_description = QPlainTextEdit()
        self.ed_description.setMaximumHeight(100)
        self.cmb_priority = QComboBox()
        for key, label in services.PRIORITY_LABELS.items():
            self.cmb_priority.addItem(label, key)
        self.cmb_visibility = QComboBox()
        self.cmb_visibility.addItem(services.VISIBILITY_LABELS["private"], "private")
        self.cmb_visibility.addItem(services.VISIBILITY_LABELS["shared"], "shared")

        form = QFormLayout()
        form.addRow("Название шаблона*:", self.ed_name)
        form.addRow("Название задачи по умолчанию*:", self.ed_title)
        form.addRow("Описание:", self.ed_description)
        form.addRow("Приоритет:", self.cmb_priority)
        form.addRow("Видимость:", self.cmb_visibility)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Сохранить")
        _cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        _cancel.setText("Отмена")
        _cancel.setObjectName("secondary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

        if template is not None:
            self.ed_name.setText(template["name"])
            self.ed_title.setText(template["default_title"])
            self.ed_description.setPlainText(template["default_description"] or "")
            self.cmb_priority.setCurrentIndex(template["default_priority"])
            self.cmb_visibility.setCurrentIndex(
                0 if template["visibility"] == "private" else 1)

    def values(self) -> dict:
        return {
            "name": self.ed_name.text().strip(),
            "default_title": self.ed_title.text().strip(),
            "default_description": self.ed_description.toPlainText().strip(),
            "default_priority": self.cmb_priority.currentData(),
            "visibility": self.cmb_visibility.currentData(),
        }


class EditIntervalDialog(QDialog):
    """Редактирование интервала (только админ). Начало/окончание, флаг «закрыт»."""

    def __init__(self, parent, entry):
        super().__init__(parent)
        self.setWindowTitle("Редактирование интервала")
        self.setMinimumWidth(380)

        self.ed_started = QDateTimeEdit()
        self.ed_started.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.ed_started.setCalendarPopup(True)
        self.chk_closed = QCheckBox("Интервал закрыт")
        self.ed_finished = QDateTimeEdit()
        self.ed_finished.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.ed_finished.setCalendarPopup(True)
        self.ed_finished.setEnabled(False)
        self.chk_closed.toggled.connect(self.ed_finished.setEnabled)

        started = services.parse_ts(entry["started_at"])
        self.ed_started.setDateTime(QDateTime(started))
        if entry["finished_at"]:
            self.chk_closed.setChecked(True)
            finished = services.parse_ts(entry["finished_at"])
            self.ed_finished.setDateTime(QDateTime(finished))
        else:
            self.chk_closed.setChecked(False)

        form = QFormLayout()
        form.addRow("Начало:", self.ed_started)
        form.addRow(self.chk_closed)
        form.addRow("Окончание:", self.ed_finished)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Сохранить")
        _cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        _cancel.setText("Отмена")
        _cancel.setObjectName("secondary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def values(self):
        started = self.ed_started.dateTime().toPython()
        finished = self.ed_finished.dateTime().toPython() if self.chk_closed.isChecked() else None
        return (started.strftime(services.TS_FMT),
                finished.strftime(services.TS_FMT) if finished else None)


class TaskCardDialog(QDialog):
    """Карточка задачи: подробности, суммарное время, живой таймер и действия."""

    def __init__(self, parent, db, user, task_id, notify=None):
        super().__init__(parent)
        self.db, self.user, self.task_id, self.notify = db, user, task_id, notify
        self.setWindowTitle("Карточка задачи")
        self.setMinimumSize(640, 520)
        self._open_started = None  # started_at моего открытого интервала

        self.lbl_title = QLabel()
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        self.lbl_title.setFont(title_font)
        self.lbl_status = QLabel()

        self.ed_description = QPlainTextEdit()
        self.ed_description.setReadOnly(True)

        self.lbl_priority = QLabel()
        self.lbl_visibility = QLabel()
        self.lbl_owner = QLabel()
        self.lbl_created = QLabel()
        self.lbl_archived = QLabel()
        self.lbl_total = QLabel()
        self.lbl_mine = QLabel()
        self.lbl_workers = QLabel()
        self.lbl_live = QLabel()
        live_font = QFont("Consolas")
        live_font.setStyleHint(QFont.StyleHint.Monospace)
        self.lbl_live.setFont(live_font)

        info = QFormLayout()
        info.addRow("Статус:", self.lbl_status)
        info.addRow("Приоритет:", self.lbl_priority)
        info.addRow("Видимость:", self.lbl_visibility)
        info.addRow("Владелец:", self.lbl_owner)
        info.addRow("Создана:", self.lbl_created)
        info.addRow("Архивирована:", self.lbl_archived)
        info.addRow("Время по всем:", self.lbl_total)
        info.addRow("Моё время:", self.lbl_mine)
        info.addRow("Кто работает:", self.lbl_workers)
        info.addRow("Сейчас идёт:", self.lbl_live)

        self.btn_toggle = QPushButton("Старт")
        self.btn_toggle.clicked.connect(self._on_toggle)
        self.btn_edit = QPushButton("Изменить…")
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_intervals = QPushButton("Интервалы…")
        self.btn_intervals.clicked.connect(self._on_intervals)
        self.btn_archive = QPushButton("Архивировать")
        self.btn_archive.clicked.connect(self._on_archive)
        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_close = QPushButton("Закрыть")
        self.btn_close.setObjectName("secondary")
        self.btn_close.clicked.connect(self.accept)

        btns = QHBoxLayout()
        for b in (self.btn_toggle, self.btn_edit, self.btn_intervals,
                  self.btn_archive, self.btn_delete):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.ed_description, 1)
        lay.addLayout(info)
        lay.addLayout(btns)

        self.reload()

    # ---------- данные ----------

    def _aggregate_row(self):
        """Строка с вычисляемыми агрегатами (обычная или архивная)."""
        for archived in (False, True):
            for r in services.list_tasks(self.db, self.user["id"],
                                         show_archived=archived):
                if r["id"] == self.task_id:
                    return r
        return None

    def reload(self):
        task = services.get_task(self.db, self.task_id)
        if task is None:
            self.accept()  # задача удалена — закрываем карточку
            return
        row = self._aggregate_row()
        if row is None:
            self.accept()
            return

        title = task["title"] + ("  [архив]" if task["is_archived"] else "")
        self.lbl_title.setText(title)
        self.lbl_status.setText(services.STATUS_LABELS[row["status"]])
        self.ed_description.setPlainText(task["description"] or "—")
        self.lbl_priority.setText(services.PRIORITY_LABELS[task["priority"]])
        self.lbl_visibility.setText(services.VISIBILITY_LABELS[task["visibility"]])
        owner = services.get_user(self.db, task["owner_id"])
        owner_name = owner["login"] if owner else "?"
        if owner and owner["is_deleted"]:
            owner_name += " (удалённый участник)"
        self.lbl_owner.setText(owner_name)
        self.lbl_created.setText(services.fmt_dt(task["created_at"]))
        self.lbl_archived.setText(services.fmt_dt(task["archived_at"]))
        self.lbl_total.setText(services.fmt_dur(row["total_seconds"]))
        self.lbl_mine.setText(services.fmt_dur(row["my_seconds"]))
        self.lbl_workers.setText(", ".join(row["workers"]) or "—")

        self._open_started = row["my_open_started"]
        if self._open_started:
            self.lbl_live.setText(
                services.fmt_dur(services.elapsed_since(self._open_started)))
        else:
            self.lbl_live.setText("—")

        # состояния кнопок
        self.btn_toggle.setText("Завершить" if row["i_work"] else "Старт")
        self.btn_toggle.setEnabled(not task["is_archived"])
        can_edit = services.can_edit_task(self.user, task)
        self.btn_edit.setEnabled(can_edit)
        self.btn_archive.setEnabled(can_edit and not task["is_archived"])
        self.btn_delete.setEnabled(can_edit and row["interval_count"] == 0)

    def tick(self):
        """Ежесекундное обновление живого таймера."""
        if self._open_started:
            self.lbl_live.setText(
                services.fmt_dur(services.elapsed_since(self._open_started)))

    # ---------- действия ----------

    def _after(self):
        self.reload()
        if self.notify is not None:
            self.notify()

    def _on_toggle(self):
        task = services.get_task(self.db, self.task_id)
        if task is None:
            return
        if self._open_started:
            if not ask(self, "Завершение",
                       f"Завершить задачу «{task['title']}»? "
                       f"Длительность: {services.fmt_dur(services.elapsed_since(self._open_started))}"):
                return
            run_action(self, services.stop_interval, self.db, self.user["id"],
                       self.task_id, "user", refresh=self._after)
        else:
            run_action(self, services.start_interval, self.db, self.user["id"],
                       self.task_id, refresh=self._after)

    def _on_edit(self):
        task = services.get_task(self.db, self.task_id)
        if task is None:
            return
        dlg = TaskDialog(self, self.db, self.user, task=task)
        if dlg.exec() == TaskDialog.DialogCode.Accepted:
            v = dlg.values()
            run_action(self, services.update_task, self.db, self.user["id"],
                       self.task_id, v["title"], v["description"], v["priority"],
                       v["visibility"], v["owner_id"], refresh=self._after)

    def _on_intervals(self):
        from .intervals_dialog import IntervalsDialog
        dlg = IntervalsDialog(self, self.db, self.user, self.task_id)
        dlg.exec()
        self._after()

    def _on_archive(self):
        task = services.get_task(self.db, self.task_id)
        if task is None:
            return
        if not ask(self, "Архивация",
                   f"Архивировать задачу «{task['title']}»?"):
            return
        run_action(self, services.archive_task, self.db, self.user["id"],
                   self.task_id, refresh=self._after)

    def _on_delete(self):
        task = services.get_task(self.db, self.task_id)
        if task is None:
            return
        if not ask(self, "Удаление",
                   f"Удалить задачу «{task['title']}»? Действие необратимо."):
            return
        run_action(self, services.delete_task, self.db, self.user["id"],
                   self.task_id, refresh=self._after)
