import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "users.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            name TEXT,
            joined_date TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER NOT NULL,
            letter_id INTEGER NOT NULL,
            learned INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, letter_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_active TEXT,
            level_1_complete INTEGER DEFAULT 0,
            level_2_complete INTEGER DEFAULT 0,
            level_3_complete INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_dialogues (
            user_id INTEGER NOT NULL,
            dialogue_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'partial',
            plays INTEGER DEFAULT 0,
            collected_at TEXT DEFAULT (datetime('now')),
            last_play TEXT,
            PRIMARY KEY (user_id, dialogue_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            dialogue_daily INTEGER DEFAULT 1,
            verbs_intro INTEGER DEFAULT 0,
            sentence_intro INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # Лёгкая миграция для уже существующих таблиц (добавляем новые колонки)
    cols = [r["name"] for r in cursor.execute("PRAGMA table_info(user_settings)")]
    if "verbs_intro" not in cols:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN verbs_intro INTEGER DEFAULT 0")
    if "sentence_intro" not in cols:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN sentence_intro INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


def register_user(user_id, chat_id, name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, chat_id, name) VALUES (?, ?, ?)",
        (user_id, chat_id, name),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO stats (user_id) VALUES (?)",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_learned_letters(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT letter_id FROM progress WHERE user_id = ? AND learned = 1",
        (user_id,),
    )
    learned = [row["letter_id"] for row in cursor.fetchall()]
    conn.close()
    return learned


def mark_letter_learned(user_id, letter_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO progress (user_id, letter_id, learned) VALUES (?, ?, 1)",
        (user_id, letter_id),
    )
    conn.commit()
    conn.close()


def add_points(user_id, points):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE stats SET
            total_points = total_points + ?,
            current_streak = current_streak + 1,
            best_streak = MAX(best_streak, current_streak + 1),
            last_active = datetime('now')
        WHERE user_id = ?
        """,
        (points, user_id),
    )
    conn.commit()
    conn.close()


def get_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stats WHERE user_id = ?", (user_id,))
    stats = cursor.fetchone()
    conn.close()
    return dict(stats) if stats else None


def reset_streak(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE stats SET current_streak = 0 WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


# ===== Диалоги =====

def collect_dialogue(user_id, dialogue_id, status):
    """Заносит диалог в коллекцию пользователя.

    full — прослушаны все реплики, partial — недопрослушан.
    Повторный partial НЕ перезаписывает уже собранный full.
    Возвращает: 'full' | 'partial' | None (если partial при существующем full).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM user_dialogues WHERE user_id = ? AND dialogue_id = ?",
        (user_id, dialogue_id),
    )
    row = cursor.fetchone()
    if row is not None and row["status"] == "full" and status == "partial":
        conn.close()
        return None
    cursor.execute(
        """
        INSERT INTO user_dialogues (user_id, dialogue_id, status, collected_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, dialogue_id) DO UPDATE SET
            status = excluded.status,
            collected_at = datetime('now')
        """,
        (user_id, dialogue_id, status),
    )
    conn.commit()
    conn.close()
    return status


def get_dialogue_status(user_id, dialogue_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM user_dialogues WHERE user_id = ? AND dialogue_id = ?",
        (user_id, dialogue_id),
    )
    row = cursor.fetchone()
    conn.close()
    return row["status"] if row else None


def mark_dialogue_played(user_id, dialogue_id):
    """Отмечает прослушивание реплики диалога (для засчитывания full)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_dialogues (user_id, dialogue_id, status, plays, last_play)
        VALUES (?, ?, 'partial', 1, datetime('now'))
        ON CONFLICT(user_id, dialogue_id) DO UPDATE SET
            plays = plays + 1,
            last_play = datetime('now')
        """,
        (user_id, dialogue_id),
    )
    conn.commit()
    conn.close()


def get_collected_dialogues(user_id):
    """Все собранные диалоги пользователя (id + статус)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT dialogue_id, status, plays, collected_at FROM user_dialogues WHERE user_id = ? ORDER BY collected_at",
        (user_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ===== Настройки (отписка от рассылки) =====

def get_dialogue_daily_enabled(user_id):
    """Рассылка диалога дня включена? По умолчанию — да (1)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT dialogue_daily FROM user_settings WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row["dialogue_daily"] if row else 1


def set_dialogue_daily(user_id, enabled):
    """Вкл/выкл ежедневную выдачу диалога дня (отписка от рассылки)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_settings (user_id, dialogue_daily)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET dialogue_daily = excluded.dialogue_daily
        """,
        (user_id, 1 if enabled else 0),
    )
    conn.commit()
    conn.close()


# ===== Флаги вводных экранов модулей =====

_INTRO_FIELDS = ("verbs_intro", "sentence_intro")


def get_intro_seen(user_id, field):
    """Видел ли пользователь вводный экран модуля (verbs_intro / sentence_intro)."""
    assert field in _INTRO_FIELDS, f"неизвестное поле {field}"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {field} FROM user_settings WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return bool(row[field]) if row else False


def mark_intro_seen(user_id, field):
    """Отмечает, что вводный экран модуля показан."""
    assert field in _INTRO_FIELDS, f"неизвестное поле {field}"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        INSERT INTO user_settings (user_id, {field})
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET {field} = 1
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()

