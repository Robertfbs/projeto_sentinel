from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from pipeline_common import normalize_column_name


@dataclass(frozen=True)
class SchemaValidationIssue:
    source_name: str
    severity: str
    code: str
    message: str
    details: dict[str, object] | None = None


def build_normalized_column_map(df: pd.DataFrame) -> dict[str, str]:
    return {
        normalize_column_name(column): str(column).strip()
        for column in df.columns
    }


def find_missing_columns(df: pd.DataFrame, required_columns: list[str]) -> list[str]:
    normalized_map = build_normalized_column_map(df)
    return [column for column in required_columns if column not in normalized_map]


def has_any_non_empty_value(df: pd.DataFrame, candidate_columns: list[str]) -> bool:
    normalized_map = build_normalized_column_map(df)
    for candidate in candidate_columns:
        original = normalized_map.get(candidate)
        if not original:
            continue
        series = (
            df[original]
            .astype("string")
            .str.strip()
            .replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
        )
        if series.notna().any():
            return True
    return False
