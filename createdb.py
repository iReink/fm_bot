import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

def create_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    # Таблица ивентов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL,
            address TEXT,
            max_participants INTEGER,
            event_date TEXT,
            event_time TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """)

    # Таблица регистраций участников
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            reg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            event_name TEXT,
            user_name TEXT,
            user_nickname TEXT,
            FOREIGN KEY (event_id) REFERENCES events(event_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Таблица логов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            user_nickname TEXT,
            description TEXT,
            log_date TEXT,
            log_time TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"База данных создана: {DB_PATH}")

if __name__ == "__main__":
    create_tables()
