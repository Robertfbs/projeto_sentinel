from __future__ import annotations

import unittest

import pandas as pd

from pipeline_common import (
    derive_bloco,
    deduplicate_latest,
    ensure_columns,
    first_not_null,
    normalize_column_name,
    normalize_identifier,
    normalize_subject,
    normalize_text,
    normalize_token_set,
    serialize_datetime,
)


class NormalizeTextTests(unittest.TestCase):
    def test_strips_accents_and_uppercases(self) -> None:
        self.assertEqual(normalize_text("São José  "), "SAO JOSE")

    def test_returns_none_for_nan_or_empty(self) -> None:
        self.assertIsNone(normalize_text(None))
        self.assertIsNone(normalize_text(float("nan")))
        self.assertIsNone(normalize_text("   "))

    def test_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_text("a    b\tc"), "A B C")


class NormalizeIdentifierTests(unittest.TestCase):
    def test_removes_trailing_dot_zero_only(self) -> None:
        self.assertEqual(normalize_identifier("40001.0"), "40001")
        # Pontos no meio devem ser preservados.
        self.assertEqual(normalize_identifier("40.01"), "40.01")

    def test_handles_multiple_trailing_zeros(self) -> None:
        self.assertEqual(normalize_identifier("123.00"), "123")

    def test_returns_none_for_blank(self) -> None:
        self.assertIsNone(normalize_identifier(None))
        self.assertIsNone(normalize_identifier(""))


class DeriveBlocoTests(unittest.TestCase):
    def test_prefix_40_is_bloco_4(self) -> None:
        self.assertEqual(derive_bloco("40123"), "Bloco 4")

    def test_prefix_10_is_bloco_1(self) -> None:
        self.assertEqual(derive_bloco("10987"), "Bloco 1")

    def test_unknown_prefix_returns_none(self) -> None:
        self.assertIsNone(derive_bloco("99999"))

    def test_handles_excel_float_artifact(self) -> None:
        self.assertEqual(derive_bloco("40123.0"), "Bloco 4")


class NormalizeSubjectTokenSetTests(unittest.TestCase):
    def test_subject_strips_punctuation(self) -> None:
        self.assertEqual(normalize_subject("Cobrança - 2024/02!"), "COBRANCA 2024 02")

    def test_token_set_drops_short_tokens(self) -> None:
        # Tokens com 2 ou menos caracteres sao descartados.
        self.assertEqual(normalize_token_set("a be cde"), {"CDE"})


class FirstNotNullTests(unittest.TestCase):
    def test_returns_first_non_blank_value(self) -> None:
        row = pd.Series({"a": None, "b": "  ", "c": "x", "d": "y"})
        self.assertEqual(first_not_null(row, ["a", "b", "c", "d"]), "x")

    def test_returns_none_when_all_blank(self) -> None:
        row = pd.Series({"a": None, "b": "  "})
        self.assertIsNone(first_not_null(row, ["a", "b"]))


class DeduplicateLatestTests(unittest.TestCase):
    def test_keeps_last_record_in_sort_order(self) -> None:
        df = pd.DataFrame(
            [
                {"id": 1, "ts": "2024-01-01", "v": "old"},
                {"id": 1, "ts": "2024-06-01", "v": "new"},
                {"id": 2, "ts": "2024-02-01", "v": "x"},
            ]
        )
        out = deduplicate_latest(df, subset=["id"], sort_columns=["ts"])
        ids = out.set_index("id")["v"].to_dict()
        self.assertEqual(ids, {1: "new", 2: "x"})

    def test_empty_input_returns_empty(self) -> None:
        df = pd.DataFrame(columns=["id", "ts"])
        out = deduplicate_latest(df, subset=["id"], sort_columns=["ts"])
        self.assertTrue(out.empty)


class EnsureColumnsTests(unittest.TestCase):
    def test_adds_missing_columns_with_none(self) -> None:
        df = pd.DataFrame([{"a": 1}])
        out = ensure_columns(df, ["a", "b", "c"])
        self.assertListEqual(list(out.columns), ["a", "b", "c"])
        self.assertTrue(out["b"].isna().all())


class SerializeDatetimeTests(unittest.TestCase):
    def test_formats_timestamp(self) -> None:
        ts = pd.Timestamp("2024-03-15 10:30:00")
        self.assertEqual(serialize_datetime(ts), "2024-03-15 10:30:00")

    def test_returns_none_for_invalid(self) -> None:
        self.assertIsNone(serialize_datetime("nao eh data"))
        self.assertIsNone(serialize_datetime(None))


class NormalizeColumnNameTests(unittest.TestCase):
    def test_normalizes_with_underscores(self) -> None:
        self.assertEqual(normalize_column_name("Número da Porta"), "numero_da_porta")
        self.assertEqual(normalize_column_name("ID-do-Ticket"), "id_do_ticket")


if __name__ == "__main__":
    unittest.main()
