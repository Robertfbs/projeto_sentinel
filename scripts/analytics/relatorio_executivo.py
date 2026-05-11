import argparse
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    from .queries import REPORT_QUERIES
    from ._db import connect as _connect_db
except ImportError:
    from queries import REPORT_QUERIES
    from _db import connect as _connect_db


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "03_database" / "pre_contencioso.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

GRANULARITY_ORDER = {
    "DIARIA": 1,
    "SEMANAL": 2,
    "MENSAL": 3,
    "ANUAL": 4,
}

SKIP_TOTAL_ROW_SHEETS = {"DATA"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera relatorio executivo do Projeto Sentinel em Excel."
    )
    parser.add_argument(
        "--data-inicial",
        help="Data inicial no formato YYYY-MM-DD.",
    )
    parser.add_argument(
        "--data-final",
        help="Data final no formato YYYY-MM-DD. Regra D-1: nunca pode ser hoje.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Forca execucao automatica com ultimos 7 dias respeitando D-1.",
    )
    return parser.parse_args()


def default_period(reference_date: date | None = None) -> tuple[date, date]:
    current_day = reference_date or date.today()
    end_date = current_day - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    return start_date, end_date


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Data invalida: {value}. Use o formato YYYY-MM-DD.") from exc


def validate_period(start_date: date, end_date: date) -> tuple[date, date]:
    max_end_date = date.today() - timedelta(days=1)

    if end_date > max_end_date:
        raise ValueError(
            f"Regra D-1 violada: a data final maxima permitida e {max_end_date:%Y-%m-%d}."
        )
    if start_date > end_date:
        raise ValueError("A data inicial nao pode ser maior que a data final.")

    return start_date, end_date


def prompt_for_period() -> tuple[date, date]:
    start_default, end_default = default_period()
    print("Informe o periodo do relatorio.")
    print(
        f"Pressione Enter nas duas perguntas para usar o modo automatico: "
        f"{start_default:%Y-%m-%d} a {end_default:%Y-%m-%d}."
    )

    start_text = input("Data inicial (YYYY-MM-DD): ").strip()
    end_text = input("Data final   (YYYY-MM-DD): ").strip()

    if not start_text and not end_text:
        return start_default, end_default
    if not start_text or not end_text:
        raise ValueError("Informe as duas datas ou deixe ambas em branco.")

    return validate_period(parse_iso_date(start_text), parse_iso_date(end_text))


def resolve_period(args: argparse.Namespace) -> tuple[date, date]:
    if args.data_inicial or args.data_final:
        if not args.data_inicial or not args.data_final:
            raise ValueError("Ao usar parametros, informe --data-inicial e --data-final.")
        return validate_period(
            parse_iso_date(args.data_inicial),
            parse_iso_date(args.data_final),
        )

    if args.auto or not sys.stdin.isatty():
        return default_period()

    return prompt_for_period()


def load_reports(
    connection: sqlite3.Connection,
    start_date: date,
    end_date: date,
) -> dict[str, pd.DataFrame]:
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        # Permite reproduzir relatorios para uma data passada; quando None,
        # COALESCE no SQL recai para 'now'/'localtime'.
        "reference_date": end_date.strftime("%Y-%m-%d"),
    }

    reports: dict[str, pd.DataFrame] = {}
    for report_name, sql in REPORT_QUERIES.items():
        reports[report_name] = pd.read_sql_query(sql, connection, params=params)
    return reports


