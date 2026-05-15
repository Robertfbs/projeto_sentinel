from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tomllib
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "mcp_server" / "config" / "sentinel_mcp.toml"
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

mcp = FastMCP(
    "sentinel-mcp",
    instructions=(
        "Servidor MCP do Projeto Sentinel. Use somente as tools registradas, "
        "sem SQL livre, e trate a Gold SQLite como fonte oficial."
    ),
    json_response=True,
)


def _resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def load_config() -> dict[str, Any]:
    config_path = _resolve_project_path(os.getenv("SENTINEL_MCP_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        raise FileNotFoundError(f"Config MCP nao encontrada: {config_path}")

    with config_path.open("rb") as file:
        config = tomllib.load(file)

    config["_config_path"] = str(config_path)
    return config


def get_gold_db_path(config: dict[str, Any] | None = None) -> Path:
    active_config = config or load_config()
    relative_db_path = active_config.get("project", {}).get("gold_database", "03_database/pre_contencioso.db")
    db_path = _resolve_project_path(relative_db_path)

    expected_parent = (PROJECT_ROOT / "03_database").resolve()
    if db_path.parent != expected_parent or db_path.name != "pre_contencioso.db":
        raise ValueError(f"Banco Gold invalido para o Sentinel MCP: {db_path}")

    return db_path


def open_gold_read_only(db_path: Path | None = None) -> sqlite3.Connection:
    target = (db_path or get_gold_db_path()).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Banco Gold nao encontrado: {target}")

    uri = f"{target.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _audit_event(tool_name: str, status: str, details: dict[str, Any] | None = None) -> None:
    config = load_config()
    audit_log = _resolve_project_path(config.get("logging", {}).get("audit_log", "mcp_server/logs/mcp_audit.jsonl"))
    audit_log.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool_name,
        "status": status,
        "details": details or {},
    }
    with audit_log.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def _validate_sqlite_identifier(name: str) -> str:
    if not isinstance(name, str) or not SAFE_IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Nome de objeto SQLite invalido: {name!r}")
    return name


def _quote_identifier(name: str) -> str:
    safe_name = _validate_sqlite_identifier(name)
    return f'"{safe_name}"'


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _parse_iso_date(value: str | None, field_name: str) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} invalida: {value!r}. Use YYYY-MM-DD.") from exc


def _default_complete_period(reference_date: str | None = None, days: int = 7) -> tuple[date, date]:
    ref = _parse_iso_date(reference_date, "reference_date") or date.today()
    end_date = ref - timedelta(days=1)
    start_date = end_date - timedelta(days=max(1, int(days)) - 1)
    return start_date, end_date


def _resolve_period(
    start_date: str | None = None,
    end_date: str | None = None,
    reference_date: str | None = None,
    default_days: int = 7,
) -> tuple[date, date]:
    parsed_start = _parse_iso_date(start_date, "start_date")
    parsed_end = _parse_iso_date(end_date, "end_date")

    if parsed_start is None and parsed_end is None:
        parsed_start, parsed_end = _default_complete_period(reference_date, default_days)
    elif parsed_start is None or parsed_end is None:
        raise ValueError("Informe start_date e end_date juntos, ou deixe ambos vazios.")

    if parsed_start > parsed_end:
        raise ValueError("start_date nao pode ser maior que end_date.")
    return parsed_start, parsed_end


def _previous_business_week(reference_date: str | None = None) -> tuple[date, date]:
    ref = _parse_iso_date(reference_date, "reference_date") or date.today()
    current_week_monday = ref - timedelta(days=ref.weekday())
    week_start = current_week_monday - timedelta(days=7)
    week_end = week_start + timedelta(days=4)
    return week_start, week_end


def _iso_period_payload(start: date, end: date) -> dict[str, str]:
    return {"start_date": start.isoformat(), "end_date": end.isoformat()}


