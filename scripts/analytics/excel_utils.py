"""Utilitarios compartilhados para exportacao de relatorios em Excel.

Centraliza ``append_total_row`` e ``auto_fit_columns`` para eliminar a
triplicacao previa nos modulos de analytics. Cada funcao recebe parametros
explicitos que antes eram convencao implicita (ex.: prefixo `flag_` que
nao deve entrar no somatorio).
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


def append_total_row(
    dataframe: pd.DataFrame,
    *,
    exclude_columns: Iterable[str] = (),
    exclude_prefixes: Iterable[str] = ("flag_",),
) -> pd.DataFrame:
    """Adiciona linha 'TOTAL' somando colunas numericas relevantes.

    Colunas com prefixo ``flag_`` (ou outras listadas em ``exclude_columns``)
    sao ignoradas no somatorio: somar flags 0/1 produz valores sem semantica.
    """
    if dataframe.empty:
        return dataframe

    excluded = set(exclude_columns)
    prefixes = tuple(exclude_prefixes)

    def _is_summable(name: str) -> bool:
        if name in excluded:
            return False
        return not any(name.startswith(p) for p in prefixes)

    numeric_columns = [
        c for c in dataframe.select_dtypes(include=["number"]).columns if _is_summable(c)
    ]
    if len(dataframe) <= 1 or not numeric_columns:
        return dataframe

    total_row: dict[str, object] = {}
    label_written = False
    for column in dataframe.columns:
        if column in numeric_columns:
            total_row[column] = dataframe[column].sum()
        elif not label_written:
            total_row[column] = "TOTAL"
            label_written = True
        else:
            total_row[column] = ""

    return pd.concat([dataframe, pd.DataFrame([total_row])], ignore_index=True)


def auto_fit_columns(
    worksheet,
    dataframe: pd.DataFrame,
    *,
    date_columns: Iterable[str] = (),
    date_format=None,
    max_width: int = 42,
) -> None:
    """Ajusta a largura de cada coluna ao maior valor exibido (ate ``max_width``)."""
    date_set = set(date_columns)
    for column_index, column_name in enumerate(dataframe.columns):
        selected = dataframe.loc[:, column_name]
        if isinstance(selected, pd.DataFrame):
            flattened_values = selected.fillna("").astype(str).to_numpy().ravel().tolist()
        else:
            flattened_values = selected.fillna("").astype(str).tolist()
        max_value_length = max((len(str(value)) for value in flattened_values), default=0)
        width = min(max(len(str(column_name)), int(max_value_length)) + 2, max_width)
        column_format = date_format if column_name in date_set else None
        worksheet.set_column(column_index, column_index, width, column_format)
