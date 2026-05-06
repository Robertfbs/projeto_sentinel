import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "03_database" / "pre_contencioso.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_FILE_NAME = "produtividade_semanal.xlsx"
SKIP_TOTAL_ROW_SHEETS = {"DATA"}

VISIBLE_DATA_COLUMNS = [
    "ticket_id",
    "data_resolucao",
    "data_criacao",
    "atribuido",
    "canal_normalizado",
    "assunto_normalizado",
    "status",
    "tipo_manifestacao",
    "tipo_solicitacao",
    "titulo_ticket",
    "matricula",
    "numero_os",
    "resultado_tratativa",
    "classificacao_solicitacoes",
    "nome_solicitante",
    "email_solicitante",
]

HIDDEN_DATA_COLUMNS = [
    "dia_semana_numero",
    "dia_semana_nome",
    "periodo_inicio_semana",
    "periodo_fim_semana",
]

DATE_COLUMNS = {
    "data_resolucao",
    "data_criacao",
    "periodo_inicio_semana",
    "periodo_fim_semana",
    "data_referencia_semana",
}

DIA_SEMANA_LABELS = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
}

BASE_SQL = """
SELECT
    t.ticket_id,
    t.data_resolucao,
    t.data_criacao,
    COALESCE(NULLIF(TRIM(t.atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
    COALESCE(NULLIF(TRIM(t.tipo_solicitacao), ''), 'NAO INFORMADO') AS tipo_solicitacao,
    t.assunto,
    t.status,
    t.tipo_manifestacao,
    t.titulo AS titulo_ticket,
    t.matricula,
    t.numero_os,
    t.resultado_tratativa,
    t.classificacao_solicitacoes,
    t.nome_solicitante,
    t.email_solicitante,
    :week_start AS periodo_inicio_semana,
    :week_end AS periodo_fim_semana
FROM tickets AS t
WHERE
    date(t.data_resolucao) BETWEEN :week_start AND :week_end
    AND COALESCE(t.flag_arquivado_relatorio, 0) = 0
    AND UPPER(TRIM(COALESCE(t.tipo_manifestacao, ''))) <> 'ANEXO'
    AND (
        t.formulario_ticket IS NULL
        OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
    )
ORDER BY
    date(t.data_resolucao) ASC,
    COALESCE(NULLIF(TRIM(t.atribuido), ''), 'NAO ATRIBUIDO') ASC,
    t.ticket_id DESC
"""


def resolve_previous_business_week(reference_date: date | None = None) -> tuple[date, date]:
    today = reference_date or date.today()
    current_week_monday = today - timedelta(days=today.weekday())
    previous_week_monday = current_week_monday - timedelta(days=7)
    previous_week_friday = previous_week_monday + timedelta(days=4)
    return previous_week_monday, previous_week_friday


def normalize_hierarchical_value(value: object) -> object:
    if pd.isna(value):
        return value

    text = str(value).strip()
    if not text:
        return value

    if "::" not in text:
        return text

    normalized = text.split("::")[-1].strip()
    return normalized or text


def normalize_report_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    df = dataframe.copy()

    if "tipo_solicitacao" in df.columns and "canal_normalizado" not in df.columns:
        df["canal_normalizado"] = df["tipo_solicitacao"].apply(normalize_hierarchical_value)

    if "assunto" in df.columns and "assunto_normalizado" not in df.columns:
        df["assunto_normalizado"] = df["assunto"].apply(normalize_hierarchical_value)

    for column in DATE_COLUMNS:
        if column in df.columns:
            parsed = pd.to_datetime(df[column], errors="coerce")
            df[column] = parsed.dt.normalize().where(parsed.notna(), pd.NaT)

    if "data_resolucao" in df.columns and "ticket_id" in df.columns:
        resolved_dates = pd.to_datetime(df["data_resolucao"], errors="coerce")
        df["dia_semana_numero"] = resolved_dates.dt.weekday
        df["dia_semana_nome"] = df["dia_semana_numero"].map(DIA_SEMANA_LABELS)

    return df


