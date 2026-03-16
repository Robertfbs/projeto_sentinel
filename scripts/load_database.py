import logging
import sqlite3

import pandas as pd


def upsert_sqlite(
    df: pd.DataFrame,
    table_name: str,
    primary_key: str,
    conn: sqlite3.Connection,
) -> None:
    """Realiza o UPSERT (UPDATE ou INSERT) dinamico via Pandas e SQLite."""
    if df.empty:
        return

    temp_table = f"temp_{table_name}"
    df.to_sql(temp_table, conn, if_exists="replace", index=False)

    columns = ", ".join(df.columns)
    colunas_update = [column for column in df.columns if column != primary_key]

    if colunas_update:
        set_clause = ", ".join([f"{column}=EXCLUDED.{column}" for column in colunas_update])
        conflict_action = f"DO UPDATE SET {set_clause}"
    else:
        conflict_action = "DO NOTHING"

    upsert_query = f"""
        INSERT INTO {table_name} ({columns})
        SELECT {columns} FROM {temp_table}
        WHERE true
        ON CONFLICT({primary_key}) {conflict_action};
    """

    cursor = conn.cursor()
    cursor.execute(upsert_query)
    cursor.execute(f"DROP TABLE {temp_table}")
    conn.commit()

    logging.info(
        "UPSERT concluido na tabela '%s': %s registros processados.",
        table_name,
        len(df),
    )
