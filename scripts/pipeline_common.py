import re
import unicodedata

import pandas as pd


def normalize_column_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized


def normalize_text(value: object) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text or None


def normalize_identifier(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    return normalized.replace(".0", "")


def derive_bloco(matricula: object) -> str | None:
    normalized = normalize_identifier(matricula)
    if not normalized:
        return None
    if normalized.startswith("40"):
        return "Bloco 4"
    if normalized.startswith("10"):
        return "Bloco 1"
    return None


def normalize_subject(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    normalized = re.sub(r"[^A-Z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def normalize_token_set(value: object) -> set[str]:
    normalized = normalize_subject(value)
    if normalized is None:
        return set()
    return {token for token in normalized.split() if len(token) > 2}


def first_not_null(row: pd.Series, columns: list[str]) -> str | None:
    for column in columns:
        value = row.get(column)
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return None


def serialize_datetime(value: object) -> str | None:
    if pd.isna(value):
        return None

    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None

    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def ensure_columns(df: pd.DataFrame, required_columns: list[str]) -> pd.DataFrame:
    prepared = df.copy()
    for column in required_columns:
        if column not in prepared.columns:
            prepared[column] = None
    return prepared


def deduplicate_latest(
    df: pd.DataFrame,
    subset: list[str],
    sort_columns: list[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    prepared = df.copy()
    existing_sort_columns = [column for column in (sort_columns or []) if column in prepared.columns]
    if existing_sort_columns:
        prepared = prepared.sort_values(existing_sort_columns, kind="stable")
    return prepared.drop_duplicates(subset=subset, keep="last").copy()