def load_weekly_data(
    connection: sqlite3.Connection,
    reference_date: date | None = None,
) -> tuple[pd.DataFrame, date, date]:
    week_start, week_end = resolve_previous_business_week(reference_date)
    params = {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
    }
    df = pd.read_sql_query(BASE_SQL, connection, params=params)
    return normalize_report_dataframe(df), week_start, week_end


def build_report_frames(data_df: pd.DataFrame, week_start: date, week_end: date) -> dict[str, pd.DataFrame]:
    df = data_df.copy()
    if "ticket_id" not in df.columns:
        df["ticket_id"] = pd.Series(dtype="Int64")
    if "atribuido" not in df.columns:
        df["atribuido"] = pd.Series(dtype="object")
    if "canal_normalizado" not in df.columns:
        if "tipo_solicitacao" in df.columns:
            df["canal_normalizado"] = df["tipo_solicitacao"].apply(normalize_hierarchical_value)
        else:
            df["canal_normalizado"] = pd.Series(dtype="object")
    if "dia_semana_numero" not in df.columns:
        df["dia_semana_numero"] = pd.Series(dtype="Int64")

    resolvidos_total_semana = pd.DataFrame(
        [
            {
                "data_referencia_semana": week_start.strftime("%Y-%m-%d"),
                "periodo_inicio_semana": week_start.strftime("%Y-%m-%d"),
                "periodo_fim_semana": week_end.strftime("%Y-%m-%d"),
                "qtde_tickets_resolvidos": int(df["ticket_id"].nunique()),
            }
        ]
    )

    weekday_rows: list[dict[str, object]] = []
    for weekday_number in range(5):
        current_date = week_start + timedelta(days=weekday_number)
        qtd = int(df.loc[df["dia_semana_numero"] == weekday_number, "ticket_id"].nunique()) if not df.empty else 0
        weekday_rows.append(
            {
                "data_referencia_semana": week_start.strftime("%Y-%m-%d"),
                "data_resolucao": current_date.strftime("%Y-%m-%d"),
                "dia_semana": DIA_SEMANA_LABELS[weekday_number],
                "qtde_tickets_resolvidos": qtd,
            }
        )
    resolvidos_por_dia = pd.DataFrame(weekday_rows)
    resolvidos_por_dia = resolvidos_por_dia[
        [
            "data_referencia_semana",
            "data_resolucao",
            "dia_semana",
            "qtde_tickets_resolvidos",
        ]
    ]

    produtividade_colaborador = (
        df.groupby("atribuido", dropna=False)["ticket_id"]
        .nunique()
        .reset_index(name="qtde_tickets_resolvidos")
        .sort_values(["qtde_tickets_resolvidos", "atribuido"], ascending=[False, True], kind="stable")
    )

    resolvidos_por_canal = (
        df.groupby("canal_normalizado", dropna=False)["ticket_id"]
        .nunique()
        .reset_index(name="qtde_tickets_resolvidos")
        .sort_values(["qtde_tickets_resolvidos", "canal_normalizado"], ascending=[False, True], kind="stable")
    )

    ordered_data_columns = [column for column in VISIBLE_DATA_COLUMNS + HIDDEN_DATA_COLUMNS if column in df.columns]
    data_sheet = df[ordered_data_columns].copy()

    return {
        "DATA": data_sheet,
        "resolvidos_total_semana": normalize_report_dataframe(resolvidos_total_semana),
        "resolvidos_por_dia": normalize_report_dataframe(resolvidos_por_dia),
        "produtividade_colaborador": normalize_report_dataframe(produtividade_colaborador),
        "resolvidos_por_canal": normalize_report_dataframe(resolvidos_por_canal),
    }


