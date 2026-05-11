import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

import pandas as pd

from db_utils import assert_identifier, assert_table


def upsert_sqlite(
    df: pd.DataFrame,
    table_name: str,
    primary_key: str,
    conn: sqlite3.Connection,
) -> None:
    """Realiza UPSERT (UPDATE ou INSERT) dinamico via Pandas e SQLite.

    O SQLite nao parametriza identificadores; tabela, PK e colunas sao
    interpolados via f-string. Para fechar o vetor de SQL injection, todos
    os nomes passam pela allowlist (`assert_table`) e regex de identificador
    (`assert_identifier`) antes da interpolacao.
    """
    if df.empty:
        return

    safe_table = assert_table(table_name)
    safe_pk = assert_identifier(primary_key)
    safe_columns = [assert_identifier(col) for col in df.columns]

    # Tabela temp privada da conexao (CREATE TEMP TABLE) com sufixo aleatorio
    # para evitar colisao em execucoes paralelas.
    temp_table = f"_tmp_{safe_table}_{uuid.uuid4().hex}"

    columns_sql = ", ".join(safe_columns)
    update_columns = [c for c in safe_columns if c != safe_pk]

    if update_columns:
        set_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_columns)
        conflict_action = f"DO UPDATE SET {set_clause}"
    else:
        conflict_action = "DO NOTHING"

    cursor = conn.cursor()
    try:
        # to_sql nao cria TEMP nativo; criamos manualmente e populamos via insert.
        df.to_sql(temp_table, conn, if_exists="replace", index=False)

        upsert_query = (
            f"INSERT INTO {safe_table} ({columns_sql}) "
            f"SELECT {columns_sql} FROM {temp_table} "
            f"ON CONFLICT({safe_pk}) {conflict_action}"
        )
        cursor.execute(upsert_query)
    finally:
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")

    # Commit deixa de ser responsabilidade desta funcao quando a conexao
    # esta dentro de uma transacao maior. O caller decide.
    if not conn.in_transaction:
        conn.commit()

    logging.info(
        "UPSERT concluido na tabela '%s': %s registros processados.",
        safe_table,
        len(df),
    )


TICKET_HISTORY_COLUMNS = [
    "ticket_id",
    "case_id",
    "matricula",
    "numero_os",
    "status",
    "atribuido",
    "titulo",
    "assunto",
    "tipo_solicitacao",
    "tipo_manifestacao",
    "resultado_tratativa",
    "grupo_tickets",
    "flag_arquivado_relatorio",
    "ticket_notificacao_id",
    "status_vinculo",
    "data_criacao",
    "data_resolucao",
]


def _serialize_value(value: object) -> str | None:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_row_hash(row: pd.Series) -> str:
    payload = {column: _serialize_value(row.get(column)) for column in TICKET_HISTORY_COLUMNS}
    return _hash_payload(payload)


