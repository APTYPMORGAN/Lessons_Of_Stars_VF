"""
Хранилище профилей пользователей VK-бота (SQLite).

Отдельная база vk_bot.db — база Telegram-бота (bot.db) не затрагивается.
VK ID и Telegram ID — РАЗНЫЕ идентификаторы, они никогда не смешиваются:
здесь таблица только для VK.
"""

import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS vk_users (
    vk_id INTEGER PRIMARY KEY,
    course INTEGER,
    faculty TEXT,
    group_name TEXT,
    last_message_id INTEGER
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_FILE)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def get_profile(vk_id: int) -> dict | None:
    """Возвращает {'course':..,'faculty':..,'group_name':..} или None, если профиля нет."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT course, faculty, group_name FROM vk_users WHERE vk_id = ?",
            (vk_id,),
        ).fetchone()
    if row is None or row[2] is None:
        return None
    return {"course": row[0], "faculty": row[1], "group_name": row[2]}


def save_profile(vk_id: int, course: int, faculty: str, group_name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO vk_users (vk_id, course, faculty, group_name)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(vk_id) DO UPDATE SET
                   course = excluded.course,
                   faculty = excluded.faculty,
                   group_name = excluded.group_name""",
            (vk_id, course, faculty, group_name),
        )


def all_vk_ids() -> list[int]:
    """Все VK ID пользователей, взаимодействовавших с ботом (для рассылки)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT vk_id FROM vk_users").fetchall()
    return [r[0] for r in rows]


# --- память последнего сообщения бота (для "удаления/замены" предыдущего ответа) ---

def get_last_message_id(vk_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_message_id FROM vk_users WHERE vk_id = ?", (vk_id,)
        ).fetchone()
    return row[0] if row and row[0] else None


def set_last_message_id(vk_id: int, message_id: int | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO vk_users (vk_id, last_message_id)
               VALUES (?, ?)
               ON CONFLICT(vk_id) DO UPDATE SET last_message_id = excluded.last_message_id""",
            (vk_id, message_id),
        )
