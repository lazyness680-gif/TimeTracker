# -*- coding: utf-8 -*-
"""Канбан-доска «Задачи»: колонки = вычисляемые статусы (Новая / В работе /
Завершена), карточки перетаскиваются мышью.

Перенос в «В работе» запускает интервал текущего участника, в «Завершена» —
останавливает его (с подтверждением). Статус по-прежнему вычисляется из
интервалов, поэтому данные не могут «разойтись» с доской.
"""

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag, QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from .. import services
from ..services import fmt_dur
from .dialogs import TaskCardDialog, TaskDialog
from .util import ask, run_action

MIME_TYPE = "application/x-timetracker-task"
STATUS_COLS = [("new", "Новая"), ("in_progress", "В работе"), ("done", "Завершена")]
VIS_FILTERS = [("all", "Вся видимость"), ("mine", "Мои"), ("shared", "Общие")]


# ------------------------------------------------------------------ карточка

class TaskCard(QFrame):
    """Карточка задачи на доске: тянете мышью — меняете статус; двойной клик —
    подробная карточка задачи."""

    def __init__(self, row, board):
        super().__init__()
        self.row, self.board = row, board
        self._drag_start = None
        self.setObjectName("card")
        self.setProperty("prio", str(row["priority"]))
        self.setProperty("active", "true" if row["status"] == "in_progress" else "false")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(200)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        title_font = QFont()
        title_font.setBold(True)
        lbl_title = QLabel(row["title"])
        lbl_title.setFont(title_font)
        lbl_title.setWordWrap(True)
        lay.addWidget(lbl_title)

        prio = QLabel(f"{services.PRIORITY_LABELS[row['priority']]} · "
                      f"{services.VISIBILITY_LABELS[row['visibility']]}")
        prio.setObjectName("prio")
        prio.setProperty("prio", str(row["priority"]))
        lay.addWidget(prio)

        lay.addWidget(QLabel(f"Всего: {fmt_dur(row['total_seconds'])}   "
                             f"Моё: {fmt_dur(row['my_seconds'])}"))

        workers = QLabel("Работают: " + (", ".join(row["workers"]) or "—"))
        workers.setWordWrap(True)
        lay.addWidget(workers)

        self.lbl_live = QLabel()
        self.lbl_live.setObjectName("liveTimer")
        live_font = QFont("Consolas")
        live_font.setStyleHint(QFont.StyleHint.Monospace)
        self.lbl_live.setFont(live_font)
        if row["i_work"]:
            self.lbl_live.setText("⏱ " + fmt_dur(services.elapsed_since(
                row["my_open_started"])))
        else:
            self.lbl_live.hide()
        lay.addWidget(self.lbl_live)

        btn_toggle = QPushButton("Завершить" if row["i_work"] else "Старт")
        btn_toggle.setEnabled(not row["is_archived"])
        btn_toggle.clicked.connect(lambda _=False: self.board.toggle_task(self.row["id"]))
        btn_card = QPushButton("Карточка…")
        btn_card.clicked.connect(lambda _=False: self.board.open_card(self.row["id"]))

        btns = QHBoxLayout()
        btns.setSpacing(4)
        btns.addWidget(btn_toggle)
        btns.addWidget(btn_card)
        lay.addLayout(btns)

    # ----- drag & drop -----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start is None:
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() \
                < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_TYPE, str(self.row["id"]).encode("utf-8"))
        drag.setMimeData(mime)
        pixmap = self.grab()
        if pixmap.width() > 280:
            pixmap = pixmap.scaledToWidth(280)
        drag.setPixmap(pixmap)
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start = None

    def mouseDoubleClickEvent(self, event):
        self.board.open_card(self.row["id"])
        super().mouseDoubleClickEvent(event)

    def tick(self):
        if self.row["i_work"] and self.lbl_live.isVisible():
            self.lbl_live.setText("⏱ " + fmt_dur(services.elapsed_since(
                self.row["my_open_started"])))


# ------------------------------------------------------------------ колонка

