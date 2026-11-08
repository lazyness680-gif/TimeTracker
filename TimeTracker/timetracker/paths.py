# -*- coding: utf-8 -*-
"""Определение путей приложения (БД по умолчанию, portable-режим)."""

import sys
from pathlib import Path

APP_NAME = "TimeTracker"
DB_DIR_NAME = "data"
DB_FILE_NAME = "timetracker.db"


def default_db_path() -> Path:
    """Путь к БД по умолчанию.

    В собранном (PyInstaller) виде — рядом с exe: ``<папка_exe>\\data\\timetracker.db``.
    При запуске из исходников — ``<корень проекта>\\data\\timetracker.db``.
    Может быть переопределён аргументом ``--db <path>``.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / DB_DIR_NAME / DB_FILE_NAME
