# -*- coding: utf-8 -*-
"""Точка входа TimeTracker (MVP без авторизации).

Порядок запуска:
  1. Аргумент --db <path> (переопределение пути к БД).
  2. Single-instance (named mutex); повторный запуск фокусирует окно.
  3. Открытие БД (WAL) и heartbeat-восстановление открытых интервалов.
  4. Первый запуск -> диалог создания команды (название + первый участник,
     без пароля). Далее сразу главное окно с переключателем участника.
"""

import argparse
import sys

from PySide6.QtWidgets import QApplication


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="TimeTracker", description="Локальный канбан-тайм-трекер команды")
    parser.add_argument("--db", help="путь к файлу базы данных SQLite")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    from timetracker.paths import default_db_path
    db_path = args.db or default_db_path()

    from timetracker.single_instance import SingleInstance, focus_existing_window
    instance = SingleInstance()
    if not instance.acquire():
        focus_existing_window()
        return 0

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("TimeTracker")
    app.setApplicationDisplayName("TimeTracker")
    app.setQuitOnLastWindowClosed(True)

    from timetracker.db import Database
    from timetracker import services
    from timetracker.ui import theme
    from timetracker.ui.first_run import FirstRunDialog
    from timetracker.ui.main_window import MainWindow

    db = Database(db_path)
    recovered = services.recover_open_intervals(db)
    theme.apply(app, theme.current_theme(db))  # светлая/тёмная тема

    if services.count_users(db) == 0:
        dialog = FirstRunDialog(db)
        if dialog.exec() != FirstRunDialog.DialogCode.Accepted:
            return 0

    member = services.current_member(db)
    if member is None:
        return 0

    note = (f"Восстановлено интервалов после сбоя: {recovered}" if recovered else "")
    win = MainWindow(db, member, status_note=note)
    win.show()
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
