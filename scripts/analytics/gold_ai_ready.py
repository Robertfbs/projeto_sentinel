from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from ._db import connect as _connect_db


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs" / "ai_ready"


GOLD_AI_READY_QUERY = """
SELECT
    ticket_id,
    case_id,
    matricula,
    bloco,
    data_criacao,
    data_resolucao,
    status,
    atribuido,
    titulo,
    assunto,
    canal_semantico,
    tipo_manifestacao,
    resultado_tratativa,
    classificacao_solicitacoes,
    classificacao_notificacoes,
    grupo_tickets,
    municipio,
    bairro,
    endereco,
    flag_auditoria_classificacao
FROM gold_ai_ready
"""


def _normalize_ai_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    text_columns = [
        "titulo",
        "assunto",
        "canal_semantico",
        "tipo_manifestacao",
        "resultado_tratativa",
        "classificacao_solicitacoes",
        "classificacao_notificacoes",
        "grupo_tickets",
        "municipio",
        "bairro",
        "endereco",
    ]
    for column in text_columns:
        if column in prepared.columns:
            prepared[column] = (
                prepared[column]
                .fillna("")
                .astype(str)
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
            )
    return prepared


def generate_gold_ai_ready(
    db_path: Path | None = None,
    reference_date: date | None = None,
    output_dir: Path | None = None,
) -> Path:
    active_db_path = db_path or DEFAULT_DB_PATH
    active_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    active_output_dir.mkdir(parents=True, exist_ok=True)

    with _connect_db(active_db_path, read_only=True) as conn:
        df_ai_ready = pd.read_sql_query(GOLD_AI_READY_QUERY, conn)

    df_ai_ready = _normalize_ai_text_columns(df_ai_ready)
    suffix = (reference_date or datetime.now().date()).strftime("%Y%m%d")
    output_path = active_output_dir / f"gold_ai_ready_{suffix}.xlsx"
    df_ai_ready.to_excel(output_path, index=False)
    return output_path


if __name__ == "__main__":
    generate_gold_ai_ready()
