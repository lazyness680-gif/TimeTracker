# -*- coding: utf-8 -*-
"""Приёмочные тесты TimeTracker (MVP без авторизации).

Покрытие: сценарии канбан-доски и тайм-трекинга, участники команды,
профиль команды, записи времени, отчёты, heartbeat, аудит, UI (offscreen).

Запуск:  python tests/test_acceptance.py
"""

import os
import sys
import tempfile
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1] / "TimeTracker"
sys.path.insert(0, str(ROOT))

from timetracker import services  # noqa: E402
from timetracker.db import Database  # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  [OK]   {name}")
    except Exception:
        FAIL.append(name)
        print(f"  [FAIL] {name}")
        traceback.print_exc()


def make_db():
    tmp = tempfile.mkdtemp(prefix="tt_test_")
    return Database(Path(tmp) / "timetracker.db")


def ts(dt_: datetime) -> str:
    return dt_.strftime(services.TS_FMT)


def seed_team(db):
    """Два участника; текущий — anna."""
    a = services.create_member(db, None, "anna")
    b = services.create_member(db, None, "boris")
    return a, b


# ---------------------------------------------------------------- сценарии

def scenario_1():
    """1. Первый запуск: команда и участник создаются без авторизации."""
    db = make_db()
    assert services.count_users(db) == 0
    assert services.current_member(db) is None
    assert services.get_team_name(db) == services.DEFAULT_TEAM_NAME

    a = services.create_member(db, None, "anna")
    assert a == 1
    # сессия — без пароля: текущий участник определяется автоматически
    assert services.current_member(db)["login"] == "anna"
    row = services.get_user(db, a)
    assert row["password_hash"] == "" and row["password_salt"] == ""
    assert row["role"] == "admin" and row["is_active"] and not row["is_deleted"]

    # дубликат имени (без учёта регистра) и валидация
    for bad, exc in (("Anna", services.Conflict), ("x", services.Validation),
                     ("a b?", services.Validation)):
        try:
            services.create_member(db, a, bad)
            raise AssertionError(f"ожидалась ошибка для {bad!r}")
        except exc:
            pass

    services.set_team_name(db, a, "Смена №1")
    assert services.get_team_name(db) == "Смена №1"
    for bad in ("", " " * 3, "x" * 65):
        try:
            services.set_team_name(db, a, bad)
            raise AssertionError("ожидалась ошибка названия")
        except services.Validation:
            pass


def scenario_2():
    """2. Участники команды: создание, переименование, удаление."""
    db = make_db()
    a, b = seed_team(db)
    assert [m["login"] for m in services.list_members(db)] == ["anna", "boris"]

    services.rename_member(db, a, b, "boris2")
    assert services.get_user(db, b)["login"] == "boris2"
    for bad, exc in (("ANNA", services.Conflict), ("x", services.Validation)):
        try:
            services.rename_member(db, a, b, bad)
            raise AssertionError(f"ожидалась ошибка для {bad!r}")
        except exc:
            pass

    # нельзя удалить себя (от чьего имени действие)
    try:
        services.delete_member(db, a, a)
        raise AssertionError("самоудаление должно быть запрещено")
    except services.Validation:
        pass

    # нельзя удалить текущего участника
    services.set_current_member(db, b)
    try:
        services.delete_member(db, a, b)
        raise AssertionError("удаление текущего участника должно быть запрещено")
    except services.Validation:
        pass

    services.set_current_member(db, a)
    services.delete_member(db, a, b)
    assert services.count_users(db) == 1
    assert all(m["id"] != b for m in services.list_members(db))
    assert services.get_user(db, b)["is_deleted"]
    # повторное удаление — ошибка
    try:
        services.delete_member(db, a, b)
        raise AssertionError("повторное удаление должно быть запрещено")
    except services.Validation:
        pass