def _normalize_hierarchical_value(value: Any) -> str:
    if value is None:
        return "NAO INFORMADO"
    text = str(value).strip()
    if not text:
        return "NAO INFORMADO"
    if "::" in text:
        normalized = text.split("::")[-1].strip()
        return normalized or text
    return text


def _safe_limit(limit: int | None, config: dict[str, Any] | None = None) -> int:
    active_config = config or load_config()
    max_limit = int(active_config.get("security", {}).get("max_list_limit", 200))
    requested = 50 if limit is None else int(limit)
    return max(1, min(requested, max_limit))


def _official_ticket_filter(date_expression: str) -> str:
    return f"""
        {date_expression} IS NOT NULL
        AND COALESCE(flag_arquivado_relatorio, 0) = 0
        AND UPPER(TRIM(COALESCE(tipo_manifestacao, ''))) <> 'ANEXO'
        AND UPPER(TRIM(COALESCE(tipo_solicitacao, ''))) <> 'INFORMATIVO::ANEXO'
        AND (
            formulario_ticket IS NULL
            OR UPPER(TRIM(COALESCE(formulario_ticket, ''))) LIKE 'SOLICIT%'
        )
    """


def _read_text_file(relative_path: str, max_chars: int = 30000) -> str:
    path = _resolve_project_path(relative_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[Conteudo truncado pelo MCP para preservar contexto.]"
    return text


def _latest_outputs(limit: int = 25) -> list[dict[str, Any]]:
    output_dir = PROJECT_ROOT / "outputs"
    if not output_dir.exists():
        return []
    files = [
        {
            "name": path.name,
            "relative_path": str(path.relative_to(PROJECT_ROOT)),
            "size_bytes": path.stat().st_size,
            "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        }
        for path in output_dir.rglob("*")
        if path.is_file()
    ]
    return sorted(files, key=lambda item: item["last_modified"], reverse=True)[:limit]


def _confirmed(tool_name: str, confirmacao: bool) -> None:
    if not confirmacao:
        _audit_event(tool_name, "blocked", {"reason": "confirmacao ausente"})
        raise PermissionError(f"A tool {tool_name} exige confirmacao=True para executar escrita em outputs.")


def _get_gold_object(connection: sqlite3.Connection, object_name: str) -> dict[str, str]:
    safe_name = _validate_sqlite_identifier(object_name)
    row = connection.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name = ?
          AND name NOT LIKE 'sqlite_%'
        """,
        (safe_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Objeto nao encontrado na Gold: {object_name!r}")
    return {"name": str(row["name"]), "type": str(row["type"])}


@mcp.tool(name="sentinel.health")
def sentinel_health() -> dict[str, Any]:
    """Verifica se o servidor MCP encontra a Gold oficial do Sentinel."""
    config = load_config()
    db_path = get_gold_db_path(config)
    db_found = db_path.exists()

    table_count = 0
    view_count = 0
    if db_found:
        with closing(open_gold_read_only(db_path)) as connection:
            rows = connection.execute(
                """
                SELECT type, COUNT(*) AS qtd
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                GROUP BY type
                """
            ).fetchall()
        counts = {str(row["type"]): int(row["qtd"]) for row in rows}
        table_count = counts.get("table", 0)
        view_count = counts.get("view", 0)

    payload = {
        "status": "ok" if db_found else "error",
        "project": config.get("project", {}).get("name", "Projeto Sentinel"),
        "project_root": str(PROJECT_ROOT),
        "config_path": config["_config_path"],
        "gold_database_found": db_found,
        "gold_database_path": str(db_path),
        "gold_database_size_mb": round(db_path.stat().st_size / (1024 * 1024), 2) if db_found else None,
        "gold_tables": table_count,
        "gold_views": view_count,
        "mode": "read_only",
    }
    _audit_event("sentinel.health", payload["status"], {"gold_database_found": db_found})
    return payload


@mcp.tool(name="gold.list_tables")
def gold_list_tables() -> dict[str, Any]:
    """Lista tabelas e views disponiveis na Gold oficial."""
    db_path = get_gold_db_path()
    with closing(open_gold_read_only(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()

    tables = [str(row["name"]) for row in rows if row["type"] == "table"]
    views = [str(row["name"]) for row in rows if row["type"] == "view"]
    payload = {"database": str(db_path), "tables": tables, "views": views}
    _audit_event("gold.list_tables", "ok", {"tables": len(tables), "views": len(views)})
    return payload


@mcp.tool(name="gold.describe_table")
def gold_describe_table(object_name: str, include_row_count: bool = True) -> dict[str, Any]:
    """Descreve colunas de uma tabela ou view permitida da Gold."""
    db_path = get_gold_db_path()
    with closing(open_gold_read_only(db_path)) as connection:
        gold_object = _get_gold_object(connection, object_name)
        quoted_name = _quote_identifier(gold_object["name"])
        column_rows = connection.execute(f"PRAGMA table_info({quoted_name})").fetchall()

        row_count: int | None = None
        if include_row_count:
            row_count = int(connection.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0])

    columns = [
        {
            "cid": int(row["cid"]),
            "name": str(row["name"]),
            "type": str(row["type"]),
            "not_null": bool(row["notnull"]),
            "default_value": row["dflt_value"],
            "primary_key": bool(row["pk"]),
        }
        for row in column_rows
    ]
    payload = {
        "database": str(db_path),
        "object": gold_object,
        "row_count": row_count,
        "columns": columns,
    }
    _audit_event("gold.describe_table", "ok", {"object_name": object_name, "include_row_count": include_row_count})
    return payload


@mcp.tool(name="analytics.weekly_productivity")
def analytics_weekly_productivity(reference_date: str | None = None) -> dict[str, Any]:
    """Resume produtividade da semana util anterior a partir da Gold."""
    week_start, week_end = _previous_business_week(reference_date)
    params = {"start_date": week_start.isoformat(), "end_date": week_end.isoformat()}
    official_filter = _official_ticket_filter("date(data_resolucao)")

    with closing(open_gold_read_only()) as connection:
        total = int(
            connection.execute(
                f"""
                SELECT COUNT(DISTINCT ticket_id)
                FROM tickets
                WHERE {official_filter}
                  AND date(data_resolucao) BETWEEN :start_date AND :end_date
                """,
                params,
            ).fetchone()[0]
        )
        by_collaborator = _rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(atribuido), ''), 'NAO ATRIBUIDO') AS colaborador,
                    COUNT(DISTINCT ticket_id) AS tickets_resolvidos
                FROM tickets
                WHERE {official_filter}
                  AND date(data_resolucao) BETWEEN :start_date AND :end_date
                GROUP BY colaborador
                ORDER BY tickets_resolvidos DESC, colaborador ASC
                """,
                params,
            ).fetchall()
        )
        by_day = _rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                    date(data_resolucao) AS data_resolucao,
                    COUNT(DISTINCT ticket_id) AS tickets_resolvidos
                FROM tickets
                WHERE {official_filter}
                  AND date(data_resolucao) BETWEEN :start_date AND :end_date
                GROUP BY date(data_resolucao)
                ORDER BY date(data_resolucao) ASC
                """,
                params,
            ).fetchall()
        )
        channel_rows = _rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(tipo_solicitacao), ''), 'NAO INFORMADO') AS canal_raw,
                    COUNT(DISTINCT ticket_id) AS tickets_resolvidos
                FROM tickets
                WHERE {official_filter}
                  AND date(data_resolucao) BETWEEN :start_date AND :end_date
                GROUP BY canal_raw
                ORDER BY tickets_resolvidos DESC, canal_raw ASC
                """,
                params,
            ).fetchall()
        )

    by_channel: dict[str, int] = {}
    for row in channel_rows:
        channel = _normalize_hierarchical_value(row["canal_raw"])
        by_channel[channel] = by_channel.get(channel, 0) + int(row["tickets_resolvidos"])

    payload = {
        "period": _iso_period_payload(week_start, week_end),
        "metric": "tickets_resolvidos",
        "total": total,
        "by_collaborator": by_collaborator,
        "by_day": by_day,
        "by_channel": [
            {"canal": canal, "tickets_resolvidos": value}
            for canal, value in sorted(by_channel.items(), key=lambda item: (-item[1], item[0]))
        ],
        "filters": [
            "Gold oficial",
            "flag_arquivado_relatorio = 0",
            "tipo_manifestacao <> ANEXO",
            "tipo_solicitacao <> Informativo::Anexo",
            "formulario_ticket nulo ou SOLICIT%",
        ],
    }
    _audit_event("analytics.weekly_productivity", "ok", {"period": payload["period"], "total": total})
    return payload


