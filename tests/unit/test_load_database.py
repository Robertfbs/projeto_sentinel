from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from db_utils import connect
from load_database import upsert_sqlite


class UpsertSqliteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        self.conn = connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE tickets (
                ticket_id INTEGER PRIMARY KEY,
                status TEXT,
                titulo TEXT
            );
            """
        )

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def test_insert_and_update(self) -> None:
        df1 = pd.DataFrame([{"ticket_id": 1, "status": "OPEN", "titulo": "A"}])
        upsert_sqlite(df1, "tickets", "ticket_id", self.conn)
        self.conn.commit()

        df2 = pd.DataFrame(
            [
                {"ticket_id": 1, "status": "CLOSED", "titulo": "A2"},
                {"ticket_id": 2, "status": "OPEN", "titulo": "B"},
            ]
        )
        upsert_sqlite(df2, "tickets", "ticket_id", self.conn)
        self.conn.commit()

        rows = self.conn.execute("SELECT ticket_id, status, titulo FROM tickets ORDER BY ticket_id").fetchall()
        self.assertEqual(rows, [(1, "CLOSED", "A2"), (2, "OPEN", "B")])

    def test_rejects_unknown_table(self) -> None:
        df = pd.DataFrame([{"ticket_id": 1}])
        with self.assertRaises(ValueError):
            upsert_sqlite(df, "tabela_invalida; DROP TABLE tickets;--", "ticket_id", self.conn)

    def test_rejects_invalid_column(self) -> None:
        df = pd.DataFrame([{"ticket_id": 1, "evil col": "x"}])
        with self.assertRaises(ValueError):
            upsert_sqlite(df, "tickets", "ticket_id", self.conn)

    def test_empty_dataframe_is_noop(self) -> None:
        df = pd.DataFrame(columns=["ticket_id", "status", "titulo"])
        upsert_sqlite(df, "tickets", "ticket_id", self.conn)
        # Nenhuma linha inserida; nenhuma exception.
        count = self.conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
