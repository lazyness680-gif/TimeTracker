# -*- coding: utf-8 -*-
"""Первый запуск без авторизации: создаём команду и первого участника
(без пароля — вход в MVP не используется)."""

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
                               QLabel, QLineEdit, QVBoxLayout)

from .. import services
from .util import show_error


class FirstRunDialog(QDialog):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("TimeTracker — создание команды")
        self.setMinimumWidth(420)

        lbl = QLabel(
            "Авторизация в MVP не используется: участники переключаются "
            "в шапке приложения без пароля.")
        lbl.setWordWrap(True)

        self.ed_team = QLineEdit(services.DEFAULT_TEAM_NAME)
        self.ed_team.setMaxLength(64)
        self.ed_member = QLineEdit()
        self.ed_member.setMaxLength(services.LOGIN_MAX)
        self.ed_member.setPlaceholderText("например: Команда")

        form = QFormLayout()
        form.addRow("Название команды*:", self.ed_team)
        form.addRow("Имя первого участника*:", self.ed_member)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Создать")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Выход")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secondary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(lbl)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def accept(self):
        team = self.ed_team.text().strip()
        member = self.ed_member.text().strip()
        if not member:
            member = "Команда"
        try:
            services.set_team_name(self.db, None, team)
            services.create_member(self.db, None, member)
        except services.ServiceError as exc:
            show_error(self, exc)
            return
        super().accept()
