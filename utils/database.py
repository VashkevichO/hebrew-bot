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
    """)
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