@mcp.tool(name="analytics.channel_volume")
def analytics_channel_volume(
    start_date: str | None = None,
    end_date: str | None = None,
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Resume volumetria de entrada por canal no periodo informado."""
    period_start, period_end = _resolve_period(start_date, end_date, reference_date)
    params = {"start_date": period_start.isoformat(), "end_date": period_end.isoformat()}
    date_expression = "date(COALESCE(data_entrada_reclamacao, data_criacao))"
    official_filter = _official_ticket_filter(date_expression)

    with closing(open_gold_read_only()) as connection:
        rows = _rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(tipo_solicitacao), ''), 'NAO INFORMADO') AS canal_raw,
                    COUNT(DISTINCT ticket_id) AS qtde_tickets
                FROM tickets
                WHERE {official_filter}
                  AND {date_expression} BETWEEN :start_date AND :end_date
                GROUP BY canal_raw
                ORDER BY qtde_tickets DESC, canal_raw ASC
                """,
                params,
            ).fetchall()
        )

    by_channel: dict[str, int] = {}
    for row in rows:
        channel = _normalize_hierarchical_value(row["canal_raw"])
        by_channel[channel] = by_channel.get(channel, 0) + int(row["qtde_tickets"])

    volumes = [
        {"canal": canal, "qtde_tickets": value}
        for canal, value in sorted(by_channel.items(), key=lambda item: (-item[1], item[0]))
    ]
    payload = {
        "period": _iso_period_payload(period_start, period_end),
        "metric": "tickets_entrada",
        "total": sum(item["qtde_tickets"] for item in volumes),
        "by_channel": volumes,
    }
    _audit_event("analytics.channel_volume", "ok", {"period": payload["period"], "total": payload["total"]})
    return payload