def scenario_3():
    """3. Личная задача А невидима для Б; общая — видна и стартуема."""
    db = make_db()
    a, b = seed_team(db)
    priv = services.create_task(db, a, "Личная А", "d", 1, "private")
    shared = services.create_task(db, a, "Общая задача", "", 2, "shared")

    b_rows = {r["id"]: r for r in services.list_tasks(db, b)}
    assert priv not in b_rows, "Б видит личную задачу А"
    assert shared in b_rows, "Б не видит общую задачу"

    try:
        services.start_interval(db, b, priv)
        raise AssertionError("Б не должен стартовать чужую личную задачу")
    except (services.PermissionDenied, services.Validation):
        pass
    services.start_interval(db, b, shared)  # Б может стартовать общую
    services.stop_interval(db, b, shared)


def scenario_4():
    """4. А и Б одновременно работают над общей задачей: оба таймера идут."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "Общая", "", 1, "shared")

    services.start_interval(db, a, t)
    a_view = {r["id"]: r for r in services.list_tasks(db, a)}[t]
    assert a_view["workers"] == ["anna"] and a_view["status"] == "in_progress"

    services.start_interval(db, b, t)  # тот же интервал времени — оба идут
    time.sleep(1.1)
    for uid, login in ((a, "anna"), (b, "boris")):
        row = {r["id"]: r for r in services.list_tasks(db, uid)}[t]
        assert sorted(row["workers"]) == ["anna", "boris"], f"работают: {row['workers']}"
        assert row["status"] == "in_progress"
        assert row["my_seconds"] >= 1.0, f"таймер {login} не тикает"
    # повторный старт той же задачи тем же участником запрещён
    try:
        services.start_interval(db, a, t)
        raise AssertionError("ожидался конфликт повторного старта")
    except services.Conflict:
        pass


def scenario_5():
    """5. А завершает свой интервал — задача ещё «В работе»; Б завершает — «Завершена»."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "Общая", "", 1, "shared")
    services.start_interval(db, a, t)
    services.start_interval(db, b, t)

    services.stop_interval(db, a, t)  # подтверждение — на уровне UI
    row = {r["id"]: r for r in services.list_tasks(db, a)}[t]
    assert row["status"] == "in_progress" and row["workers"] == ["boris"]

    services.stop_interval(db, b, t)
    row = {r["id"]: r for r in services.list_tasks(db, b)}[t]
    assert row["status"] == "done" and row["workers"] == []


def scenario_6():
    """6. Перезапуск завершённой задачи: новый интервал, статус «В работе»."""
    db = make_db()
    a, _b = seed_team(db)
    t = services.create_task(db, a, "Задача", "", 1, "shared")
    e1 = services.start_interval(db, a, t)
    services.stop_interval(db, a, t)
    e2 = services.start_interval(db, a, t)  # перезапуск
    assert e2 != e1
    row = {r["id"]: r for r in services.list_tasks(db, a)}[t]
    assert row["status"] == "in_progress" and row["interval_count"] == 2


def scenario_7():
    """7. Задача с интервалами: удаление недоступно, архивирование доступно."""
    db = make_db()
    a, _b = seed_team(db)
    t1 = services.create_task(db, a, "С интервалами", "", 1, "private")
    services.start_interval(db, a, t1)
    services.stop_interval(db, a, t1)
    try:
        services.delete_task(db, a, t1)
        raise AssertionError("удаление должно быть запрещено")
    except services.Conflict:
        pass
    services.archive_task(db, a, t1)
    assert all(r["id"] != t1 for r in services.list_tasks(db, a))
    assert any(r["id"] == t1 for r in services.list_tasks(db, a, show_archived=True))

    # без интервалов — удаление разрешено
    t2 = services.create_task(db, a, "Без интервалов", "", 1, "private")
    services.delete_task(db, a, t2)
    assert services.get_task(db, t2) is None


