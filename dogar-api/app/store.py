"""SQLite persistence: site content, plus Dogar's vector index.

SQLite keeps deployment to a single file and no extra service. If you'd rather
run PostgreSQL on Neon with pgvector — the stack you already use — only the four
functions below need rewriting; nothing else in the app touches the database.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS content (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    data    TEXT NOT NULL,
    updated TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS passages (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title  TEXT NOT NULL,
    text   TEXT NOT NULL,
    vector BLOB NOT NULL
);
"""

EMPTY = {"identity": {}, "socials": [], "projects": [], "timeline": [], "knowledge": []}


def _connect() -> sqlite3.Connection:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def read_content() -> dict:
    """Full content, knowledge included. Admin-only."""
    with _connect() as conn:
        row = conn.execute("SELECT data FROM content WHERE id = 1").fetchone()
    return json.loads(row[0]) if row else dict(EMPTY)


def public_content() -> dict:
    """What the site itself loads. Dogar's brain is stripped out."""
    data = read_content()
    data.pop("knowledge", None)
    return data


def write_content(data: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO content (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated = CURRENT_TIMESTAMP",
            (json.dumps(data, ensure_ascii=False),),
        )


def replace_passages(rows: list[tuple[str, str, np.ndarray]]) -> int:
    """Swap the whole index atomically after a Studio save."""
    with _connect() as conn:
        conn.execute("DELETE FROM passages")
        conn.executemany(
            "INSERT INTO passages (title, text, vector) VALUES (?, ?, ?)",
            [(t, x, v.astype(np.float32).tobytes()) for t, x, v in rows],
        )
    return len(rows)


def all_passages() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT title, text, vector FROM passages").fetchall()
    return [
        {"title": t, "text": x, "vector": np.frombuffer(v, dtype=np.float32)}
        for t, x, v in rows
    ]
