from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from db_utils import connect as _connect


class DatabaseRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = _connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DatabaseRepository":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None and self._conn is not None:
            self._conn.rollback()
        self.close()

    def begin(self) -> None:
        self.connect().execute("BEGIN")

    def commit(self) -> None:
        self.connect().commit()

    def rollback(self) -> None:
        self.connect().rollback()

    def execute(self, sql: str, params: dict | tuple | None = None) -> sqlite3.Cursor:
        cursor = self.connect().cursor()
        cursor.execute(sql, params or ())
        return cursor

    def executemany(self, sql: str, params_seq: list[tuple] | list[dict]) -> sqlite3.Cursor:
        cursor = self.connect().cursor()
        cursor.executemany(sql, params_seq)
        return cursor

    def fetch_df(self, sql: str, params: dict | tuple | None = None) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.connect(), params=params)

    def table_exists(self, table_name: str) -> bool:
        row = self.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        ).fetchone()
        return row is not None
