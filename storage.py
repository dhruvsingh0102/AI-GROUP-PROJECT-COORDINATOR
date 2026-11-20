"""SQLite-local / Supabase-hosted persistence for the coordinator."""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DATABASE_PATH", "coordinator.db"))


def using_supabase() -> bool:
    url = os.getenv("SUPABASE_URL", "").strip()
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if bool(url) != bool(secret):
        raise RuntimeError("Set both SUPABASE_URL and SUPABASE_SECRET_KEY, or leave both empty for SQLite.")
    return bool(url)


@lru_cache(maxsize=1)
def supabase_client():
    if not using_supabase():
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY.")
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_SECRET_KEY"].strip())


def connect():
    """Open a SQLite connection. Supabase callers should use the functions below."""
    if using_supabase():
        raise RuntimeError("Direct SQLite access is unavailable in Supabase mode.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    if using_supabase():
        # Keep deployment setup explicit: the schema is created from supabase/schema.sql.
        try:
            supabase_client().table("people").select("id,whatsapp_phone,whatsapp_last_inbound_at").limit(1).execute()
            supabase_client().table("processed_whatsapp_messages").select("message_id").limit(1).execute()
        except Exception as exc:
            raise RuntimeError(
                "Could not read the WhatsApp schema in Supabase. Run supabase/whatsapp_migration.sql. "
                f"Details: {exc}"
            ) from exc
        return

    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS people (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
          telegram_id INTEGER UNIQUE, whatsapp_phone TEXT UNIQUE,
          whatsapp_last_inbound_at TEXT
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
        CREATE TABLE IF NOT EXISTS processed_whatsapp_messages (
          message_id TEXT PRIMARY KEY,
          received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        people_columns = {row["name"] for row in db.execute("PRAGMA table_info(people)").fetchall()}
        if "whatsapp_phone" not in people_columns:
            db.execute("ALTER TABLE people ADD COLUMN whatsapp_phone TEXT")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS people_whatsapp_phone_idx ON people(whatsapp_phone)")
        if "whatsapp_last_inbound_at" not in people_columns:
            db.execute("ALTER TABLE people ADD COLUMN whatsapp_last_inbound_at TEXT")


def _remote_rows(response) -> list[dict]:
    return response.data or []


def normalize_whatsapp_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if not 8 <= len(digits) <= 15:
        raise ValueError("WhatsApp phone numbers must be in international format with 8 to 15 digits.")
    return digits


def add_person(name: str, whatsapp_phone: str | None = None):
    name = name.strip()
    phone = normalize_whatsapp_phone(whatsapp_phone) if whatsapp_phone else None
    if using_supabase():
        client = supabase_client()
        normalized = name.casefold()
        rows = _remote_rows(
            client.table("people").select("*").eq("name_normalized", normalized).limit(1).execute()
        )
        if rows:
            row = rows[0]
            if phone is not None:
                updated = _remote_rows(
                    client.table("people").update({
                        "whatsapp_phone": phone,
                        "whatsapp_last_inbound_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", row["id"]).execute()
                )
                if updated:
                    return updated[0]
            return row
        rows = _remote_rows(
            client.table("people").insert({
                "name": name,
                "name_normalized": normalized,
                "whatsapp_phone": phone,
                "whatsapp_last_inbound_at": datetime.now(timezone.utc).isoformat() if phone else None,
            }).execute()
        )
        return rows[0] if rows else None

    with connect() as db:
        db.execute(
            "INSERT INTO people(name,whatsapp_phone,whatsapp_last_inbound_at) VALUES(?,?,CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END) "
            "ON CONFLICT(name) DO UPDATE SET "
            "whatsapp_phone=COALESCE(excluded.whatsapp_phone,people.whatsapp_phone), "
            "whatsapp_last_inbound_at=CASE WHEN excluded.whatsapp_phone IS NOT NULL THEN CURRENT_TIMESTAMP ELSE people.whatsapp_last_inbound_at END",
            (name, phone, phone),
        )
        return dict(db.execute("SELECT * FROM people WHERE name=? COLLATE NOCASE", (name,)).fetchone())


def person_by_whatsapp(phone: str):
    phone = normalize_whatsapp_phone(phone)
    if using_supabase():
        rows = _remote_rows(
            supabase_client().table("people").select("*").eq("whatsapp_phone", phone).limit(1).execute()
        )
        return rows[0] if rows else None
    with connect() as db:
        row = db.execute("SELECT * FROM people WHERE whatsapp_phone=?", (phone,)).fetchone()
        return dict(row) if row else None


def note_whatsapp_inbound(person_id: int):
    if using_supabase():
        supabase_client().table("people").update({
            "whatsapp_last_inbound_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", person_id).execute()
        return
    with connect() as db:
        db.execute("UPDATE people SET whatsapp_last_inbound_at=CURRENT_TIMESTAMP WHERE id=?", (person_id,))


def whatsapp_window_open(person: dict, hours: int = 24) -> bool:
    value = person.get("whatsapp_last_inbound_at")
    if not value:
        return False
    try:
        last_message = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if last_message.tzinfo is None:
            last_message = last_message.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_message < timedelta(hours=hours)
    except ValueError:
        return False


def claim_whatsapp_message(message_id: str) -> bool:
    """Return false for webhook retries already processed by Meta."""
    if using_supabase():
        try:
            supabase_client().table("processed_whatsapp_messages").insert({"message_id": message_id}).execute()
            return True
        except Exception as exc:
            if "23505" in str(exc) or "duplicate key" in str(exc).lower():
                return False
            raise
    with connect() as db:
        cursor = db.execute("INSERT OR IGNORE INTO processed_whatsapp_messages(message_id) VALUES(?)", (message_id,))
        return cursor.rowcount == 1


def people():
    if using_supabase():
        return _remote_rows(supabase_client().table("people").select("*").order("name").execute())
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM people ORDER BY name").fetchall()]


def create_task(title: str, description: str = "", assignee_id=None, unblocker_id=None):
    if using_supabase():
        rows = _remote_rows(supabase_client().table("tasks").insert({
            "title": title,
            "description": description,
            "assignee_id": assignee_id,
            "unblocker_id": unblocker_id,
            "status": "Pending",
        }).execute())
        return rows[0]["id"] if rows else None
    with connect() as db:
        cur = db.execute(
            "INSERT INTO tasks(title,description,assignee_id,unblocker_id,status) VALUES(?,?,?,?, 'Pending')",
            (title, description, assignee_id, unblocker_id),
        )
        return cur.lastrowid


def tasks(status: str | None = None):
    if using_supabase():
        query = supabase_client().table("tasks").select(
            "*, assignee:people!tasks_assignee_id_fkey(name), unblocker:people!tasks_unblocker_id_fkey(name)"
        )
        if status and status != "All":
            query = query.eq("status", status)
        rows = _remote_rows(query.order("id").execute())
        for row in rows:
            row["assignee"] = (row.get("assignee") or {}).get("name")
            row["unblocker"] = (row.get("unblocker") or {}).get("name")
        return rows
    with connect() as db:
        if status and status != "All":
            rows = db.execute(
                """SELECT t.*, a.name assignee, u.name unblocker FROM tasks t
                   LEFT JOIN people a ON a.id=t.assignee_id LEFT JOIN people u ON u.id=t.unblocker_id
                   WHERE t.status=? ORDER BY t.id""",
                (status,),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT t.*, a.name assignee, u.name unblocker FROM tasks t
                   LEFT JOIN people a ON a.id=t.assignee_id LEFT JOIN people u ON u.id=t.unblocker_id
                   ORDER BY t.id"""
            ).fetchall()
        return [dict(row) for row in rows]


def task(task_id: int):
    if using_supabase():
        rows = _remote_rows(supabase_client().table("tasks").select("*").eq("id", task_id).limit(1).execute())
        return rows[0] if rows else None
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None


def set_task_status(task_id: int, status: str, blocker: str | None = None):
    if using_supabase():
        supabase_client().table("tasks").update({
            "status": status, "blocker": blocker,
        }).eq("id", task_id).execute()
        return
    with connect() as db:
        db.execute("UPDATE tasks SET status=?, blocker=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, blocker, task_id))


def update_task_management(task_id: int, status: str, blocker: str | None, assignee_id: int | None, unblocker_id: int | None):
    if using_supabase():
        supabase_client().table("tasks").update({
            "status": status,
            "blocker": blocker,
            "assignee_id": assignee_id,
            "unblocker_id": unblocker_id,
        }).eq("id", task_id).execute()
        return
    with connect() as db:
        db.execute(
            """UPDATE tasks SET status=?, blocker=?, assignee_id=?, unblocker_id=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, blocker, assignee_id, unblocker_id, task_id),
        )


def add_update(task_id: int, person_id: int | None, message: str, status: str, blocker: str | None):
    if using_supabase():
        supabase_client().table("updates").insert({
            "task_id": task_id, "person_id": person_id, "message": message,
            "status": status, "blocker": blocker,
        }).execute()
        return
    with connect() as db:
        db.execute("INSERT INTO updates(task_id,person_id,message,status,blocker) VALUES(?,?,?,?,?)", (task_id, person_id, message, status, blocker))


def add_followup(task_id: int, recipient_id: int, message: str):
    if using_supabase():
        supabase_client().table("followups").insert({
            "task_id": task_id, "recipient_id": recipient_id, "message": message,
        }).execute()
        return
    with connect() as db:
        db.execute("INSERT INTO followups(task_id,recipient_id,message) VALUES(?,?,?)", (task_id, recipient_id, message))


def update_history(limit=50):
    if using_supabase():
        rows = _remote_rows(
            supabase_client().table("updates").select("*, task:tasks(title), person:people(name)")
            .order("id", desc=True).limit(limit).execute()
        )
        for row in rows:
            row["title"] = (row.pop("task", None) or {}).get("title")
            row["person"] = (row.pop("person", None) or {}).get("name")
        return rows
    with connect() as db:
        rows = db.execute(
            """SELECT u.*, t.title, p.name person FROM updates u JOIN tasks t ON t.id=u.task_id
               LEFT JOIN people p ON p.id=u.person_id ORDER BY u.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def followup_history(limit=50):
    if using_supabase():
        rows = _remote_rows(
            supabase_client().table("followups").select("*, task:tasks(title), recipient:people(name)")
            .order("id", desc=True).limit(limit).execute()
        )
        for row in rows:
            row["title"] = (row.pop("task", None) or {}).get("title")
            row["recipient"] = (row.pop("recipient", None) or {}).get("name")
        return rows
    with connect() as db:
        rows = db.execute(
            """SELECT f.*, t.title, p.name recipient FROM followups f JOIN tasks t ON t.id=f.task_id
               JOIN people p ON p.id=f.recipient_id ORDER BY f.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
