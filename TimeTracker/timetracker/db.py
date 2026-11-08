# -*- coding: utf-8 -*-
"""Слой базы данных: SQLite (stdlib), режим WAL, схема и индексы по разделу 6 ТЗ."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('admin','user')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    is_deleted    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    created_by    INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    priority     INTEGER NOT NULL DEFAULT 1 CHECK(priority IN (0,1,2)),  -- 0/1/2 = Низкий/Обычный/Высокий
    visibility   TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private','shared')),
    owner_id     INTEGER NOT NULL REFERENCES users(id),
    created_by   INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL,
    is_archived  INTEGER NOT NULL DEFAULT 0,
    archived_at  TEXT,
    is_hidden    INTEGER NOT NULL DEFAULT 0  -- скрывается для личных задач удалённых владельцев
);

CREATE TABLE IF NOT EXISTS templates (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    default_title        TEXT NOT NULL DEFAULT '',
    default_description  TEXT NOT NULL DEFAULT '',
    default_priority     INTEGER NOT NULL DEFAULT 1,
    visibility           TEXT NOT NULL DEFAULT 'private' CHECK(visibility IN ('private','shared')),
    owner_id             INTEGER NOT NULL REFERENCES users(id),
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    started_at  TEXT NOT NULL,
    finished_at TEXT,           -- NULL = интервал открыт
    closed_by   TEXT CHECK(closed_by IS NULL OR closed_by IN
                 ('user','logout','app_close','shutdown_recovery','admin'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(id),
    action       TEXT NOT NULL,
    entity_type  TEXT,
    entity_id    INTEGER,
    details_json TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_time_entries_task_finished ON time_entries(task_id, finished_at);
CREATE INDEX IF NOT EXISTS idx_time_entries_user_started  ON time_entries(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_tasks_owner_visibility     ON tasks(owner_id, visibility);
CREATE INDEX IF NOT EXISTS idx_users_login                ON users(login);
"""


class Database:
    """Обёртка над sqlite3: WAL, busy_timeout, внешние ключи, авто-коммит."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # WAL корректен при быстром переключении пользователей Windows
        self.conn.execute("PRAGMA journal_mode=WAL").fetchone()
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def query_all(self, sql: str, params=()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params=()):
        return self.conn.execute(sql, params).fetchone()

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
