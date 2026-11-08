# -*- coding: utf-8 -*-
"""Общие помощники UI: подтверждения, вывод ошибок."""

from PySide6.QtWidgets import QMessageBox

from .. import services


def ask(parent, title: str, text: str) -> bool:
    """Вопрос Да/Нет (по умолчанию — Нет)."""
    ret = QMessageBox.question(
        parent, title, text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    return ret == QMessageBox.StandardButton.Yes


def show_error(parent, exc: Exception):
    QMessageBox.warning(parent, "TimeTracker", str(exc))


def run_action(parent, fn, *args, refresh=None, **kwargs):
    """Выполнить действие с перехватом ошибок бизнес-логики.

    Возвращает результат или None; при успехе вызывает refresh (если задан).
    """
    try:
        result = fn(*args, **kwargs)
    except services.ServiceError as exc:
        show_error(parent, exc)
        return None
    if refresh is not None:
        refresh()
    return result