class BoardColumn(QFrame):
    """Колонка доски: принимает перетаскиваемые карточки."""

    def __init__(self, key, title, on_drop):
        super().__init__()
        self.key, self.on_drop = key, on_drop
        self.setObjectName(f"col_{key}")
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.cards = []

        self.lbl_title = QLabel(f"{title}  ")
        self.lbl_title.setProperty("colTitle", "1")
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self.lbl_title.setFont(font)

        head = QHBoxLayout()
        head.addWidget(self.lbl_title)
        head.addStretch(1)

        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(6)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addLayout(head)
        lay.addLayout(self.cards_layout)
        lay.addStretch(1)

    def set_count(self, n: int):
        title = dict(STATUS_COLS)[self.key]
        self.lbl_title.setText(f"{title}  ({n})")

    def add_card(self, card: TaskCard):
        self.cards.append(card)
        self.cards_layout.addWidget(card)

    def clear_cards(self):
        for c in self.cards:
            self.cards_layout.removeWidget(c)
            c.deleteLater()
        self.cards = []

    # ----- подсветка и приёмка -----

    def _highlighted(self, on: bool):
        """Подсветка колонки при перетаскивании (через свойство QSS)."""
        self.setProperty("drop", "true" if on else "false")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    @staticmethod
    def _task_id(event):
        mime = event.mimeData()
        if not mime.hasFormat(MIME_TYPE):
            return None
        try:
            return int(bytes(mime.data(MIME_TYPE)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def dragEnterEvent(self, event):
        if self._task_id(event) is not None:
            self._highlighted(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._task_id(event) is not None:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._highlighted(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._highlighted(False)
        task_id = self._task_id(event)
        if task_id is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.on_drop(self.key, task_id)


# ------------------------------------------------------------------ доска

class BoardTab(QWidget):
    def __init__(self, db, user, notify_changed):
        super().__init__()
        self.db, self.user, self.notify = db, user, notify_changed
        self._rows = {}          # task_id -> строка list_tasks
        self._columns = {}

        self.btn_new = QPushButton("Создать задачу")
        self.btn_new.clicked.connect(self._on_new)

        self.cmb_vis = QComboBox()
        for key, label in VIS_FILTERS:
            self.cmb_vis.addItem(label, key)
        self.chk_archive = QCheckBox("Показать архив")
        self.cmb_vis.currentIndexChanged.connect(self.refresh)
        self.chk_archive.toggled.connect(self.refresh)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.btn_new)
        toolbar.addStretch(1)
        toolbar.addWidget(self.cmb_vis)
        toolbar.addWidget(self.chk_archive)

        board = QHBoxLayout()
        board.setSpacing(8)
        for key, title in STATUS_COLS:
            col = BoardColumn(key, title, self._on_drop)
            self._columns[key] = col
            board.addWidget(col, 1)

        lay = QVBoxLayout(self)
        lay.addLayout(toolbar)
        lay.addLayout(board, 1)

        self.refresh()

    # ---------- данные ----------

    def refresh(self):
        rows = services.list_tasks(
            self.db, self.user["id"],
            visibility=self.cmb_vis.currentData(),
            show_archived=self.chk_archive.isChecked())
        self._rows = {r["id"]: r for r in rows}
        for key, col in self._columns.items():
            col.clear_cards()
        for r in rows:
            self._columns[r["status"]].add_card(TaskCard(r, self))
        for key, col in self._columns.items():
            col.set_count(sum(1 for r in rows if r["status"] == key))

    def tick(self):
        for col in self._columns.values():
            for card in col.cards:
                card.tick()

    # ---------- открытие карточки и старт/стоп кнопкой ----------

    def open_card(self, task_id):
        dlg = TaskCardDialog(self, self.db, self.user, task_id, notify=self.notify)
        dlg.exec()

    def toggle_task(self, task_id):
        row = self._rows.get(task_id)
        if row is None:
            return
        if row["i_work"]:
            self._confirm_and_stop(row)
        else:
            run_action(self, services.start_interval, self.db,
                       self.user["id"], task_id, refresh=self.notify)

    def _confirm_and_stop(self, row):
        seconds = services.elapsed_since(row["my_open_started"])
        if not ask(self, "Завершение",
                   f"Завершить задачу «{row['title']}»? "
                   f"Длительность: {fmt_dur(seconds)}"):
            self.notify()  # вернуть карточку на место
            return
        run_action(self, services.stop_interval, self.db, self.user["id"],
                   row["id"], "user", refresh=self.notify)

    # ---------- действия доски ----------

    def _on_new(self):
        dlg = TaskDialog(self, self.db, self.user)
        if dlg.exec() == TaskDialog.DialogCode.Accepted:
            v = dlg.values()
            run_action(self, services.create_task, self.db, self.user["id"],
                       v["title"], v["description"], v["priority"],
                       v["visibility"], v["owner_id"], refresh=self.notify)

    def _on_drop(self, column_key, task_id):
        """Перенос карточки: статусы вычисляются из интервалов, поэтому
        перенос = старт/останов интервала текущего участника."""
        row = self._rows.get(task_id)
        if row is None:
            self.notify()
            return
        if row["is_archived"]:
            QMessageBox.information(self, "TimeTracker",
                                    "Архивная задача недоступна для переноса. "
                                    "Снимите её с архива.")
            self.notify()
            return
        if column_key == row["status"]:
            return

        if column_key == "in_progress":
            if row["i_work"]:
                return
            run_action(self, services.start_interval, self.db,
                       self.user["id"], task_id, refresh=self.notify)

        elif column_key == "done":
            if not row["i_work"]:
                QMessageBox.information(
                    self, "TimeTracker",
                    "Перенос в «Завершена» закрывает только ваш интервал.\n"
                    "У вас нет активного интервала по этой задаче.")
                self.notify()
                return
            self._confirm_and_stop(row)

        elif column_key == "new":
            if row["interval_count"] == 0:
                return  # интервалов нет — задача и так «Новая»
            QMessageBox.information(
                self, "TimeTracker",
                "У задачи уже есть интервалы — статус «Новая» недоступен.\n"
                "Если задача не нужна — архивируйте её.")
            self.notify()