@mcp.tool(name="tickets.processed")
def tickets_processed(
    start_date: str | None = None,
    end_date: str | None = None,
    reference_date: str | None = None,
    date_field: str = "data_resolucao",
    limit: int = 50,
) -> dict[str, Any]:
    """Lista tickets processados na Gold com campos nao sensiveis."""
    allowed_date_fields = {
        "data_resolucao": "date(data_resolucao)",
        "data_criacao": "date(data_criacao)",
        "data_entrada": "date(COALESCE(data_entrada_reclamacao, data_criacao))",
    }
    if date_field not in allowed_date_fields:
        raise ValueError(f"date_field invalido: {date_field!r}. Use {sorted(allowed_date_fields)}.")

    period_start, period_end = _resolve_period(start_date, end_date, reference_date)
    safe_limit = _safe_limit(limit)
    date_expression = allowed_date_fields[date_field]
    params = {
        "start_date": period_start.isoformat(),
        "end_date": period_end.isoformat(),
        "limit": safe_limit,
    }
    official_filter = _official_ticket_filter(date_expression)

    with closing(open_gold_read_only()) as connection:
        total = int(
            connection.execute(
                f"""
                SELECT COUNT(DISTINCT ticket_id)
                FROM tickets
                WHERE {official_filter}
                  AND {date_expression} BETWEEN :start_date AND :end_date
                """,
                params,
            ).fetchone()[0]
        )
        rows = _rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                    ticket_id,
                    date(data_criacao) AS data_criacao,
                    date(data_resolucao) AS data_resolucao,
                    status,
                    COALESCE(NULLIF(TRIM(atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
                    COALESCE(NULLIF(TRIM(tipo_solicitacao), ''), 'NAO INFORMADO') AS tipo_solicitacao,
                    tipo_manifestacao,
                    classificacao_solicitacoes,
                    formulario_ticket
                FROM tickets
                WHERE {official_filter}
                  AND {date_expression} BETWEEN :start_date AND :end_date
                ORDER BY {date_expression} DESC, ticket_id DESC
                LIMIT :limit
                """,
                params,
            ).fetchall()
        )

    for row in rows:
        row["canal_normalizado"] = _normalize_hierarchical_value(row.pop("tipo_solicitacao"))

    payload = {
        "period": _iso_period_payload(period_start, period_end),
        "date_field": date_field,
        "total_matching_tickets": total,
        "returned": len(rows),
        "limit": safe_limit,
        "tickets": rows,
        "pii_policy": "Campos pessoais como CPF, telefone, e-mail e nome do solicitante nao sao retornados.",
    }
    _audit_event("tickets.processed", "ok", {"period": payload["period"], "returned": len(rows), "total": total})
    return payload


@mcp.tool(name="etl.last_run")
def etl_last_run(log_limit: int = 20) -> dict[str, Any]:
    """Retorna a ultima execucao registrada do ETL e seus logs principais."""
    safe_limit = _safe_limit(log_limit)
    with closing(open_gold_read_only()) as connection:
        run = connection.execute(
            """
            SELECT *
            FROM etl_runs
            ORDER BY COALESCE(data_inicio, data_execucao) DESC, data_execucao DESC
            LIMIT 1
            """
        ).fetchone()
        if run is None:
            payload = {"latest_run": None, "logs": []}
            _audit_event("etl.last_run", "ok", {"found": False})
            return payload

        latest_run = dict(run)
        logs = _rows_to_dicts(
            connection.execute(
                """
                SELECT timestamp_log, nivel, etapa, status, volume_processado, tempo_etapa, erro
                FROM etl_logs
                WHERE run_id = ?
                ORDER BY timestamp_log ASC
                LIMIT ?
                """,
                (latest_run["run_id"], safe_limit),
            ).fetchall()
        )

    payload = {"latest_run": latest_run, "logs": logs, "log_limit": safe_limit}
    _audit_event("etl.last_run", "ok", {"run_id": latest_run.get("run_id"), "logs": len(logs)})
    return payload


@mcp.tool(name="reports.generate_weekly_productivity")
def reports_generate_weekly_productivity(confirmacao: bool = False, reference_date: str | None = None) -> dict[str, Any]:
    """Gera o relatorio oficial de produtividade semanal em outputs, com confirmacao."""
    tool_name = "reports.generate_weekly_productivity"
    _confirmed(tool_name, confirmacao)

    from analytics.produtividade_semanal import generate_produtividade_semanal_report

    ref_date = _parse_iso_date(reference_date, "reference_date")
    output_path = generate_produtividade_semanal_report(get_gold_db_path(), ref_date)
    payload = {
        "status": "ok",
        "output_path": str(output_path),
        "size_bytes": output_path.stat().st_size if output_path.exists() else None,
    }
    _audit_event(tool_name, "ok", payload)
    return payload


@mcp.tool(name="reports.generate_executive")
def reports_generate_executive(
    confirmacao: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Gera relatorio executivo oficial em outputs, com confirmacao."""
    tool_name = "reports.generate_executive"
    _confirmed(tool_name, confirmacao)

    from analytics.relatorio_executivo import load_reports, sort_report_frames, validate_period, write_report_to_excel

    period_start, period_end = _resolve_period(start_date, end_date, reference_date)
    validate_period(period_start, period_end)
    with closing(open_gold_read_only(get_gold_db_path())) as connection:
        reports = load_reports(connection, period_start, period_end)
    output_path = write_report_to_excel(sort_report_frames(reports), period_start, period_end)
    payload = {
        "status": "ok",
        "period": _iso_period_payload(period_start, period_end),
        "output_path": str(output_path),
        "size_bytes": output_path.stat().st_size if output_path.exists() else None,
    }
    _audit_event(tool_name, "ok", payload)
    return payload


@mcp.tool(name="powerbi.export_semantic_model")
def powerbi_export_semantic_model(confirmacao: bool = False) -> dict[str, Any]:
    """Gera export semantico para Power BI em outputs/semantic, com confirmacao."""
    tool_name = "powerbi.export_semantic_model"
    _confirmed(tool_name, confirmacao)

    from analytics.powerbi_semantic_exports import generate_powerbi_semantic_exports

    exported_files = generate_powerbi_semantic_exports(get_gold_db_path(), PROJECT_ROOT / "outputs" / "semantic")
    payload = {
        "status": "ok",
        "files": {
            name: {
                "path": str(path),
                "size_bytes": path.stat().st_size if path.exists() else None,
            }
            for name, path in exported_files.items()
        },
    }
    _audit_event(tool_name, "ok", {"files": list(payload["files"])})
    return payload


@mcp.tool(name="integrations.teams.prepare_message")
def integrations_teams_prepare_message(
    destination: str,
    purpose: str,
    content: str,
    urgency: str = "normal",
) -> dict[str, Any]:
    """Prepara rascunho de mensagem Teams; nao envia."""
    message = f"""Destino: {destination}
Urgencia: {urgency}

{purpose}

{content}
"""
    payload = {
        "mode": "draft_only",
        "channel": "teams",
        "destination": destination,
        "message": message.strip(),
        "requires_human_review": True,
        "sent": False,
    }
    _audit_event("integrations.teams.prepare_message", "draft", {"destination": destination, "urgency": urgency})
    return payload


@mcp.tool(name="integrations.outlook.prepare_email")
def integrations_outlook_prepare_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> dict[str, Any]:
    """Prepara rascunho de e-mail Outlook; nao envia."""
    payload = {
        "mode": "draft_only",
        "channel": "outlook",
        "to": to,
        "cc": cc,
        "subject": subject,
        "body": body,
        "requires_human_review": True,
        "sent": False,
    }
    _audit_event("integrations.outlook.prepare_email", "draft", {"to": to, "cc": cc})
    return payload


@mcp.tool(name="integrations.planner.prepare_task")
def integrations_planner_prepare_task(
    title: str,
    description: str,
    owner: str | None = None,
    due_date: str | None = None,
    bucket: str = "A definir",
) -> dict[str, Any]:
    """Prepara rascunho de tarefa Planner; nao cria tarefa."""
    parsed_due_date = _parse_iso_date(due_date, "due_date") if due_date else None
    payload = {
        "mode": "draft_only",
        "channel": "planner",
        "title": title,
        "description": description,
        "owner": owner,
        "due_date": parsed_due_date.isoformat() if parsed_due_date else None,
        "bucket": bucket,
        "requires_human_review": True,
        "created": False,
    }
    _audit_event("integrations.planner.prepare_task", "draft", {"owner": owner, "due_date": payload["due_date"]})
    return payload


@mcp.resource("sentinel://project/readme", mime_type="text/markdown")
def resource_project_readme() -> str:
    """README principal do Projeto Sentinel."""
    return _read_text_file("README.md")


@mcp.resource("sentinel://project/prd", mime_type="text/markdown")
def resource_project_prd() -> str:
    """PRD vigente do Projeto Sentinel."""
    return _read_text_file("prd.md")


@mcp.resource("sentinel://project/techspec", mime_type="text/markdown")
def resource_project_techspec() -> str:
    """TechSpec vigente do Projeto Sentinel."""
    return _read_text_file("techspec.md")


@mcp.resource("sentinel://schema/gold", mime_type="application/json")
def resource_gold_schema() -> str:
    """Schema resumido de tabelas e views da Gold."""
    schema: dict[str, Any] = {"database": str(get_gold_db_path()), "objects": []}
    with closing(open_gold_read_only()) as connection:
        objects = connection.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        for item in objects:
            quoted_name = _quote_identifier(str(item["name"]))
            columns = [
                {"name": str(row["name"]), "type": str(row["type"]), "primary_key": bool(row["pk"])}
                for row in connection.execute(f"PRAGMA table_info({quoted_name})").fetchall()
            ]
            schema["objects"].append({"name": str(item["name"]), "type": str(item["type"]), "columns": columns})
    return json.dumps(schema, ensure_ascii=False, indent=2)


@mcp.resource("sentinel://rules/catalog", mime_type="application/json")
def resource_rules_catalog() -> str:
    """Catalogo das regras operacionais dos agentes Sentinel."""
    rules_dir = PROJECT_ROOT / ".agents" / "rules"
    rules = []
    if rules_dir.exists():
        for path in sorted(rules_dir.glob("*.md")):
            rules.append(
                {
                    "name": path.stem,
                    "relative_path": str(path.relative_to(PROJECT_ROOT)),
                    "preview": path.read_text(encoding="utf-8", errors="replace")[:1200],
                }
            )
    return json.dumps({"rules": rules}, ensure_ascii=False, indent=2)


@mcp.resource("sentinel://outputs/catalog", mime_type="application/json")
def resource_outputs_catalog() -> str:
    """Catalogo dos outputs mais recentes do Sentinel."""
    return json.dumps({"outputs": _latest_outputs()}, ensure_ascii=False, indent=2)


@mcp.prompt(name="resumo_executivo_produtividade")
def prompt_resumo_executivo_produtividade(periodo: str, dados_json: str) -> str:
    return f"""Gere um resumo executivo de produtividade do Projeto Sentinel para {periodo}.

Use somente os dados JSON fornecidos abaixo.
Nao invente numeros, nao exponha PII e cite os filtros relevantes.
Estruture em: sintese, destaques por colaborador, canais relevantes e atencoes.

Dados:
{dados_json}
"""


@mcp.prompt(name="auditoria_tickets")
def prompt_auditoria_tickets(periodo: str, dados_json: str) -> str:
    return f"""Analise os tickets do Projeto Sentinel no periodo {periodo} sob perspectiva de auditoria.

Use apenas os dados fornecidos. Destaque inconsistencias, lacunas, excecoes e recomendacoes de validacao.
Nao proponha update direto no banco; quando houver recorrencia, recomende persistir regra no ETL.

Dados:
{dados_json}
"""


@mcp.prompt(name="relatorio_executivo_corporativo")
def prompt_relatorio_executivo_corporativo(contexto: str, dados_json: str) -> str:
    return f"""Prepare uma resposta corporativa executiva para o contexto: {contexto}.

Regras:
- seja objetivo e rastreavel;
- use somente os dados estruturados recebidos;
- cite periodo e fonte Gold quando aplicavel;
- se faltar dado, declare a limitacao.

Dados:
{dados_json}
"""


@mcp.prompt(name="rascunho_microsoft_teams")
def prompt_rascunho_microsoft_teams(destino: str, contexto: str, dados_json: str) -> str:
    return f"""Prepare um rascunho de mensagem para Microsoft Teams.

Destino: {destino}
Contexto: {contexto}

Use tom profissional, curto e acionavel. Nao afirme que a mensagem foi enviada.

Dados:
{dados_json}
"""


if __name__ == "__main__":
    mcp.run()