def scenario_8():
    """8. Переключение участника не трогает интервалы; закрытие приложения
    закрывает все открытые интервалы текущим временем."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "Задача", "", 1, "private")
    services.start_interval(db, a, t)
    services.start_interval(db, b, services.create_task(db, b, "Ещё", "", 1, "private"))

    # переключение на другого участника: интервалы остаются открытыми
    services.set_current_member(db, b)
    assert services.current_member(db)["id"] == b
    assert len(services.open_intervals_for_user(db, a)) == 1
    assert len(services.open_intervals_all(db)) == 2

    # закрытие приложения (без авторизации — все участники)
    before = datetime.now()
    n = services.stop_all_open(db, "app_close")
    after = datetime.now()
    assert n == 2
    rows = services.list_intervals(db, t)
    assert rows[0]["finished_at"] and rows[0]["closed_by"] == "app_close"
    assert before.strftime(services.TS_FMT) <= rows[0]["finished_at"] <= after.strftime(services.TS_FMT)
    assert services.open_intervals_all(db) == []


def scenario_9():
    """9. Имитация выключения ПК: при следующем запуске интервалы закрыты
    временем последнего heartbeat."""
    db = make_db()
    a, _b = seed_team(db)
    t = services.create_task(db, a, "Задача", "", 1, "private")

    # «сессия»: интервал открыт в 10:00, heartbeat в 10:07, процесс убит
    started = ts(datetime.now().replace(microsecond=0) - timedelta(minutes=10))
    heartbeat = ts(datetime.now().replace(microsecond=0) - timedelta(minutes=3))
    db.execute("INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
               "VALUES(?,?,?,NULL,NULL)", (t, a, started))
    services.set_setting(db, services.HEARTBEAT_KEY, heartbeat)

    closed = services.recover_open_intervals(db)
    assert closed == 1
    row = services.list_intervals(db, t)[0]
    assert row["finished_at"] == heartbeat
    assert row["closed_by"] == "shutdown_recovery"

    # интервал, начатый ПОСЛЕ последнего heartbeat — закрывается моментом старта
    late_start = ts(datetime.now().replace(microsecond=0) + timedelta(minutes=1))
    db.execute("INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
               "VALUES(?,?,?,NULL,NULL)", (t, a, late_start))
    services.recover_open_intervals(db)
    row = services.list_intervals(db, t)[0]
    assert row["finished_at"] == late_start and row["closed_by"] == "shutdown_recovery"


def scenario_10():
    """10. Отчёт: фильтр по периоду и участнику, итог = сумме интервалов."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "Общая", "", 1, "shared")

    now = datetime.now()

    def insert(uid, start: datetime, minutes: int):
        db.execute("INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
                   "VALUES(?,?,?,?, 'user')", (t, uid, ts(start),
                                               ts(start + timedelta(minutes=minutes))))

    insert(a, now - timedelta(days=2), 30)   # а, позавчера: 30 мин
    insert(a, now - timedelta(days=1), 15)   # а, вчера: 15 мин
    insert(b, now - timedelta(days=1), 45)   # б, вчера: 45 мин
    insert(a, now - timedelta(days=10), 60)  # вне периода

    d_from, d_to = (date.today() - timedelta(days=3)), date.today()

    rows = services.report_by_users(db, d_from, d_to)
    total = sum(r["seconds"] for r in rows)
    assert total == (30 + 15 + 45) * 60, f"итого {total}"

    rows_a = services.report_by_users(db, d_from, d_to, user_id=a)
    assert len(rows_a) == 1 and rows_a[0]["seconds"] == 45 * 60

    rows_task = services.report_by_users(db, d_from, d_to, task_id=t)
    assert sum(r["seconds"] for r in rows_task) == 90 * 60

    # только закрытые интервалы: открытый в отчёт не попадает
    services.start_interval(db, a, t)
    rows2 = services.report_by_users(db, d_from, d_to)
    assert sum(r["seconds"] for r in rows2) == 90 * 60


