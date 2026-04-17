import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "03_database" / "pre_contencioso.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_FILE_NAME = "relatorio_diario_pre-contencioso.xlsx"
SKIP_TOTAL_ROW_SHEETS = {"DATA", "audiencias_vencidas_pendentes", "movimentacoes_excecao"}

VISIBLE_DATA_COLUMNS = [
    "ticket_id",
    "data_criacao",
    "data_resolucao",
    "atribuido",
    "tipo_solicitacao",
    "tem_audiencia",
    "audiencia",
    "data_audiencia",
    "data_reagendamento",
    "data_audiencia_efetiva",
    "preposto",
    "status",
    "local_procon",
    "titulo_ticket",
    "assunto",
    "matricula",
    "numero_os",
    "resultado_tratativa",
    "classificacao_solicitacoes",
    "nome_solicitante",
    "email_solicitante",
    "bairro",
    "municipio",
]

HIDDEN_DATA_COLUMNS = [
    "status_normalizado",
    "flag_entrada_dia_util_anterior",
    "flag_resolvido_dia_util_anterior",
    "flag_entrada_audiencia_dia_util_anterior",
    "flag_audiencia_semana_aberta",
    "flag_audiencia_semana_encerrada",
    "data_referencia_execucao",
    "data_referencia_dia_util_anterior",
    "data_inicio_semana_execucao",
    "data_fim_semana_execucao",
]

DATE_COLUMNS = {
    "data_criacao",
    "data_resolucao",
    "data_audiencia",
    "data_reagendamento",
    "data_audiencia_efetiva",
    "data_referencia_execucao",
    "data_referencia_dia_util_anterior",
    "data_inicio_semana_execucao",
    "data_fim_semana_execucao",
    "data_referencia_entrada",
    "data_referencia_resolucao",
    "data_inicio_janela",
    "data_fim_janela",
    "data_entrada",
}

BRAZIL_FIXED_HOLIDAYS = (
    (1, 1),
    (4, 21),
    (5, 1),
    (9, 7),
    (10, 12),
    (11, 2),
    (11, 15),
    (12, 25),
)

DAILY_BASE_SQL = """
SELECT
    t.ticket_id,
    t.data_criacao,
    t.data_resolucao,
    COALESCE(NULLIF(TRIM(t.atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
    COALESCE(NULLIF(TRIM(t.tipo_solicitacao), ''), 'NAO INFORMADO') AS tipo_solicitacao,
    t.status,
    UPPER(TRIM(COALESCE(t.status, ''))) AS status_normalizado,
    t.titulo AS titulo_ticket,
    t.assunto,
    t.matricula,
    t.numero_os,
    t.resultado_tratativa,
    t.classificacao_solicitacoes,
    t.nome_solicitante,
    t.email_solicitante,
    t.bairro,
    t.municipio,
    CASE WHEN a.audiencia_id IS NOT NULL THEN 1 ELSE 0 END AS tem_audiencia,
    a.audiencia,
    a.data_audiencia,
    a.data_reagendamento,
    date(COALESCE(a.data_reagendamento, a.data_audiencia)) AS data_audiencia_efetiva,
    a.preposto,
    a.local_procon,
    :today AS data_referencia_execucao,
    :business_day AS data_referencia_dia_util_anterior,
    :today AS data_inicio_semana_execucao,
    :week_end AS data_fim_semana_execucao,
    CASE
        WHEN date(t.data_criacao) = :business_day THEN 1 ELSE 0
    END AS flag_entrada_dia_util_anterior,
    CASE
        WHEN date(t.data_resolucao) = :business_day THEN 1 ELSE 0
    END AS flag_resolvido_dia_util_anterior,
    CASE
        WHEN date(t.data_criacao) = :business_day
             AND a.audiencia_id IS NOT NULL
        THEN 1 ELSE 0
    END AS flag_entrada_audiencia_dia_util_anterior,
    CASE
        WHEN a.audiencia_id IS NOT NULL
             AND date(COALESCE(a.data_reagendamento, a.data_audiencia)) BETWEEN :today AND :week_end
             AND UPPER(TRIM(COALESCE(t.status, ''))) NOT IN ('SOLVED', 'CLOSED')
        THEN 1 ELSE 0
    END AS flag_audiencia_semana_aberta,
    CASE
        WHEN a.audiencia_id IS NOT NULL
             AND date(COALESCE(a.data_reagendamento, a.data_audiencia)) BETWEEN :today AND :week_end
             AND UPPER(TRIM(COALESCE(t.status, ''))) IN ('SOLVED', 'CLOSED')
        THEN 1 ELSE 0
    END AS flag_audiencia_semana_encerrada
FROM tickets AS t
LEFT JOIN audiencias AS a
    ON a.ticket_id = t.ticket_id
WHERE
    COALESCE(t.flag_arquivado_relatorio, 0) = 0
    AND UPPER(TRIM(COALESCE(t.tipo_manifestacao, ''))) <> 'ANEXO'
    AND (
        t.formulario_ticket IS NULL
        OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
    )
    AND (
        date(t.data_criacao) = :business_day
        OR date(t.data_resolucao) = :business_day
        OR (
            a.audiencia_id IS NOT NULL
            AND date(COALESCE(a.data_reagendamento, a.data_audiencia)) BETWEEN :today AND :week_end
        )
    )
ORDER BY
    date(COALESCE(a.data_reagendamento, a.data_audiencia)) ASC,
    date(t.data_criacao) DESC,
    t.ticket_id DESC
"""

