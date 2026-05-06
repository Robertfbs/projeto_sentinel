from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from db_utils import ALLOWED_TABLES, assert_identifier, assert_table, connect


class AllowlistTests(unittest.TestCase):
    def test_known_table_passes(self) -> None:
        self.assertEqual(assert_table("tickets"), "tickets")

    def test_unknown_table_raises(self) -> None:
        with self.assertRaises(ValueError):
            assert_table("tickets; DROP TABLE clientes;")
        with self.assertRaises(ValueError):
            assert_table("nao_existe")

    def test_non_string_raises(self) -> None:
        with self.assertRaises(ValueError):
            assert_table(123)  # type: ignore[arg-type]

    def test_allowlist_is_frozen(self) -> None:
        self.assertIsInstance(ALLOWED_TABLES, frozenset)


class IdentifierValidationTests(unittest.TestCase):
    def test_simple_identifier(self) -> None:
        self.assertEqual(assert_identifier("matricula"), "matricula")
        self.assertEqual(assert_identifier("col_1"), "col_1")

    def test_rejects_quotes_and_spaces(self) -> None:
        for bad in ("col with space", "a;b", "1col", "col-name", "col`name", "col\"name"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    assert_identifier(bad)


class ConnectTests(unittest.TestCase):
    def test_connect_enables_pragmas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with connect(db_path) as conn:
                fk_state = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(int(fk_state), 1)
            self.assertEqual(str(journal).lower(), "wal")

    def test_read_only_skips_wal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            # Inicializa o arquivo primeiro.
            sqlite3.connect(db_path).close()
            with connect(db_path, read_only=True) as conn:
                fk_state = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            self.assertEqual(int(fk_state), 1)


if __name__ == "__main__":
    unittest.main()
