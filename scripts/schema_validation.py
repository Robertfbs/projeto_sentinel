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


def _resolve_candidate_aliases(
    candidate: str,
    column_aliases: dict[str, list[str]] | None = None,
) -> list[str]:
    aliases = column_aliases or {}
    normalized_candidate = normalize_column_name(candidate)
    resolved = [normalized_candidate]
    resolved.extend(normalize_column_name(alias) for alias in aliases.get(normalized_candidate, []))
    return list(dict.fromkeys(resolved))


def find_missing_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    column_aliases: dict[str, list[str]] | None = None,
) -> list[str]:
    normalized_map = build_normalized_column_map(df)
    missing_columns: list[str] = []
    for column in required_columns:
        candidate_names = _resolve_candidate_aliases(column, column_aliases)
        if not any(candidate_name in normalized_map for candidate_name in candidate_names):
            missing_columns.append(column)
    return missing_columns


def has_any_non_empty_value(
    df: pd.DataFrame,
    candidate_columns: list[str],
    column_aliases: dict[str, list[str]] | None = None,
) -> bool:
    normalized_map = build_normalized_column_map(df)
    for candidate in candidate_columns:
        for candidate_name in _resolve_candidate_aliases(candidate, column_aliases):
            original = normalized_map.get(candidate_name)
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
