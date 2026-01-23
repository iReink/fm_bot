import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"


def add_notification_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}
    if "notification_on" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN notification_on INTEGER DEFAULT 1")
        conn.commit()
        print("Добавлено поле notification_on в users")
    else:
        print("Поле notification_on уже существует")

    conn.close()


if __name__ == "__main__":
    add_notification_column()
