"""SQLite persistence for people, tasks, and update history."""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DATABASE_PATH", "coordinator.db"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS people (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
          telegram_id INTEGER UNIQUE
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
          assignee_id INTEGER REFERENCES people(id), unblocker_id INTEGER REFERENCES people(id),
          status TEXT NOT NULL DEFAULT 'Pending', blocker TEXT,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS updates (
          id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
          person_id INTEGER REFERENCES people(id), message TEXT NOT NULL,
          status TEXT NOT NULL, blocker TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS followups (
          id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
          recipient_id INTEGER NOT NULL REFERENCES people(id), message TEXT NOT NULL,
          sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def add_person(name: str, telegram_id: int | None = None):
    with connect() as db:
        db.execute("INSERT INTO people(name,telegram_id) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET telegram_id=COALESCE(excluded.telegram_id,people.telegram_id)", (name.strip(), telegram_id))
        return db.execute("SELECT * FROM people WHERE name=? COLLATE NOCASE", (name.strip(),)).fetchone()


def person_by_telegram(telegram_id: int):
    with connect() as db:
        return db.execute("SELECT * FROM people WHERE telegram_id=?", (telegram_id,)).fetchone()


def people():
    with connect() as db:
        return db.execute("SELECT * FROM people ORDER BY name").fetchall()


def create_task(title: str, description: str = "", assignee_id=None, unblocker_id=None):
    with connect() as db:
        cur = db.execute("INSERT INTO tasks(title,description,assignee_id,unblocker_id,status) VALUES(?,?,?,?, 'Pending')", (title, description, assignee_id, unblocker_id))
        return cur.lastrowid


def tasks(status: str | None = None):
    with connect() as db:
        if status and status != "All":
            return db.execute("""SELECT t.*, a.name assignee, u.name unblocker FROM tasks t LEFT JOIN people a ON a.id=t.assignee_id LEFT JOIN people u ON u.id=t.unblocker_id WHERE t.status=? ORDER BY t.id""", (status,)).fetchall()
        return db.execute("""SELECT t.*, a.name assignee, u.name unblocker FROM tasks t LEFT JOIN people a ON a.id=t.assignee_id LEFT JOIN people u ON u.id=t.unblocker_id ORDER BY t.id""").fetchall()


def task(task_id: int):
    with connect() as db:
        return db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()


def set_task_status(task_id: int, status: str, blocker: str | None = None):
    with connect() as db:
        db.execute("UPDATE tasks SET status=?, blocker=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, blocker, task_id))


def update_task_management(task_id: int, status: str, blocker: str | None, assignee_id: int | None, unblocker_id: int | None):
    with connect() as db:
        db.execute(
            """UPDATE tasks SET status=?, blocker=?, assignee_id=?, unblocker_id=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, blocker, assignee_id, unblocker_id, task_id),
        )


def add_update(task_id: int, person_id: int | None, message: str, status: str, blocker: str | None):
    with connect() as db:
        db.execute("INSERT INTO updates(task_id,person_id,message,status,blocker) VALUES(?,?,?,?,?)", (task_id, person_id, message, status, blocker))


def add_followup(task_id: int, recipient_id: int, message: str):
    with connect() as db:
        db.execute("INSERT INTO followups(task_id,recipient_id,message) VALUES(?,?,?)", (task_id, recipient_id, message))


def update_history(limit=50):
    with connect() as db:
        return db.execute("""SELECT u.*, t.title, p.name person FROM updates u JOIN tasks t ON t.id=u.task_id LEFT JOIN people p ON p.id=u.person_id ORDER BY u.id DESC LIMIT ?""", (limit,)).fetchall()


def followup_history(limit=50):
    with connect() as db:
        return db.execute("""SELECT f.*, t.title, p.name recipient FROM followups f JOIN tasks t ON t.id=f.task_id JOIN people p ON p.id=f.recipient_id ORDER BY f.id DESC LIMIT ?""", (limit,)).fetchall()