EXCEPTION_MOVEMENTS_SQL = """
SELECT
    date(t.data_criacao) AS data_entrada,
    date(t.data_resolucao) AS data_resolucao,
    COALESCE(NULLIF(TRIM(t.atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
    COALESCE(NULLIF(TRIM(t.tipo_solicitacao), ''), 'NAO INFORMADO') AS canal
FROM tickets AS t
WHERE
    COALESCE(t.flag_arquivado_relatorio, 0) = 0
    AND UPPER(TRIM(COALESCE(t.tipo_manifestacao, ''))) <> 'ANEXO'
    AND (
        t.formulario_ticket IS NULL
        OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
    )
    AND :has_exception_window = 1
    AND (
        date(t.data_criacao) BETWEEN :exception_start AND :exception_end
        OR date(t.data_resolucao) BETWEEN :exception_start AND :exception_end
    )
ORDER BY
    date(t.data_criacao) ASC,
    date(t.data_resolucao) ASC,
    atribuido ASC,
    canal ASC
"""


def calculate_easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def build_holiday_calendar(years: set[int]) -> set[date]:
    holidays: set[date] = set()
    for year in years:
        holidays.update({date(year, month, day) for month, day in BRAZIL_FIXED_HOLIDAYS})
        easter = calculate_easter_sunday(year)
        holidays.update(
            {
                easter - timedelta(days=48),  # Carnival Monday
                easter - timedelta(days=47),  # Carnival Tuesday
                easter - timedelta(days=2),   # Good Friday
                easter + timedelta(days=60),  # Corpus Christi
            }
        )
    return holidays


def is_business_day(target_date: date, holidays: set[date]) -> bool:
    return target_date.weekday() < 5 and target_date not in holidays


def resolve_previous_business_day(reference_date: date, holidays: set[date]) -> date:
    candidate = reference_date - timedelta(days=1)
    while not is_business_day(candidate, holidays):
        candidate -= timedelta(days=1)
    return candidate


def resolve_reference_window(
    reference_date: date | None = None,
) -> tuple[date, date, date, date | None, date | None, set[date]]:
    today = reference_date or date.today()
    holiday_years = {today.year, (today - timedelta(days=7)).year, (today + timedelta(days=7)).year}
    holidays = build_holiday_calendar(holiday_years)
    business_day = resolve_previous_business_day(today, holidays)
    week_end = today + timedelta(days=max(0, 4 - today.weekday()))
    exception_start = business_day + timedelta(days=1)
    exception_end = today - timedelta(days=1)

    if exception_start > exception_end:
        exception_start = None
        exception_end = None

    return today, business_day, week_end, exception_start, exception_end, holidays


def normalize_subject_for_report(value: object) -> object:
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

    for text_column in ["assunto", "tipo_solicitacao", "canal"]:
        if text_column in df.columns:
            df[text_column] = df[text_column].apply(normalize_subject_for_report)

    for column in DATE_COLUMNS:
        if column in df.columns:
            parsed = pd.to_datetime(df[column], errors="coerce")
            df[column] = parsed.dt.normalize().where(parsed.notna(), pd.NaT)

    return df