def scenario_11():
    """11. «Быстрый старт» из шаблона: задача создана + интервал сразу открыт."""
    db = make_db()
    a, _b = seed_team(db)
    tpl = services.create_template(db, a, "Утренняя проверка",
                                   "Проверить сервер", "Шаги…", 2, "shared")
    task_id, entry_id = services.quick_start(db, a, tpl)
    task = services.get_task(db, task_id)
    assert task["title"] == "Проверить сервер" and task["priority"] == 2
    assert task["visibility"] == "shared" and task["owner_id"] == a
    row = {r["id"]: r for r in services.list_tasks(db, a)}[task_id]
    assert row["status"] == "in_progress" and row["i_work"]
    plain = services.create_task(db, a, task["title"], "Шаги…", 2, "shared")
    row2 = {r["id"]: r for r in services.list_tasks(db, a)}[plain]
    assert row2["status"] == "new"


def scenario_12():
    """12. Профиль команды: название, статистика участников за период."""
    db = make_db()
    a, b = seed_team(db)
    services.set_team_name(db, a, "Ночная смена")
    assert services.get_team_name(db) == "Ночная смена"

    t = services.create_task(db, a, "Общая", "", 1, "shared")
    now = datetime.now()

    def insert(uid, minutes: int, days_ago: int):
        start = now - timedelta(days=days_ago)
        db.execute("INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
                   "VALUES(?,?,?,?, 'user')", (t, uid, ts(start),
                                               ts(start + timedelta(minutes=minutes))))

    insert(a, 60, 1)
    insert(b, 30, 1)
    insert(a, 120, 40)  # вне периода

    d_from, d_to = date.today() - timedelta(days=3), date.today()
    stats = services.member_stats(db, d_from, d_to)
    assert stats[a] == 60 * 60 and stats[b] == 30 * 60, stats
    assert sum(stats.values()) == 90 * 60

    # команда/сессия: current_member откатывается на первого активного
    # при удалении сохранённого участника (через прямую правку настройки)
    services.set_setting(db, services.CURRENT_MEMBER_KEY, str(b))
    db.execute("UPDATE users SET is_deleted=1 WHERE id=?", (b,))
    assert services.current_member(db)["id"] == a
    assert services.current_member_id(db) == a


# ---------------------------------------------------------------- доп. проверки

