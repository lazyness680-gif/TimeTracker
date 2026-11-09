# -*- coding: utf-8 -*-
"""Снимает скриншоты главного окна (светлая/тёмная тема) для лендинга.

Запуск:  python deploy/make_screenshots.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "TimeTracker"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from timetracker import services  # noqa: E402
from timetracker.db import Database  # noqa: E402
from timetracker.ui import theme  # noqa: E402
from timetracker.ui.main_window import MainWindow  # noqa: E402

OUT = ROOT / "site"
OUT.mkdir(exist_ok=True)


def main():
    app = QApplication.instance() or QApplication([])

    tmp = tempfile.mkdtemp(prefix="tt_shot_")
    db = Database(Path(tmp) / "timetracker.db")

    services.set_team_name(db, None, "Демо-команда")
    anna = services.create_member(db, None, "anna")
    boris = services.create_member(db, None, "boris")
    services.set_current_member(db, anna)

    # задачи в разных статусах, чтобы доска выглядела живой
    t_new = services.create_task(db, anna, "Сверстать лендинг", "Готовить макет\nи адаптив",
                                 2, "shared")
    t_prog = services.create_task(db, anna, "Рефакторинг модуля отчётов", "",
                                  1, "shared")
    t_done = services.create_task(db, boris, "Ревью API-слоя", "", 0, "shared")
    t_priv = services.create_task(db, boris, "Личная: план смены", "", 1, "private")

    from datetime import datetime, timedelta
    now = datetime.now()

    def close_entry(uid, tid, start, minutes):
        db.execute(
            "INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
            "VALUES(?,?,?,?, 'user')",
            (tid, uid, start.strftime(services.TS_FMT),
             (start + timedelta(minutes=minutes)).strftime(services.TS_FMT)))

    close_entry(anna, t_done, now - timedelta(hours=3), 45)
    close_entry(boris, t_done, now - timedelta(hours=2, minutes=30), 30)

    # активные интервалы: у anna два, у boris один по общей задаче
    services.start_interval(db, anna, t_new)
    services.start_interval(db, anna, t_prog)
    services.start_interval(db, boris, t_prog)

    win = MainWindow(db, services.current_member(db))
    win.resize(1280, 800)
    win.show()
    for _ in range(3):
        app.processEvents()

    for name, key in (("screenshot-light", "light"), ("screenshot-dark", "dark")):
        theme.apply(app, key)
        app.processEvents()
        path = OUT / f"{name}.png"
        if not win.grab().save(str(path)):
            raise SystemExit(f"не удалось сохранить {path}")
        print("saved", path)

    win.deleteLater()
    print("OK")


if __name__ == "__main__":
    main()