def append_total_row(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    numeric_columns = dataframe.select_dtypes(include=["number"]).columns.tolist()
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


def auto_fit_columns(worksheet, dataframe: pd.DataFrame, date_format=None) -> None:
    for column_index, column_name in enumerate(dataframe.columns):
        column_values = dataframe[column_name].fillna("").astype(str)
        max_value_length = column_values.map(len).max() if not column_values.empty else 0
        width = min(max(len(str(column_name)), int(max_value_length)) + 2, 42)
        column_format = date_format if column_name in DATE_COLUMNS else None
        worksheet.set_column(column_index, column_index, width, column_format)


def write_report_excel(reports: dict[str, pd.DataFrame]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    primary_path = OUTPUT_DIR / OUTPUT_FILE_NAME
    fallback_path = OUTPUT_DIR / f"{primary_path.stem}_{datetime.now():%Y%m%d_%H%M%S}{primary_path.suffix}"
    last_error: Exception | None = None

    for output_path in [primary_path, fallback_path]:
        try:
            if output_path.exists():
                output_path.unlink()

            with pd.ExcelWriter(
                output_path,
                engine="xlsxwriter",
                date_format="dd/mm/yyyy",
                datetime_format="dd/mm/yyyy",
            ) as writer:
                workbook = writer.book
                header_format = workbook.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1})
                total_row_format = workbook.add_format({"bold": True, "top": 2})
                date_format = workbook.add_format({"num_format": "dd/mm/yyyy"})

                for sheet_name, dataframe in reports.items():
                    excel_sheet_name = sheet_name[:31]
                    df_to_export = dataframe.copy()

                    if sheet_name not in SKIP_TOTAL_ROW_SHEETS:
                        df_to_export = append_total_row(df_to_export)

                    if df_to_export.empty:
                        placeholder = pd.DataFrame([{"mensagem": "Sem dados para a semana de referencia calculada."}])
                        placeholder.to_excel(writer, sheet_name=excel_sheet_name, index=False)
                        worksheet = writer.sheets[excel_sheet_name]
                        for col_num, value in enumerate(placeholder.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        auto_fit_columns(worksheet, placeholder)
                        worksheet.freeze_panes(1, 0)
                        continue

                    df_to_export.to_excel(writer, sheet_name=excel_sheet_name, index=False)
                    worksheet = writer.sheets[excel_sheet_name]

                    for col_num, value in enumerate(df_to_export.columns.values):
                        worksheet.write(0, col_num, value, header_format)

                    auto_fit_columns(worksheet, df_to_export, date_format=date_format)
                    worksheet.freeze_panes(1, 0)

                    if sheet_name == "DATA":
                        table_columns = [{"header": column} for column in df_to_export.columns]
                        worksheet.add_table(
                            0,
                            0,
                            len(df_to_export),
                            len(df_to_export.columns) - 1,
                            {
                                "name": "tb_produtividade_semanal_data",
                                "style": "Table Style Medium 2",
                                "columns": table_columns,
                            },
                        )
                        for column_name in HIDDEN_DATA_COLUMNS:
                            if column_name in df_to_export.columns:
                                col_idx = df_to_export.columns.get_loc(column_name)
                                worksheet.set_column(col_idx, col_idx, None, None, {"hidden": True})
                    else:
                        worksheet.autofilter(0, 0, len(df_to_export), len(df_to_export.columns) - 1)
                        if len(df_to_export) > len(dataframe):
                            worksheet.set_row(len(df_to_export), None, total_row_format)

            return output_path
        except OSError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("Falha inesperada ao gerar o relatorio de produtividade semanal.")


def generate_produtividade_semanal_report(
    db_path: Path | None = None,
    reference_date: date | None = None,
) -> Path:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado em: {database_path}")

    with sqlite3.connect(database_path) as connection:
        data_df, week_start, week_end = load_weekly_data(connection, reference_date)

    report_frames = build_report_frames(data_df, week_start, week_end)
    output_path = write_report_excel(report_frames)
    logging.info("Relatorio de produtividade semanal gerado em: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_produtividade_semanal_report()
