"""Избранное «посмотреть позже»: фильмы пользователей хранятся в SQLite."""
import sqlite3
from pathlib import Path

DB_PATH = "data/favorites.db"
PAGE_SIZE = 20  # как в списках TMDB, чтобы клавиатура с номерами выглядела одинаково


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    # ponytail: синхронный sqlite3 внутри async-бота — запросы локальные и быстрые; aiosqlite, если упрёмся
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        release_date TEXT NOT NULL,
        PRIMARY KEY (user_id, movie_id))""")
    return db


def add(db: sqlite3.Connection, user_id: int, movie_id: int, title: str, release_date: str) -> bool:
    """True, если фильма ещё не было в избранном."""
    with db:
        cursor = db.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?, ?, ?)",
                            (user_id, movie_id, title, release_date))
    return cursor.rowcount == 1


def remove(db: sqlite3.Connection, user_id: int, movie_id: int) -> bool:
    """True, если фильм был в избранном."""
    with db:
        cursor = db.execute("DELETE FROM favorites WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
    return cursor.rowcount == 1


def contains(db: sqlite3.Connection, user_id: int, movie_id: int) -> bool:
    query = "SELECT 1 FROM favorites WHERE user_id = ? AND movie_id = ?"
    return db.execute(query, (user_id, movie_id)).fetchone() is not None


def page(db: sqlite3.Connection, user_id: int, number: int) -> dict:
    """Страница избранного в том же виде, что списки TMDB: total_pages и results. Новые фильмы сверху."""
    total = db.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)).fetchone()[0]
    rows = db.execute("SELECT movie_id, title, release_date FROM favorites WHERE user_id = ? "
                      "ORDER BY rowid DESC LIMIT ? OFFSET ?", (user_id, PAGE_SIZE, (number - 1) * PAGE_SIZE))
    return {"total_pages": -(-total // PAGE_SIZE),
            "results": [{"id": movie_id, "title": title, "release_date": date} for movie_id, title, date in rows]}
