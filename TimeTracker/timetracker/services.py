# -*- coding: utf-8 -*-
"""Бизнес-логика TimeTracker: пользователи, задачи, шаблоны, интервалы,
аудит, отчёты, heartbeat-восстановление. UI работает только через эти функции."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

# ---------- константы ----------

PRIORITY_LABELS = {0: "Низкий", 1: "Обычный", 2: "Высокий"}
VISIBILITY_LABELS = {"private": "Личная", "shared": "Общая"}
STATUS_LABELS = {"new": "Новая", "in_progress": "В работе", "done": "Завершена"}
CLOSED_BY_LABELS = {
    "user": "вручную",
    "logout": "выход из учётной записи",
    "app_close": "закрытие приложения",
    "shutdown_recovery": "восстановление после выключения",
    "admin": "администратор",
}

LOGIN_MIN, LOGIN_MAX = 2, 32
TS_FMT = "%Y-%m-%d %H:%M:%S"

HEARTBEAT_KEY = "last_activity_at"
TEAM_NAME_KEY = "team_name"
CURRENT_MEMBER_KEY = "current_member_id"
DEFAULT_TEAM_NAME = "Моя команда"


# ---------- исключения ----------

class ServiceError(Exception):
    """Базовая ошибка бизнес-логики (показывается пользователю)."""


class Validation(ServiceError):
    """Некорректные данные."""


class PermissionDenied(ServiceError):
    """Недостаточно прав."""


class Conflict(ServiceError):
    """Действие невозможно в текущем состоянии."""


# ---------- время и форматирование ----------

def now_iso() -> str:
    return datetime.now().strftime(TS_FMT)


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, TS_FMT)


def fmt_dt(iso: Optional[str]) -> str:
    """Отображение даты-времени: dd.MM.yyyy HH:mm."""
    if not iso:
        return "—"
    try:
        return parse_ts(iso).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def fmt_dur(seconds) -> str:
    """Длительность в формате ЧЧ:ММ (часы могут превышать 24)."""
    total = int(seconds)
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


# ---------- аудит ----------

def audit(db, actor_id: Optional[int], action: str, entity_type: str,
          entity_id: Optional[int], details: dict | None = None):
    """Запись ключевого действия в audit_log (JSON-детали)."""
    db.execute(
        "INSERT INTO audit_log(user_id, action, entity_type, entity_id, details_json, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (actor_id, action, entity_type, entity_id,
         json.dumps(details or {}, ensure_ascii=False), now_iso()),
    )


def list_audit(db, limit: int = 500):
    return db.query_all(
        "SELECT a.*, u.login FROM audit_log a LEFT JOIN users u ON u.id=a.user_id "
        "ORDER BY a.id DESC LIMIT ?", (limit,))


# ---------- настройки / heartbeat ----------

def get_setting(db, key: str) -> Optional[str]:
    row = db.query_one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else None


def set_setting(db, key: str, value: str):
    db.execute("INSERT INTO settings(key, value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def write_heartbeat(db):
    """Каждые 30 секунд пишем время последней активности (см. п.5.4 ТЗ)."""
    set_setting(db, HEARTBEAT_KEY, now_iso())


# ---------- участники команды (MVP без авторизации) ----------
# Пароли и вход не используются: поля схемы заполняются пустыми значениями,
# все участники равноправны (role='admin' — внутренняя роль для сервисных
# проверок: без входа ограничения прав бессмысленны).

def count_users(db) -> int:
    return db.query_one("SELECT COUNT(*) AS c FROM users WHERE is_deleted=0")["c"]


def get_user(db, user_id):
    return db.query_one("SELECT * FROM users WHERE id=?", (user_id,))


def list_users(db):
    return db.query_all("SELECT * FROM users ORDER BY login")


def list_members(db):
    """Активные участники команды (для шапки, фильтров и профиля)."""
    return db.query_all(
        "SELECT * FROM users WHERE is_deleted=0 ORDER BY login")


def active_logins(db):
    return db.query_all(
        "SELECT login FROM users WHERE is_active=1 AND is_deleted=0 ORDER BY login")


def validate_member_name(name: str) -> str:
    s = (name or "").strip()
    if not (LOGIN_MIN <= len(s) <= LOGIN_MAX):
        raise Validation(f"Имя участника: от {LOGIN_MIN} до {LOGIN_MAX} символов")
    for ch in s:
        if not (ch.isalnum() or ch in "._- "):
            raise Validation("Имя может содержать только буквы, цифры и символы . _ -")
    return s


def _require_admin(db, actor_id):
    actor = get_user(db, actor_id)
    if actor is None or actor["role"] != "admin":
        raise PermissionDenied("Требуются права администратора")


def create_member(db, actor_id, name: str) -> int:
    """Добавить участника команды (без пароля)."""
    name = validate_member_name(name)
    if db.query_one("SELECT id FROM users WHERE lower(login)=lower(?)", (name,)):
        raise Conflict(f"Участник «{name}» уже есть")
    cur = db.execute(
        "INSERT INTO users(login, password_hash, password_salt, role, is_active, is_deleted, created_at, created_by) "
        "VALUES(?, '', '', 'admin', 1, 0, ?, ?)",
        (name, now_iso(), actor_id),
    )
    member_id = cur.lastrowid
    audit(db, actor_id, "create_member", "user", member_id, {"name": name})
    if not get_setting(db, CURRENT_MEMBER_KEY):
        set_setting(db, CURRENT_MEMBER_KEY, str(member_id))
    return member_id


def rename_member(db, actor_id, member_id: int, name: str):
    name = validate_member_name(name)
    target = get_user(db, member_id)
    if target is None or target["is_deleted"]:
        raise Validation("Участник не найден")
    dup = db.query_one("SELECT id FROM users WHERE lower(login)=lower(?) AND id!=?",
                       (name, member_id))
    if dup:
        raise Conflict(f"Имя «{name}» уже занято")
    db.execute("UPDATE users SET login=? WHERE id=?", (name, member_id))
    audit(db, actor_id, "rename_member", "user", member_id,
          {"old": target["login"], "new": name})


def delete_member(db, actor_id, member_id: int):
    """Мягкое удаление участника: данные и интервалы сохраняются."""
    _require_admin(db, actor_id)
    if member_id == actor_id:
        raise Validation("Нельзя удалить участника, от имени которого выполняется действие")
    if str(current_member_id(db) or "") == str(member_id):
        raise Validation("Нельзя удалить текущего участника — сначала переключитесь")
    target = get_user(db, member_id)
    if target is None:
        raise Validation("Участник не найден")
    if target["is_deleted"]:
        raise Validation("Участник уже удалён")
    db.execute("UPDATE users SET is_deleted=1 WHERE id=?", (member_id,))
    db.execute("UPDATE tasks SET is_hidden=1 WHERE owner_id=? AND visibility='private'",
               (member_id,))
    audit(db, actor_id, "delete_member", "user", member_id, {"name": target["login"]})


# ---------- команда и текущий участник ----------

def get_team_name(db) -> str:
    return get_setting(db, TEAM_NAME_KEY) or DEFAULT_TEAM_NAME


def set_team_name(db, actor_id, name: str):
    name = (name or "").strip()
    if not name:
        raise Validation("Название команды не может быть пустым")
    if len(name) > 64:
        raise Validation("Название команды: до 64 символов")
    set_setting(db, TEAM_NAME_KEY, name)
    audit(db, actor_id, "rename_team", "team", None, {"name": name})


def current_member_id(db):
    v = get_setting(db, CURRENT_MEMBER_KEY)
    return int(v) if v else None


def set_current_member(db, member_id: int):
    set_setting(db, CURRENT_MEMBER_KEY, str(member_id))


def current_member(db):
    """Текущий участник (переключатель в шапке); иначе первый активный.

    Если сохранённый участник удалён/не найден — возвращается первый активный,
    и настройка пересохраняется на него.
    """
    mid = current_member_id(db)
    if mid is not None:
        row = db.query_one(
            "SELECT * FROM users WHERE id=? AND is_active=1 AND is_deleted=0", (mid,))
        if row is not None:
            return row
    row = db.query_one(
        "SELECT * FROM users WHERE is_active=1 AND is_deleted=0 ORDER BY id LIMIT 1")
    if row is not None:
        set_current_member(db, row["id"])
    return row


# ---------- задачи ----------

def get_task(db, task_id):
    return db.query_one("SELECT * FROM tasks WHERE id=?", (task_id,))


def _is_admin(user_row) -> bool:
    return user_row is not None and user_row["role"] == "admin"


def can_edit_task(user_row, task_row) -> bool:
    return _is_admin(user_row) or task_row["owner_id"] == user_row["id"]


def can_work_on(user_row, task_row) -> bool:
    """Старт/завершение — только по своим и общим задачам (роль не даёт
    обхода видимости: в MVP участники равноправны, личное остаётся личным)."""
    return task_row["visibility"] == "shared" or task_row["owner_id"] == user_row["id"]


def _validate_task_fields(db, title, priority, visibility, owner_id):
    title = (title or "").strip()
    if not title:
        raise Validation("Укажите название задачи")
    if priority not in PRIORITY_LABELS:
        raise Validation("Недопустимый приоритет")
    if visibility not in ("private", "shared"):
        raise Validation("Недопустимая видимость")
    owner = get_user(db, owner_id)
    if owner is None or owner["is_deleted"]:
        raise Validation("Владелец не найден или удалён")
    return title


def create_task(db, actor_id, title, description="", priority=1,
                visibility="private", owner_id=None) -> int:
    actor = get_user(db, actor_id)
    if actor is None:
        raise Validation("Пользователь не найден")
    owner = owner_id if owner_id is not None else actor_id
    title = _validate_task_fields(db, title, priority, visibility, owner)
    cur = db.execute(
        "INSERT INTO tasks(title, description, priority, visibility, owner_id, created_by, "
        "created_at, is_archived, archived_at, is_hidden) VALUES(?,?,?,?,?,?,?,0,NULL,0)",
        (title, description or "", priority, visibility, owner, actor_id, now_iso()),
    )
    task_id = cur.lastrowid
    audit(db, actor_id, "create_task", "task", task_id,
          {"title": title, "visibility": visibility, "owner_id": owner})
    return task_id


def update_task(db, actor_id, task_id, title, description, priority,
                visibility, owner_id):
    actor = get_user(db, actor_id)
    task = get_task(db, task_id)
    if task is None:
        raise Validation("Задача не найдена")
    if not can_edit_task(actor, task):
        raise PermissionDenied("Редактировать задачу может владелец или администратор")
    title = _validate_task_fields(db, title, priority, visibility, owner_id)
    db.execute(
        "UPDATE tasks SET title=?, description=?, priority=?, visibility=?, owner_id=? WHERE id=?",
        (title, description or "", priority, visibility, owner_id, task_id),
    )
    details = {"title": title, "visibility": visibility, "owner_id": owner_id,
               "priority": priority}
    audit(db, actor_id, "update_task", "task", task_id, details)
    if task["owner_id"] != actor_id:
        audit(db, actor_id, "admin_edit", "task", task_id, details)


def archive_task(db, actor_id, task_id):
    actor = get_user(db, actor_id)
    task = get_task(db, task_id)
    if task is None:
        raise Validation("Задача не найдена")
    if not can_edit_task(actor, task):
        raise PermissionDenied("Архивировать задачу может владелец или администратор")
    db.execute("UPDATE tasks SET is_archived=1, archived_at=? WHERE id=?", (now_iso(), task_id))
    audit(db, actor_id, "archive_task", "task", task_id, {"title": task["title"]})


def delete_task(db, actor_id, task_id):
    """Удаление — только если у задачи нет ни одного интервала (п.5.2 ТЗ)."""
    actor = get_user(db, actor_id)
    task = get_task(db, task_id)
    if task is None:
        raise Validation("Задача не найдена")
    if not can_edit_task(actor, task):
        raise PermissionDenied("Удалять задачу может владелец или администратор")
    n = db.query_one("SELECT COUNT(*) AS c FROM time_entries WHERE task_id=?", (task_id,))["c"]
    if n:
        raise Conflict("У задачи есть интервалы — удаление недоступно. Используйте «Архивировать».")
    db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    audit(db, actor_id, "delete_task", "task", task_id, {"title": task["title"]})


def _closed_seconds_expr(alias="e"):
    return (f"(CAST(strftime('%s',{alias}.finished_at) AS INTEGER) - "
            f"CAST(strftime('%s',{alias}.started_at) AS INTEGER))")


def list_tasks(db, actor_id, status="all", visibility="all", show_archived=False) -> list[dict]:
    """Список задач главного экрана с агрегатами и вычисляемым статусом.

    visibility: all | mine (я владелец) | shared (видимость «Общая»).
    status: all | new | in_progress | done.
    Скрытые (is_hidden) задачи исключены у всех; архивные — только при show_archived.
    Видимость строго по правилам: общие + свои (роль участника обхода не даёт).
    """
    actor = get_user(db, actor_id)
    conds, params = ["t.is_hidden=0", "(t.visibility='shared' OR t.owner_id=?)"], [actor_id]
    conds.append("t.is_archived=1" if show_archived else "t.is_archived=0")

    rows = db.query_all(
        f"""SELECT t.*, u.login AS owner_login, u.is_deleted AS owner_deleted,
            (SELECT COUNT(*) FROM time_entries e WHERE e.task_id=t.id) AS interval_count,
            (SELECT COUNT(*) FROM time_entries e WHERE e.task_id=t.id AND e.finished_at IS NULL) AS open_count,
            (SELECT COALESCE(SUM({_closed_seconds_expr()}),0) FROM time_entries e
                WHERE e.task_id=t.id AND e.finished_at IS NOT NULL) AS closed_seconds,
            (SELECT COALESCE(SUM({_closed_seconds_expr()}),0) FROM time_entries e
                WHERE e.task_id=t.id AND e.finished_at IS NOT NULL AND e.user_id=?) AS my_closed_seconds
            FROM tasks t JOIN users u ON u.id=t.owner_id
            WHERE {" AND ".join(conds)}""",
        [*params, actor_id],
    )
    opens = db.query_all(
        "SELECT e.id, e.task_id, e.user_id, e.started_at, u.login "
        "FROM time_entries e JOIN users u ON u.id=e.user_id WHERE e.finished_at IS NULL")
    open_map: dict[int, list] = {}
    for r in opens:
        open_map.setdefault(r["task_id"], []).append(r)

    now = datetime.now()
    result = []
    for r in rows:
        d = dict(r)
        task_opens = open_map.get(d["id"], [])
        live_total = live_mine = 0
        workers, my_started = [], None
        for o in task_opens:
            elapsed = max(0.0, (now - parse_ts(o["started_at"])).total_seconds())
            live_total += elapsed
            if o["user_id"] == actor_id:
                live_mine += elapsed
                my_started = o["started_at"]
            if o["login"] not in workers:
                workers.append(o["login"])
        d["workers"] = workers
        d["i_work"] = my_started is not None
        d["my_open_started"] = my_started
        d["total_seconds"] = d["closed_seconds"] + live_total
        d["my_seconds"] = d["my_closed_seconds"] + live_mine
        d["status"] = ("new" if d["interval_count"] == 0
                       else "in_progress" if d["open_count"] > 0 else "done")
        if status != "all" and d["status"] != status:
            continue
        if visibility == "mine" and d["owner_id"] != actor_id:
            continue
        if visibility == "shared" and d["visibility"] != "shared":
            continue
        result.append(d)

    order = {"in_progress": 0, "new": 1, "done": 2}
    result.sort(key=lambda d: (order[d["status"]], -d["priority"], d["title"].lower()))
    return result


def task_time_summary(db, actor_id, task_ids) -> dict[int, dict]:
    """Лёгкая сводка для ежесекундного обновления таймеров (без полной перезагрузки списка)."""
    ids = list(task_ids)
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    closed = {r["task_id"]: (r["total"], r["mine"]) for r in db.query_all(
        f"""SELECT e.task_id,
               COALESCE(SUM({_closed_seconds_expr()}),0) AS total,
               COALESCE(SUM(CASE WHEN e.user_id=? THEN {_closed_seconds_expr()} ELSE 0 END),0) AS mine
            FROM time_entries e
            WHERE e.task_id IN ({ph}) AND e.finished_at IS NOT NULL
            GROUP BY e.task_id""", [actor_id, *ids])}
    opens = db.query_all(
        f"""SELECT e.id, e.task_id, e.user_id, e.started_at, u.login
            FROM time_entries e JOIN users u ON u.id=e.user_id
            WHERE e.finished_at IS NULL AND e.task_id IN ({ph})""", ids)
    now = datetime.now()
    summary: dict[int, dict] = {}
    for tid in ids:
        summary[tid] = {"total_seconds": closed.get(tid, (0, 0))[0],
                        "my_seconds": closed.get(tid, (0, 0))[1],
                        "workers": [], "i_work": False}
    for o in opens:
        s = summary[o["task_id"]]
        elapsed = max(0.0, (now - parse_ts(o["started_at"])).total_seconds())
        s["total_seconds"] += elapsed
        if o["user_id"] == actor_id:
            s["my_seconds"] += elapsed
            s["i_work"] = True
        if o["login"] not in s["workers"]:
            s["workers"].append(o["login"])
    return summary


# ---------- интервалы (time_entries) ----------

def start_interval(db, actor_id, task_id) -> int:
    actor = get_user(db, actor_id)
    task = get_task(db, task_id)
    if task is None:
        raise Validation("Задача не найдена")
    if not can_work_on(actor, task):
        raise PermissionDenied("Работать можно по своим и общим задачам")
    if task["is_archived"]:
        raise Conflict("Архивную задачу нельзя запустить")
    if db.query_one("SELECT id FROM time_entries WHERE task_id=? AND user_id=? AND finished_at IS NULL",
                    (task_id, actor_id)):
        raise Conflict("У вас уже есть открытый интервал по этой задаче")
    started = now_iso()
    cur = db.execute(
        "INSERT INTO time_entries(task_id, user_id, started_at, finished_at, closed_by) "
        "VALUES(?,?,?,NULL,NULL)", (task_id, actor_id, started))
    entry_id = cur.lastrowid
    audit(db, actor_id, "start", "time_entry", entry_id,
          {"task_id": task_id, "task_title": task["title"], "started_at": started})
    return entry_id


def my_open_entry(db, user_id, task_id):
    return db.query_one(
        "SELECT * FROM time_entries WHERE user_id=? AND task_id=? AND finished_at IS NULL",
        (user_id, task_id))


def elapsed_since(started_iso: str) -> float:
    """Сколько секунд прошло с указанного момента (для живых таймеров)."""
    return max(0.0, (datetime.now() - parse_ts(started_iso)).total_seconds())


def open_interval_seconds(entry_row) -> float:
    return elapsed_since(entry_row["started_at"])


def stop_interval(db, actor_id, task_id, closed_by="user"):
    """Завершение — закрывает только интервал текущего пользователя (п.5.2 ТЗ)."""
    entry = my_open_entry(db, actor_id, task_id)
    if entry is None:
        raise Conflict("Нет открытого интервала по этой задаче")
    finished = now_iso()
    db.execute("UPDATE time_entries SET finished_at=?, closed_by=? WHERE id=?",
               (finished, closed_by, entry["id"]))
    audit(db, actor_id, "stop", "time_entry", entry["id"],
          {"task_id": task_id, "closed_by": closed_by, "finished_at": finished})
    return entry["id"]


def stop_all_for_user(db, user_id, closed_by) -> int:
    """Закрыть все открытые интервалы пользователя текущим временем
    (выход из учётки / закрытие приложения). Возвращает число закрытых."""
    rows = db.query_all(
        "SELECT id, task_id FROM time_entries WHERE user_id=? AND finished_at IS NULL",
        (user_id,))
    finished = now_iso()
    for r in rows:
        db.execute("UPDATE time_entries SET finished_at=?, closed_by=? WHERE id=?",
                   (finished, closed_by, r["id"]))
        audit(db, user_id, "stop", "time_entry", r["id"],
              {"task_id": r["task_id"], "closed_by": closed_by, "finished_at": finished})
    return len(rows)


def open_intervals_for_user(db, user_id):
    return db.query_all(
        "SELECT e.id, e.task_id, e.started_at, t.title FROM time_entries e "
        "JOIN tasks t ON t.id=e.task_id "
        "WHERE e.user_id=? AND e.finished_at IS NULL ORDER BY e.started_at", (user_id,))


def open_intervals_all(db):
    """Все открытые интервалы всех участников (закрытие приложения, п.5.4 ТЗ)."""
    return db.query_all(
        "SELECT e.id, e.task_id, e.user_id, e.started_at, t.title, u.login "
        "FROM time_entries e JOIN tasks t ON t.id=e.task_id JOIN users u ON u.id=e.user_id "
        "WHERE e.finished_at IS NULL ORDER BY e.started_at")


def stop_all_open(db, closed_by) -> int:
    """Закрыть все открытые интервалы всех участников текущим временем."""
    rows = db.query_all(
        "SELECT id, task_id, user_id FROM time_entries WHERE finished_at IS NULL")
    finished = now_iso()
    for r in rows:
        db.execute("UPDATE time_entries SET finished_at=?, closed_by=? WHERE id=?",
                   (finished, closed_by, r["id"]))
        audit(db, r["user_id"], "stop", "time_entry", r["id"],
              {"task_id": r["task_id"], "closed_by": closed_by,
               "finished_at": finished})
    return len(rows)


def list_intervals(db, task_id):
    return db.query_all(
        "SELECT e.*, u.login, u.is_deleted AS user_deleted FROM time_entries e "
        "JOIN users u ON u.id=e.user_id WHERE e.task_id=? "
        "ORDER BY e.started_at DESC, e.id DESC", (task_id,))


def update_interval(db, actor_id, entry_id, started_at: str, finished_at: Optional[str]):
    """Редактирование интервала (только админ, аудит edit_time_entry)."""
    _require_admin(db, actor_id)
    entry = db.query_one("SELECT * FROM time_entries WHERE id=?", (entry_id,))
    if entry is None:
        raise Validation("Интервал не найден")
    if not started_at:
        raise Validation("Укажите начало интервала")
    try:
        parse_ts(started_at)
        if finished_at:
            parse_ts(finished_at)
    except ValueError:
        raise Validation("Неверный формат даты/времени")
    if finished_at and finished_at <= started_at:
        raise Validation("Окончание должно быть позже начала")
    db.execute("UPDATE time_entries SET started_at=?, finished_at=? WHERE id=?",
               (started_at, finished_at, entry_id))
    audit(db, actor_id, "edit_time_entry", "time_entry", entry_id,
          {"task_id": entry["task_id"], "old": {"started_at": entry["started_at"],
                                                "finished_at": entry["finished_at"]},
           "new": {"started_at": started_at, "finished_at": finished_at}})


def recover_open_intervals(db) -> int:
    """Heartbeat-восстановление (п.5.4 ТЗ): при старте приложения все открытые
    интервалы закрываются временем last_activity_at (если оно >= started_at)."""
    last = get_setting(db, HEARTBEAT_KEY)
    rows = db.query_all(
        "SELECT id, user_id, task_id, started_at FROM time_entries WHERE finished_at IS NULL")
    for r in rows:
        finished = r["started_at"]
        if last and last >= r["started_at"]:
            finished = last
        db.execute("UPDATE time_entries SET finished_at=?, closed_by='shutdown_recovery' WHERE id=?",
                   (finished, r["id"]))
        audit(db, r["user_id"], "stop", "time_entry", r["id"],
              {"task_id": r["task_id"], "closed_by": "shutdown_recovery",
               "finished_at": finished, "recovered": True})
    return len(rows)


# ---------- шаблоны ----------

def get_template(db, template_id):
    return db.query_one("SELECT * FROM templates WHERE id=?", (template_id,))


def _validate_template_fields(db, name, default_title, default_priority, visibility, owner_id):
    name = (name or "").strip()
    if not name:
        raise Validation("Укажите название шаблона")
    default_title = (default_title or "").strip()
    if not default_title:
        raise Validation("Укажите название задачи по умолчанию")
    if default_priority not in PRIORITY_LABELS:
        raise Validation("Недопустимый приоритет")
    if visibility not in ("private", "shared"):
        raise Validation("Недопустимая видимость")
    if get_user(db, owner_id) is None:
        raise Validation("Владелец не найден")
    return name, default_title


def create_template(db, actor_id, name, default_title, default_description="",
                    default_priority=1, visibility="private") -> int:
    name, default_title = _validate_template_fields(
        db, name, default_title, default_priority, visibility, actor_id)
    cur = db.execute(
        "INSERT INTO templates(name, default_title, default_description, default_priority, "
        "visibility, owner_id, created_at) VALUES(?,?,?,?,?,?,?)",
        (name, default_title, default_description or "", default_priority,
         visibility, actor_id, now_iso()))
    template_id = cur.lastrowid
    audit(db, actor_id, "create_template", "template", template_id, {"name": name})
    return template_id


def update_template(db, actor_id, template_id, name, default_title, default_description,
                    default_priority, visibility):
    actor = get_user(db, actor_id)
    tpl = get_template(db, template_id)
    if tpl is None:
        raise Validation("Шаблон не найден")
    if not (_is_admin(actor) or tpl["owner_id"] == actor_id):
        raise PermissionDenied("Редактировать шаблон может владелец или администратор")
    name, default_title = _validate_template_fields(
        db, name, default_title, default_priority, visibility, tpl["owner_id"])
    db.execute(
        "UPDATE templates SET name=?, default_title=?, default_description=?, "
        "default_priority=?, visibility=? WHERE id=?",
        (name, default_title, default_description or "", default_priority,
         visibility, template_id))
    audit(db, actor_id, "update_template", "template", template_id, {"name": name})
    if tpl["owner_id"] != actor_id:
        audit(db, actor_id, "admin_edit", "template", template_id, {"name": name})


def delete_template(db, actor_id, template_id):
    actor = get_user(db, actor_id)
    tpl = get_template(db, template_id)
    if tpl is None:
        raise Validation("Шаблон не найден")
    if not (_is_admin(actor) or tpl["owner_id"] == actor_id):
        raise PermissionDenied("Удалять шаблон может владелец или администратор")
    db.execute("DELETE FROM templates WHERE id=?", (template_id,))
    audit(db, actor_id, "delete_template", "template", template_id, {"name": tpl["name"]})


def list_templates(db, actor_id) -> list[dict]:
    """Видимость шаблонов: свои + общие (равноправие участников, без обхода)."""
    rows = db.query_all(
        "SELECT t.*, u.login AS owner_login, u.is_deleted AS owner_deleted "
        "FROM templates t JOIN users u ON u.id=t.owner_id "
        "WHERE t.visibility='shared' OR t.owner_id=? ORDER BY t.name", (actor_id,))
    return [dict(r) for r in rows]


def quick_start(db, actor_id, template_id) -> tuple[int, int]:
    """«Быстрый старт»: создать задачу из шаблона и сразу открыть интервал."""
    tpl = get_template(db, template_id)
    if tpl is None:
        raise Validation("Шаблон не найден")
    task_id = create_task(db, actor_id, tpl["default_title"], tpl["default_description"],
                          tpl["default_priority"], tpl["visibility"], owner_id=actor_id)
    entry_id = start_interval(db, actor_id, task_id)
    return task_id, entry_id


# ---------- отчёты ----------

def list_my_entries(db, user_id, date_from, date_to, task_id=None):
    """Записи времени пользователя за период (п.2 ТЗ: «просмотр своих записей»).

    date_from/date_to — datetime.date (включительно, по started_at).
    Возвращает строки: id, task_id, title, started_at, finished_at, closed_by,
    seconds (у открытого интервала — текущая длительность, обновляемая UI).
    """
    conds = ["e.user_id=?", "e.started_at >= ?", "e.started_at <= ?"]
    params: list = [user_id,
                    date_from.strftime("%Y-%m-%d 00:00:00"),
                    date_to.strftime("%Y-%m-%d 23:59:59")]
    if task_id:
        conds.append("e.task_id=?")
        params.append(task_id)
    rows = db.query_all(
        f"""SELECT e.id, e.task_id, t.title, e.started_at, e.finished_at, e.closed_by
            FROM time_entries e
            JOIN tasks t ON t.id=e.task_id
            WHERE {" AND ".join(conds)}
            ORDER BY e.started_at DESC, e.id DESC""", params)
    now = datetime.now()
    result = []
    for r in rows:
        d = dict(r)
        if d["finished_at"]:
            d["seconds"] = ((parse_ts(d["finished_at"])
                             - parse_ts(d["started_at"])).total_seconds())
        else:
            d["seconds"] = max(0.0, (now - parse_ts(d["started_at"])).total_seconds())
        result.append(d)
    return result


def list_tasks_for_user_combobox(db, user_id):
    """Задачи, доступные пользователю (свои + общие), для фильтра «Мои записи»."""
    return db.query_all(
        "SELECT id, title, is_archived FROM tasks "
        "WHERE is_hidden=0 AND (visibility='shared' OR owner_id=?) "
        "ORDER BY title", (user_id,))


def member_stats(db, date_from, date_to) -> dict[int, int]:
    """Суммарное закрытое время по участникам за период (профиль команды).

    Возвращает {user_id: seconds}; участники без записей отсутствуют.
    """
    rows = db.query_all(
        f"""SELECT e.user_id, COALESCE(SUM({_closed_seconds_expr()}),0) AS seconds
            FROM time_entries e
            WHERE e.finished_at IS NOT NULL AND e.started_at >= ? AND e.started_at <= ?
            GROUP BY e.user_id""",
        [date_from.strftime("%Y-%m-%d 00:00:00"),
         date_to.strftime("%Y-%m-%d 23:59:59")])
    return {r["user_id"]: r["seconds"] for r in rows}


def report_by_users(db, date_from, date_to, user_id=None, task_id=None):
    """Отчёт по пользователям за период (только закрытые интервалы, п.5.5 ТЗ).

    date_from/date_to — datetime.date (включительно, по started_at).
    Возвращает строки: login, user_deleted, task_id, title, archived, hidden, seconds, n.
    """
    conds = ["e.finished_at IS NOT NULL", "e.started_at >= ?", "e.started_at <= ?"]
    params: list = [date_from.strftime("%Y-%m-%d 00:00:00"),
                    date_to.strftime("%Y-%m-%d 23:59:59")]
    if user_id:
        conds.append("e.user_id=?")
        params.append(user_id)
    if task_id:
        conds.append("e.task_id=?")
        params.append(task_id)
    return db.query_all(
        f"""SELECT u.login, u.is_deleted AS user_deleted, t.id AS task_id, t.title,
               t.is_archived AS archived, t.is_hidden AS hidden,
               COALESCE(SUM({_closed_seconds_expr()}),0) AS seconds,
               COUNT(*) AS n
            FROM time_entries e
            JOIN users u ON u.id=e.user_id
            JOIN tasks t ON t.id=e.task_id
            WHERE {" AND ".join(conds)}
            GROUP BY u.login, t.id
            ORDER BY u.login, t.title""", params)