def extra_hidden_tasks_of_deleted_member():
    """Личные задачи удалённого участника скрыты из списков, видны в отчётах."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "Личная А", "", 1, "private")
    services.start_interval(db, a, t)
    services.stop_interval(db, a, t)

    # удаляем anna (текущий — она, поэтому сначала переключаемся на b)
    services.set_current_member(db, b)
    services.delete_member(db, b, a)

    assert all(r["id"] != t for r in services.list_tasks(db, b)), \
        "скрытая задача не должна быть в списке даже у другого участника"
    rows = services.report_by_users(db, date.today() - timedelta(days=1), date.today())
    assert any(r["title"] == "Личная А" and r["user_deleted"] for r in rows), \
        "в отчёте задачи удалённого участника должны быть"


def extra_audit_log():
    """Аудит ключевых действий пишется."""
    db = make_db()
    a, b = seed_team(db)
    t = services.create_task(db, a, "З", "", 1, "private")
    services.start_interval(db, a, t)
    services.stop_interval(db, a, t)
    services.update_task(db, b, t, "З2", "", 1, "private", a)  # правка чужого -> admin_edit
    services.set_team_name(db, a, "Команда-2")
    actions = {r["action"] for r in services.list_audit(db)}
    for expected in ("create_member", "create_task", "start", "stop",
                     "update_task", "admin_edit", "rename_team"):
        assert expected in actions, f"нет действия {expected}: {actions}"


def extra_admin_interval_edit():
    """Редактирование интервалов — только для роли admin (в MVP все участники
    — admin; legacy-пользователь со старой ролью 'user' — нет)."""
    db = make_db()
    a, _b = seed_team(db)
    t = services.create_task(db, a, "З", "", 1, "private")
    services.start_interval(db, a, t)
    services.stop_interval(db, a, t)
    entry = services.list_intervals(db, t)[0]

    # legacy-строка из старой версии: роль user, пароль из прежнего входа
    cur = db.execute(
        "INSERT INTO users(login,password_hash,password_salt,role,is_active,is_deleted,created_at,created_by) "
        "VALUES('legacy','x','y','user',1,0,?,?)", (services.now_iso(), a))
    legacy_id = cur.lastrowid

    new_start = ts(datetime.now() - timedelta(hours=1))
    try:
        services.update_interval(db, legacy_id, entry["id"], new_start, None)
        raise AssertionError("не-админ не должен редактировать интервалы")
    except services.PermissionDenied:
        pass

    services.update_interval(db, a, entry["id"], new_start,
                             ts(datetime.now() - timedelta(minutes=30)))
    row = services.list_intervals(db, t)[0]
    assert row["started_at"] == new_start
    assert any(r["action"] == "edit_time_entry" for r in services.list_audit(db))


def extra_my_entries():
    """Просмотр своих записей времени: только свои, период, фильтр по задаче,
    открытый интервал с текущей длительностью."""
    db = make_db()
    a, b = seed_team(db)
    t1 = services.create_task(db, a, "Задача А", "", 1, "shared")
    t2 = services.create_task(db, a, "Личная А", "", 1, "private")

    now = datetime.now()

    def insert(uid, tid, start: datetime, minutes: int):
        db.execute("INSERT INTO time_entries(task_id,user_id,started_at,finished_at,closed_by) "
                   "VALUES(?,?,?,?, 'user')",
                   (tid, uid, ts(start), ts(start + timedelta(minutes=minutes))))

    insert(a, t1, now - timedelta(days=1, minutes=50), 50)   # а, вчера
    insert(a, t2, now - timedelta(hours=2), 30)              # а, сегодня
    insert(b, t1, now - timedelta(days=1), 45)               # б — не должен попасть
    insert(a, t1, now - timedelta(days=40), 60)              # вне периода

    d_from, d_to = date.today() - timedelta(days=3), date.today()

    rows = services.list_my_entries(db, a, d_from, d_to)
    assert len(rows) == 2, f"ожидалось 2 записи, получено {len(rows)}"
    assert {r["title"] for r in rows} == {"Задача А", "Личная А"}
    assert sum(r["seconds"] for r in rows) == (50 + 30) * 60
    assert rows[0]["started_at"] >= rows[1]["started_at"]

    rows_t1 = services.list_my_entries(db, a, d_from, d_to, task_id=t1)
    assert len(rows_t1) == 1 and rows_t1[0]["title"] == "Задача А"

    rows_b = services.list_my_entries(db, b, d_from, d_to)
    assert len(rows_b) == 1 and rows_b[0]["title"] == "Задача А"

    # открытый интервал попадает в список с текущей длительностью
    services.start_interval(db, a, t1)
    rows_open = services.list_my_entries(db, a, d_from, d_to)
    opens = [r for r in rows_open if r["finished_at"] is None]
    assert len(opens) == 1 and opens[0]["seconds"] >= 0
    assert len(rows_open) == 3

    # задачи для фильтра: свои + общие, скрытые исключены
    ids = {t["id"] for t in services.list_tasks_for_user_combobox(db, a)}
    assert ids == {t1, t2}
    ids_b = {t["id"] for t in services.list_tasks_for_user_combobox(db, b)}
    assert ids_b == {t1}, "Б не должен видеть личную задачу А в фильтре"


def extra_theme():
    """Темы: сохранение выбора, полнота QSS, fallback для мусорного значения."""
    db = make_db()
    from timetracker.ui import theme

    assert theme.current_theme(db) == theme.DEFAULT_THEME == "light"
    light, dark = theme.qss_for("light"), theme.qss_for("dark")
    assert light and dark and light != dark
    for token in ("QPushButton", "QTabBar::tab", "#col_in_progress", "#card",
                  "#danger", "#secondary", "QScrollBar"):
        assert token in light, f"нет {token} в светлой теме"
        assert token in dark, f"нет {token} в тёмной теме"
    assert theme.qss_for("weird") == light  # неизвестная тема -> светлая

    theme.save_theme(db, "dark")
    assert theme.current_theme(db) == "dark"
    services.set_setting(db, theme.THEME_KEY, "banana")
    assert theme.current_theme(db) == "light"  # мусор -> дефолт
    theme.save_theme(db, "light")


def extra_single_instance():
    """Named mutex: второй acquire возвращает False."""
    from timetracker.single_instance import SingleInstance
    first = SingleInstance()
    assert first.acquire(), "первый экземпляр должен получить мьютекс"
    second = SingleInstance()
    assert not second.acquire(), "второй экземпляр должен быть отклонён"
    first.release()
    third = SingleInstance()
    assert third.acquire(), "после release мьютекс снова доступен"
    third.release()


def extra_fmt():
    assert services.fmt_dur(0) == "00:00"
    assert services.fmt_dur(65) == "00:01"
    assert services.fmt_dur(3661) == "01:01"
    assert services.fmt_dur(3600 * 125 + 60) == "125:01"
    assert services.fmt_dt("2026-11-07 09:05:00") == "07.11.2026 09:05"
    assert services.fmt_dt(None) == "—"


# ---------------------------------------------------------------- UI-смоук (offscreen)

def ui_smoke():
    """Смоук UI: первичный диалог, доска, переносы, карточка, участники,
    переключатель, закрытие с интервалами."""
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    app = QApplication.instance() or QApplication([])

    tmp = tempfile.mkdtemp(prefix="tt_ui_")
    db = Database(Path(tmp) / "timetracker.db")

    from timetracker.ui.first_run import FirstRunDialog
    from timetracker.ui.main_window import MainWindow
    from timetracker.ui.dialogs import TaskCardDialog
    from timetracker import services as svc

    orig_question = QMessageBox.question
    orig_information = QMessageBox.information
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    QMessageBox.information = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Ok)
    try:
        # --- первичный диалог: команда + участник без пароля ---
        dlg = FirstRunDialog(db)
        dlg.ed_team.setText("Демо-команда")
        dlg.ed_member.setText("anna")
        dlg.accept()
        assert dlg.result() == QDialog.DialogCode.Accepted
        assert svc.count_users(db) == 1
        assert svc.get_team_name(db) == "Демо-команда"
        member = svc.current_member(db)
        assert member["login"] == "anna"

        # --- главное окно: 5 вкладок, доска первая, тема переключается ---
        win = MainWindow(db, member)
        assert win.tabs.count() == 5
        assert win.tabs.tabText(0) == "Доска"
        assert win.lbl_team.text() == "Команда: Демо-команда"
        assert win.cmb_theme.count() == 2

        from timetracker.ui import theme
        win.cmb_theme.setCurrentIndex(1)          # тёмная тема
        assert theme.current_theme(db) == "dark"
        assert app.styleSheet() != "", "QSS не применился"
        win.cmb_theme.setCurrentIndex(0)          # обратно к светлой
        assert theme.current_theme(db) == "light"

        # --- задача на доске: Новая -> В работе -> Завершена ---
        t = svc.create_task(db, member["id"], "Канбан-задача", "", 1, "shared")
        win._data_changed()
        assert len(win.board_tab._columns["new"].cards) == 1

        win.board_tab._on_drop("in_progress", t)  # перенос = старт интервала
        assert win.board_tab._rows[t]["status"] == "in_progress"
        assert len(win.board_tab._columns["in_progress"].cards) == 1
        assert len(win._panel_timer_labels) == 1, "нет чипа в «Мои активные»"
        assert win.records_tab.table.rowCount() == 1, "нет записи в «Мои записи»"

        win.board_tab._on_drop("done", t)          # перенос = останов (с вопросом)
        assert win.board_tab._rows[t]["status"] == "done"
        assert len(win.board_tab._columns["done"].cards) == 1

        # перенос в «Новая» при наличии интервалов запрещён — карточка остаётся
        win.board_tab._on_drop("new", t)
        assert win.board_tab._rows[t]["status"] == "done"

        # --- карточка задачи ---
        card = TaskCardDialog(win, db, member, t, notify=win._data_changed)
        assert card.lbl_title.text().startswith("Канбан-задача")
        assert card.lbl_status.text() == "Завершена"
        assert card.btn_toggle.text() == "Старт"
        assert not card.btn_delete.isEnabled(), "с интервалами нельзя удалять"
        card.tick()
        card.accept()

        # --- участник + переключатель в шапке ---
        svc.create_member(db, member["id"], "boris")
        win._data_changed()
        assert win.cmb_member.count() == 2
        assert win.team_tab.table.rowCount() == 2

        win.cmb_member.setCurrentIndex(1)   # переключение без пароля
        assert win.user["login"] == "boris"
        assert win.tabs.count() == 5, "вкладки должны быть пересозданы"
        assert win.records_tab.user["login"] == "boris"
        assert win.board_tab.user["login"] == "boris"

        # --- закрытие окна с открытыми интервалами закрывает все (app_close) ---
        svc.start_interval(db, member["id"], t)   # у anna снова открыт интервал
        assert len(svc.open_intervals_all(db)) == 1
        win.close()
        entries = svc.list_intervals(db, t)
        assert entries and entries[0]["finished_at"]
        assert entries[0]["closed_by"] == "app_close"
        assert svc.open_intervals_all(db) == []
        win.deleteLater()
    finally:
        QMessageBox.question = orig_question
        QMessageBox.information = orig_information


def main():
    print("== TimeTracker: сценарии (MVP без авторизации) ==")
    check("Сценарий 1  — команда и участник без входа", scenario_1)
    check("Сценарий 2  — участники: создание/переименование/удаление", scenario_2)
    check("Сценарий 3  — личные и общие задачи", scenario_3)
    check("Сценарий 4  — одновременная работа А и Б", scenario_4)
    check("Сценарий 5  — последовательное завершение", scenario_5)
    check("Сценарий 6  — перезапуск завершённой задачи", scenario_6)
    check("Сценарий 7  — удаление/архивирование", scenario_7)
    check("Сценарий 8  — переключение и закрытие приложения", scenario_8)
    check("Сценарий 9  — heartbeat-восстановление", scenario_9)
    check("Сценарий 10 — отчёт за период", scenario_10)
    check("Сценарий 11 — быстрый старт из шаблона", scenario_11)
    check("Сценарий 12 — профиль команды и статистика", scenario_12)
    print("== Дополнительно ==")
    check("Доп: скрытые задачи удалённого участника", extra_hidden_tasks_of_deleted_member)
    check("Доп: аудит ключевых действий", extra_audit_log)
    check("Доп: редактирование интервалов (roles)", extra_admin_interval_edit)
    check("Доп: просмотр своих записей времени", extra_my_entries)
    check("Доп: single-instance мьютекс", extra_single_instance)
    check("Доп: темы (светлая/тёмная)", extra_theme)
    check("Доп: форматирование времени", extra_fmt)
    print("== UI (offscreen) ==")
    check("UI: диалог/доска/переносы/карточка/участники/закрытие", ui_smoke)

    print(f"\nПройдено: {len(PASS)}  Провалено: {len(FAIL)}")
    if FAIL:
        print("Провалены:", ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
