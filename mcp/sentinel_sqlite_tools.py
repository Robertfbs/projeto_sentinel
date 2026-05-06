from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Iterable

# Permite importar o helper compartilhado do ETL.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from db_utils import assert_table, connect  # noqa: E402


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "03_database" / "pre_contencioso.db"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    return connect(Path(db_path or DEFAULT_DB_PATH), read_only=True)


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
    safe_table = assert_table(table_name)
    with _connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {safe_table}").fetchone()
    return int(row[0] if row else 0)


def fetch_sample(table_name: str, limit: int = 5, db_path: Path | None = None) -> list[tuple]:
    safe_table = assert_table(table_name)
    safe_limit = max(1, min(int(limit), 100))
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM {safe_table} LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return rows


def describe_tables(table_names: Iterable[str], db_path: Path | None = None) -> dict[str, int]:
    return {table_name: count_rows(table_name, db_path) for table_name in table_names}