def load_daily_data(
    connection: sqlite3.Connection,
    reference_date: date | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, date, date, date, date | None, date | None]:
    today, business_day, week_end, exception_start, exception_end, _holidays = resolve_reference_window(reference_date)
    params = {
        "today": today.strftime("%Y-%m-%d"),
        "business_day": business_day.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
    }
    df = pd.read_sql_query(DAILY_BASE_SQL, connection, params=params)
    exception_params = {
        "has_exception_window": 1 if exception_start and exception_end else 0,
        "exception_start": exception_start.strftime("%Y-%m-%d") if exception_start else "",
        "exception_end": exception_end.strftime("%Y-%m-%d") if exception_end else "",
    }
    exception_df = pd.read_sql_query(EXCEPTION_MOVEMENTS_SQL, connection, params=exception_params)
    return df, exception_df, today, business_day, week_end, exception_start, exception_end


def build_report_frames(
    data_df: pd.DataFrame,
    exception_df: pd.DataFrame,
    today: date,
    business_day: date,
    week_end: date,
) -> dict[str, pd.DataFrame]:
    df = data_df.copy()

    entrada_df = df[df["flag_entrada_dia_util_anterior"] == 1].copy()
    resolvidos_df = df[df["flag_resolvido_dia_util_anterior"] == 1].copy()
    entrada_audiencias_df = df[df["flag_entrada_audiencia_dia_util_anterior"] == 1].copy()
    audiencias_abertas_df = df[df["flag_audiencia_semana_aberta"] == 1].copy()
    audiencias_encerradas_df = df[df["flag_audiencia_semana_encerrada"] == 1].copy()
    today_ts = pd.Timestamp(today)
    audiencias_vencidas_pendentes_df = df[
        (df["tem_audiencia"] == 1)
        & pd.to_datetime(df["data_audiencia_efetiva"], errors="coerce").lt(today_ts)
        & ~df["status_normalizado"].isin(["SOLVED", "CLOSED"])
    ].copy()

    entrada_total = pd.DataFrame(
        [
            {
                "data_referencia_entrada": business_day.strftime("%Y-%m-%d"),
                "qtde_tickets": int(entrada_df["ticket_id"].nunique()),
            }
        ]
    )

    entrada_por_canal = (
        entrada_df.groupby("tipo_solicitacao", dropna=False)["ticket_id"]
        .nunique()
        .reset_index(name="qtde_tickets")
        .sort_values(["qtde_tickets", "tipo_solicitacao"], ascending=[False, True], kind="stable")
    )

    resolvidos_total = pd.DataFrame(
        [
            {
                "data_referencia_resolucao": business_day.strftime("%Y-%m-%d"),
                "qtde_tickets_resolvidos": int(resolvidos_df["ticket_id"].nunique()),
            }
        ]
    )

    resolvidos_por_colaborador = (
        resolvidos_df.groupby("atribuido", dropna=False)["ticket_id"]
        .nunique()
        .reset_index(name="qtde_tickets_resolvidos")
        .sort_values(["qtde_tickets_resolvidos", "atribuido"], ascending=[False, True], kind="stable")
    )

    entrada_audiencias = pd.DataFrame(
        [
            {
                "data_referencia_entrada": business_day.strftime("%Y-%m-%d"),
                "qtde_tickets_com_audiencia": int(entrada_audiencias_df["ticket_id"].nunique()),
            }
        ]
    )

    audiencias_semana_abertas = (
        audiencias_abertas_df.groupby(
            ["data_audiencia_efetiva", "local_procon", "preposto", "atribuido"],
            dropna=False,
        )["ticket_id"]
        .nunique()
        .reset_index(name="qtde_audiencias")
        .sort_values(
            ["data_audiencia_efetiva", "qtde_audiencias", "local_procon", "preposto", "atribuido"],
            ascending=[True, False, True, True, True],
            kind="stable",
        )
    )
    audiencias_semana_abertas.insert(0, "data_inicio_janela", today.strftime("%Y-%m-%d"))
    audiencias_semana_abertas.insert(1, "data_fim_janela", week_end.strftime("%Y-%m-%d"))

    audiencias_semana_encerradas = (
        audiencias_encerradas_df.groupby(
            ["data_audiencia_efetiva", "local_procon", "preposto", "atribuido"],
            dropna=False,
        )["ticket_id"]
        .nunique()
        .reset_index(name="qtde_audiencias")
        .sort_values(
            ["data_audiencia_efetiva", "qtde_audiencias", "local_procon", "preposto", "atribuido"],
            ascending=[True, False, True, True, True],
            kind="stable",
        )
    )
    audiencias_semana_encerradas.insert(0, "data_inicio_janela", today.strftime("%Y-%m-%d"))
    audiencias_semana_encerradas.insert(1, "data_fim_janela", week_end.strftime("%Y-%m-%d"))

    audiencias_vencidas_pendentes = audiencias_vencidas_pendentes_df[
        [
            "ticket_id",
            "data_criacao",
            "data_resolucao",
            "data_audiencia",
            "data_reagendamento",
            "data_audiencia_efetiva",
            "status",
            "atribuido",
            "preposto",
            "local_procon",
            "titulo_ticket",
            "assunto",
            "matricula",
            "numero_os",
            "tipo_solicitacao",
            "resultado_tratativa",
            "nome_solicitante",
            "email_solicitante",
        ]
    ].sort_values(
        ["data_audiencia_efetiva", "status", "atribuido", "ticket_id"],
        ascending=[True, True, True, False],
        kind="stable",
    )

    ordered_data_columns = [column for column in VISIBLE_DATA_COLUMNS + HIDDEN_DATA_COLUMNS if column in df.columns]
    df = df[ordered_data_columns].copy()
    exception_export = exception_df[["data_entrada", "data_resolucao", "atribuido", "canal"]].copy()
    exception_export = exception_export.sort_values(
        ["data_entrada", "data_resolucao", "atribuido", "canal"],
        ascending=[True, True, True, True],
        kind="stable",
    )

    reports = {
        "DATA": df,
        "entrada_total_tickets": entrada_total,
        "entrada_por_canal": entrada_por_canal,
        "resolvidos_total": resolvidos_total,
        "resolvidos_por_colaborador": resolvidos_por_colaborador,
        "entrada_audiencias": entrada_audiencias,
        "audiencias_semana_abertas": audiencias_semana_abertas,
        "audiencias_semana_encerradas": audiencias_semana_encerradas,
        "audiencias_vencidas_pendentes": audiencias_vencidas_pendentes,
        "movimentacoes_excecao": exception_export,
    }

    return {sheet_name: normalize_report_dataframe(report_df) for sheet_name, report_df in reports.items()}


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
                        placeholder = pd.DataFrame([{"mensagem": "Sem dados para a janela calculada."}])
                        placeholder.to_excel(writer, sheet_name=excel_sheet_name, index=False)
                        worksheet = writer.sheets[excel_sheet_name]
                        for col_num, value in enumerate(placeholder.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        auto_fit_columns(worksheet, placeholder)
                        worksheet.freeze_panes(1, 0)
                        continue

                    start_row = 0
                    df_to_export.to_excel(writer, sheet_name=excel_sheet_name, index=False, startrow=start_row)

                    worksheet = writer.sheets[excel_sheet_name]

                    for col_num, value in enumerate(df_to_export.columns.values):
                        worksheet.write(start_row, col_num, value, header_format)

                    auto_fit_columns(worksheet, df_to_export, date_format=date_format)
                    worksheet.freeze_panes(start_row + 1, 0)

                    if sheet_name == "DATA":
                        table_columns = [{"header": column} for column in df_to_export.columns]
                        worksheet.add_table(
                            start_row,
                            0,
                            start_row + len(df_to_export),
                            len(df_to_export.columns) - 1,
                            {
                                "name": "tb_relatorio_diario_data",
                                "style": "Table Style Medium 2",
                                "columns": table_columns,
                            },
                        )
                        for column_name in HIDDEN_DATA_COLUMNS:
                            if column_name in df_to_export.columns:
                                col_idx = df_to_export.columns.get_loc(column_name)
                                worksheet.set_column(col_idx, col_idx, None, None, {"hidden": True})
                    else:
                        worksheet.autofilter(
                            start_row,
                            0,
                            start_row + len(df_to_export),
                            len(df_to_export.columns) - 1,
                        )
                        if sheet_name not in SKIP_TOTAL_ROW_SHEETS and len(df_to_export) > len(dataframe):
                            worksheet.set_row(start_row + len(df_to_export), None, total_row_format)

            return output_path
        except OSError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("Falha inesperada ao gerar o relatorio diario pre-contencioso.")


def generate_daily_pre_contencioso_report(
    db_path: Path | None = None,
    reference_date: date | None = None,
) -> Path:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado em: {database_path}")

    with sqlite3.connect(database_path) as connection:
        data_df, exception_df, today, business_day, week_end, _exception_start, _exception_end = load_daily_data(
            connection, reference_date
        )

    report_frames = build_report_frames(data_df, exception_df, today, business_day, week_end)
    output_path = write_report_excel(report_frames)
    logging.info("Relatorio diario pre-contencioso gerado em: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_daily_pre_contencioso_report()