def sort_report_frames(reports: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    sorted_reports: dict[str, pd.DataFrame] = {}

    for report_name, dataframe in reports.items():
        df = dataframe.copy()

        if report_name == "Produtividade" and not df.empty:
            df["granularidade_ordem"] = df["granularidade"].map(GRANULARITY_ORDER)
            df = df.sort_values(
                by=["granularidade_ordem", "periodo_inicio", "atribuido"],
                kind="stable",
            ).drop(columns=["granularidade_ordem"])

        if report_name == "Inflow" and not df.empty:
            df["granularidade_ordem"] = df["granularidade"].map(GRANULARITY_ORDER)
            df["canal_ordem"] = (df["canal_entrada"] != "TOTAL GERAL").astype(int)
            df = df.sort_values(
                by=["granularidade_ordem", "periodo_inicio", "canal_ordem", "canal_entrada"],
                kind="stable",
            ).drop(columns=["granularidade_ordem", "canal_ordem"])

        if report_name == "DATA" and not df.empty:
            df = df.sort_values(
                by=[
                    "flag_audiencia_em_aberto_regra_atual",
                    "flag_periodo_entrada",
                    "data_entrada_base",
                    "ticket_id",
                ],
                ascending=[False, False, False, False],
                kind="stable",
            )

        sorted_reports[report_name] = df

    return sorted_reports


try:
    from .excel_utils import append_total_row as _append_total_row_shared
    from .excel_utils import auto_fit_columns as _auto_fit_columns_shared
except ImportError:
    from excel_utils import append_total_row as _append_total_row_shared  # type: ignore[no-redef]
    from excel_utils import auto_fit_columns as _auto_fit_columns_shared  # type: ignore[no-redef]


def append_total_row(dataframe: pd.DataFrame) -> pd.DataFrame:
    return _append_total_row_shared(dataframe)


def auto_fit_columns(worksheet, dataframe: pd.DataFrame) -> None:
    _auto_fit_columns_shared(worksheet, dataframe, max_width=40)


def write_report_to_excel(
    reports: dict[str, pd.DataFrame],
    start_date: date,
    end_date: date,
) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    generated_at = datetime.now()
    output_path = OUTPUT_DIR / f"relatorio_executivo_{generated_at:%Y%m%d_%H%M%S}.xlsx"

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#D9E2F3",
                "border": 1,
            }
        )
        total_row_format = workbook.add_format(
            {
                "bold": True,
                "top": 2,
            }
        )

        for sheet_name, dataframe in reports.items():
            df_to_export = dataframe.copy()
            if sheet_name not in SKIP_TOTAL_ROW_SHEETS:
                df_to_export = append_total_row(df_to_export)
            excel_sheet_name = sheet_name[:31]

            if df_to_export.empty:
                placeholder = pd.DataFrame(
                    [
                        {
                            "mensagem": "Sem dados para o periodo informado.",
                            "periodo_inicial": start_date.strftime("%Y-%m-%d"),
                            "periodo_final": end_date.strftime("%Y-%m-%d"),
                        }
                    ]
                )
                placeholder.to_excel(writer, sheet_name=excel_sheet_name, index=False)
                worksheet = writer.sheets[excel_sheet_name]
                auto_fit_columns(worksheet, placeholder)
                worksheet.freeze_panes(1, 0)
                for col_num, value in enumerate(placeholder.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                continue

            df_to_export.to_excel(writer, sheet_name=excel_sheet_name, index=False)
            worksheet = writer.sheets[excel_sheet_name]

            for col_num, value in enumerate(df_to_export.columns.values):
                worksheet.write(0, col_num, value, header_format)

            auto_fit_columns(worksheet, df_to_export)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, len(df_to_export), len(df_to_export.columns) - 1)

            if len(df_to_export) > len(dataframe):
                worksheet.set_row(len(df_to_export), None, total_row_format)

    return output_path


def print_terminal_summary(
    reports: dict[str, pd.DataFrame],
    start_date: date,
    end_date: date,
    output_path: Path,
) -> None:
    audiencias_abertas = reports["Audiencias em Aberto"]
    funil_procon = reports["Funil PROCON"]
    produtividade = reports["Produtividade"]
    inflow = reports["Inflow"]
    data_base = reports["DATA"]

    qtde_audiencias_abertas = int(
        audiencias_abertas["qtde_audiencias_em_aberto"].iloc[0]
    ) if not audiencias_abertas.empty else 0
    qtde_audiencias_futuras = int(
        audiencias_abertas["qtde_audiencias_somente_data_futura"].iloc[0]
    ) if not audiencias_abertas.empty else 0

    qtde_procon_total = int(
        funil_procon["qtde_tickets_procon_periodo"].iloc[0]
    ) if not funil_procon.empty else 0
    qtde_procon_audiencia = int(
        funil_procon["qtde_tickets_procon_com_audiencia"].iloc[0]
    ) if not funil_procon.empty else 0
    taxa_procon = float(
        funil_procon["taxa_conversao_pct"].fillna(0).iloc[0]
    ) if not funil_procon.empty else 0.0

    produtividade_diaria = produtividade[produtividade["granularidade"] == "DIARIA"]
    tickets_resolvidos_periodo = int(produtividade_diaria["tickets_resolvidos"].sum()) if not produtividade_diaria.empty else 0
    colaboradores_ativos = int(produtividade_diaria["atribuido"].nunique()) if not produtividade_diaria.empty else 0

    inflow_diario_total = inflow[
        (inflow["granularidade"] == "DIARIA") & (inflow["canal_entrada"] == "TOTAL GERAL")
    ]
    tickets_entrada_periodo = int(inflow_diario_total["qtde_tickets"].sum()) if not inflow_diario_total.empty else 0

    print()
    print("=" * 72)
    print("RELATORIO EXECUTIVO - PROJETO SENTINEL")
    print("=" * 72)
    print(f"Periodo analisado : {start_date:%Y-%m-%d} ate {end_date:%Y-%m-%d}")
    print(
        "Audiencias abertas: "
        f"{qtde_audiencias_abertas} pela regra atual corrigida | "
        f"{qtde_audiencias_futuras} somente por data futura"
    )
    print(
        "Funil PROCON      : "
        f"{qtde_procon_audiencia}/{qtde_procon_total} tickets com audiencia "
        f"({taxa_procon:.2f}%)"
    )
    print(
        "Produtividade     : "
        f"{tickets_resolvidos_periodo} tickets resolvidos por {colaboradores_ativos} colaborador(es)"
    )
    print(f"Inflow            : {tickets_entrada_periodo} tickets no periodo")
    print(f"Base DATA         : {len(data_base)} linhas para conferencia manual")
    print(f"Arquivo gerado    : {output_path}")
    print("=" * 72)
    print()


def main() -> None:
    args = parse_args()
    start_date, end_date = resolve_period(args)

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado em: {DB_PATH}")

    with _connect_db(DB_PATH, read_only=True) as connection:
        reports = load_reports(connection, start_date, end_date)

    reports = sort_report_frames(reports)
    output_path = write_report_to_excel(reports, start_date, end_date)
    print_terminal_summary(reports, start_date, end_date, output_path)


if __name__ == "__main__":
    main()
