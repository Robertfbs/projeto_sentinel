from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "03_database" / "pre_contencioso.db"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    target = Path(db_path or DEFAULT_DB_PATH)
    return sqlite3.connect(target)


def list_tables(db_path: Path | None = None) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()
    return [row[0] for row in rows]


def count_rows(table_name: str, db_path: Path | None = None) -> int:
    with _connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0] if row else 0)


def fetch_sample(table_name: str, limit: int = 5, db_path: Path | None = None) -> list[tuple]:
    safe_limit = max(1, min(limit, 100))
    with _connect(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM {table_name} LIMIT {safe_limit}").fetchall()
    return rows


def describe_tables(table_names: Iterable[str], db_path: Path | None = None) -> dict[str, int]:
    return {table_name: count_rows(table_name, db_path) for table_name in table_names}