def _build_payload_json(row: pd.Series) -> str:
    payload = {column: _serialize_value(row.get(column)) for column in row.index.tolist()}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def persist_ticket_history(
    df_tickets: pd.DataFrame,
    conn: sqlite3.Connection,
    run_id: str,
    effective_at: str | None = None,
) -> list[int]:
    if df_tickets.empty:
        return []

    effective_timestamp = effective_at or _utc_timestamp()
    current = df_tickets.copy()
    for column in TICKET_HISTORY_COLUMNS:
        if column not in current.columns:
            current[column] = None
    current["hash_dados"] = current.apply(_build_row_hash, axis=1)
    current["payload_json"] = current.apply(_build_payload_json, axis=1)

    ticket_ids = current["ticket_id"].dropna().astype(int).tolist()
    placeholders = ",".join("?" for _ in ticket_ids)
    existing_query = f"""
        SELECT ticket_hist_id, ticket_id, hash_dados
        FROM tickets_historico
        WHERE flag_ativo = 1
          AND ticket_id IN ({placeholders})
    """
    existing_rows = pd.read_sql_query(existing_query, conn, params=ticket_ids) if ticket_ids else pd.DataFrame()
    existing_map = {
        int(row["ticket_id"]): {
            "ticket_hist_id": int(row["ticket_hist_id"]),
            "hash_dados": row["hash_dados"],
        }
        for _, row in existing_rows.iterrows()
    }

    rows_to_close: list[int] = []
    rows_to_insert: list[tuple] = []
    changed_ticket_ids: list[int] = []

    for _, row in current.iterrows():
        ticket_id = int(row["ticket_id"])
        existing = existing_map.get(ticket_id)
        if existing and existing["hash_dados"] == row["hash_dados"]:
            continue

        if existing:
            rows_to_close.append(existing["ticket_hist_id"])

        changed_ticket_ids.append(ticket_id)
        rows_to_insert.append(
            (
                ticket_id,
                row.get("case_id"),
                row.get("matricula"),
                row.get("numero_os"),
                row.get("status"),
                row.get("atribuido"),
                row.get("titulo"),
                row.get("assunto"),
                row.get("tipo_solicitacao"),
                row.get("tipo_manifestacao"),
                row.get("resultado_tratativa"),
                row.get("grupo_tickets"),
                row.get("flag_arquivado_relatorio"),
                row.get("ticket_notificacao_id"),
                row.get("status_vinculo"),
                _serialize_value(row.get("data_criacao")),
                _serialize_value(row.get("data_resolucao")),
                effective_timestamp,
                None,
                1,
                run_id,
                row["hash_dados"],
                row["payload_json"],
            )
        )

    cursor = conn.cursor()
    if rows_to_close:
        close_placeholders = ",".join("?" for _ in rows_to_close)
        cursor.execute(
            f"""
            UPDATE tickets_historico
            SET flag_ativo = 0,
                data_fim_vigencia = ?
            WHERE ticket_hist_id IN ({close_placeholders})
            """,
            (effective_timestamp, *rows_to_close),
        )

    if rows_to_insert:
        cursor.executemany(
            """
            INSERT INTO tickets_historico (
                ticket_id, case_id, matricula, numero_os, status, atribuido, titulo, assunto,
                tipo_solicitacao, tipo_manifestacao, resultado_tratativa, grupo_tickets,
                flag_arquivado_relatorio, ticket_notificacao_id, status_vinculo,
                data_criacao, data_resolucao, data_inicio_vigencia, data_fim_vigencia,
                flag_ativo, run_id, hash_dados, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )

    if not conn.in_transaction:
        conn.commit()
    logging.info(
        "Historico de tickets atualizado: %s novo(s) snapshot(s) versionado(s).",
        len(rows_to_insert),
    )
    return changed_ticket_ids


def sync_current_ticket_version_metadata(
    ticket_ids: list[int],
    changed_ticket_ids: list[int],
    conn: sqlite3.Connection,
    effective_at: str | None = None,
) -> None:
    if not ticket_ids:
        return

    effective_timestamp = effective_at or _utc_timestamp()
    cursor = conn.cursor()

    if changed_ticket_ids:
        changed_placeholders = ",".join("?" for _ in changed_ticket_ids)
        cursor.execute(
            f"""
            UPDATE tickets
            SET data_inicio_vigencia = ?,
                data_fim_vigencia = NULL,
                flag_ativo = 1
            WHERE ticket_id IN ({changed_placeholders})
            """,
            (effective_timestamp, *changed_ticket_ids),
        )

    all_placeholders = ",".join("?" for _ in ticket_ids)
    cursor.execute(
        f"""
        UPDATE tickets
        SET data_inicio_vigencia = COALESCE(data_inicio_vigencia, ?),
            data_fim_vigencia = NULL,
            flag_ativo = 1
        WHERE ticket_id IN ({all_placeholders})
        """,
        (effective_timestamp, *ticket_ids),
    )
    if not conn.in_transaction:
        conn.commit()
