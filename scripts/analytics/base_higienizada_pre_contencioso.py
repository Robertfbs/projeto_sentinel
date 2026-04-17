import logging
import sqlite3
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "03_database" / "pre_contencioso.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_FILE_STEM = "base_higienizada_pre-contencioso"
OUTPUT_COLUMNS = [
    "data_criacao",
    "data_resolucao",
    "ticket_id",
    "atribuido",
    "formulario_ticket",
    "tags_ticket",
    "grupo_tickets",
    "matricula",
    "superintendencia_adr",
    "canal_origem",
    "cpf_cliente",
    "passou_nivel_1",
    "canais_de_atrito",
    "tipo_solicitacao",
    "motivo_espera",
    "prioridade_ticket",
    "titulo",
    "classificacao_notificacoes",
    "tipo_manifestacao",
    "resultado_tratativa",
    "controle_interno",
    "numero_os",
    "status",
    "concessionaria",
    "classificacao_solicitacoes",
    "assunto",
    "local_procon",
    "audiencia",
    "nome_solicitante",
    "email_solicitante",
    "bloco",
    "bairro",
    "municipio",
    "logradouro",
    "endereco",
    "numero_porta",
    "complemento",
    "telefone",
    "nome_cliente_gss",
    "nome_requerente_gss",
    "tipo_audiencia",
    "data_audiencia",
    "preposto",
    "data_reagendamento",
    "case_id",
    "case_jec",
    "protocolo_referencia",
]
DATE_COLUMNS = {
    "data_criacao",
    "data_resolucao",
    "data_audiencia",
    "data_reagendamento",
}


def build_source_sql(table_name: str) -> str:
    return f"""
    SELECT
        date(t.data_criacao) AS data_criacao,
        date(t.data_resolucao) AS data_resolucao,
        t.ticket_id,
        t.atribuido,
        t.formulario_ticket,
        t.tags_ticket,
        t.grupo_tickets,
        t.matricula,
        t.superintendencia_adr,
        t.canal_origem,
        t.cpf_cliente,
        t.passou_nivel_1,
        t.canais_de_atrito,
        t.tipo_solicitacao,
        t.motivo_espera,
        t.prioridade_ticket,
        t.titulo,
        t.classificacao_notificacoes,
        t.tipo_manifestacao,
        t.resultado_tratativa,
        t.controle_interno,
        t.numero_os,
        t.status,
        t.concessionaria,
        t.classificacao_solicitacoes,
        t.assunto,
        a.local_procon,
        a.audiencia,
        t.nome_solicitante,
        t.email_solicitante,
        t.bloco,
        t.bairro,
        t.municipio,
        t.logradouro,
        t.endereco,
        t.numero_porta,
        t.complemento,
        t.telefone,
        t.nome_cliente_gss,
        t.nome_requerente_gss,
        a.tipo_audiencia,
        date(a.data_audiencia) AS data_audiencia,
        a.preposto,
        date(a.data_reagendamento) AS data_reagendamento,
        t.case_id,
        t.case_jec,
        COALESCE(
            NULLIF(TRIM(t.protocolo_referencia_informado), ''),
            NULLIF(TRIM(c.protocolo_agenersa), ''),
            NULLIF(TRIM(t.protocolo_procon), ''),
            NULLIF(TRIM(t.protocolo_defensoria), ''),
            NULLIF(TRIM(t.protocolo_codecon), ''),
            NULLIF(TRIM(t.case_jec), '')
        ) AS protocolo_referencia
    FROM {table_name} AS t
    LEFT JOIN audiencias AS a
        ON a.ticket_id = t.ticket_id
    LEFT JOIN cases AS c
        ON c.case_id = t.case_id
    WHERE
        COALESCE(t.flag_arquivado_relatorio, 0) = 0
        AND UPPER(TRIM(REPLACE(COALESCE(t.tipo_manifestacao, ''), char(160), ' '))) <> 'ANEXO'
        AND UPPER(TRIM(REPLACE(COALESCE(t.classificacao_notificacoes, ''), char(160), ' '))) <> 'INFORMATIVO::ANEXO'
    """


def normalize_whitespace(value: object) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).replace("\xa0", " ").strip()
    text = " ".join(text.split())
    return text or None


def normalize_subject(value: object) -> str | None:
    text = normalize_whitespace(value)
    if text is None:
        return None

    if "::" in text:
        text = text.split("::")[-1].strip()

    text = unicodedata.normalize("NFKC", text)
    text = " ".join(text.split())
    return text.upper() if text else None


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.reindex(columns=OUTPUT_COLUMNS)

    df = dataframe.copy()

    for column in df.columns:
        if column in DATE_COLUMNS:
            parsed = pd.to_datetime(df[column], errors="coerce")
            df[column] = parsed.dt.normalize().where(parsed.notna(), pd.NaT)
        elif column == "assunto":
            df[column] = df[column].apply(normalize_subject)
        elif df[column].dtype == "object":
            df[column] = df[column].apply(normalize_whitespace)

    tipo_manifestacao_norm = (
        df["tipo_manifestacao"].fillna("").astype(str).str.replace("\xa0", " ", regex=False).str.strip().str.upper()
    )
    classificacao_notificacoes_norm = (
        df["classificacao_notificacoes"]
        .fillna("")
        .astype(str)
        .str.replace("\xa0", " ", regex=False)
        .str.strip()
        .str.upper()
    )
    df = df[
        (tipo_manifestacao_norm != "ANEXO")
        & (classificacao_notificacoes_norm != "INFORMATIVO::ANEXO")
    ].copy()

    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = None

    return df[OUTPUT_COLUMNS].sort_values(
        ["data_criacao", "ticket_id"],
        ascending=[False, False],
        kind="stable",
    )


def auto_fit_columns(worksheet, dataframe: pd.DataFrame, date_format=None) -> None:
    for column_index, column_name in enumerate(dataframe.columns):
        column_values = dataframe[column_name].fillna("").astype(str)
        max_value_length = column_values.map(len).max() if not column_values.empty else 0
        width = min(max(len(str(column_name)), int(max_value_length)) + 2, 42)
        worksheet.set_column(
            column_index,
            column_index,
            width,
            date_format if column_name in DATE_COLUMNS else None,
        )


def write_excel(dataframe: pd.DataFrame, execution_date: date | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    base_date = execution_date or date.today()
    output_path = OUTPUT_DIR / f"{OUTPUT_FILE_STEM}_{base_date:%Y_%m_%d}.xlsx"
    fallback_path = OUTPUT_DIR / f"{output_path.stem}_{datetime.now():%H%M%S}{output_path.suffix}"
    last_error: Exception | None = None

    for candidate_path in [output_path, fallback_path]:
        try:
            if candidate_path.exists():
                candidate_path.unlink()

            with pd.ExcelWriter(
                candidate_path,
                engine="xlsxwriter",
                date_format="dd/mm/yyyy",
                datetime_format="dd/mm/yyyy",
            ) as writer:
                workbook = writer.book
                header_format = workbook.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1})
                date_format = workbook.add_format({"num_format": "dd/mm/yyyy"})

                export_df = dataframe.copy()
                if export_df.empty:
                    export_df = pd.DataFrame([{"mensagem": "Sem dados higienizados disponiveis."}])

                export_df.to_excel(writer, sheet_name="DATA", index=False)
                worksheet = writer.sheets["DATA"]

                for col_num, value in enumerate(export_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                auto_fit_columns(worksheet, export_df, date_format=date_format)
                worksheet.freeze_panes(1, 0)

                if not export_df.empty and "mensagem" not in export_df.columns:
                    worksheet.add_table(
                        0,
                        0,
                        len(export_df),
                        len(export_df.columns) - 1,
                        {
                            "name": "tb_base_higienizada_pre_contencioso",
                            "style": "Table Style Medium 2",
                            "columns": [{"header": column} for column in export_df.columns],
                        },
                    )

            return candidate_path
        except OSError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    raise RuntimeError("Falha inesperada ao gerar a base higienizada.")


def generate_base_higienizada_pre_contencioso(
    db_path: Path | None = None,
    reference_date: date | None = None,
) -> Path:
    database_path = db_path or DB_PATH
    if not database_path.exists():
        raise FileNotFoundError(f"Banco de dados nao encontrado em: {database_path}")

    with sqlite3.connect(database_path) as connection:
        df_solicitacao = pd.read_sql_query(build_source_sql("tickets"), connection)
        df_notificacao = pd.read_sql_query(build_source_sql("tickets_notificacao"), connection)

    combined_df = pd.concat([df_solicitacao, df_notificacao], ignore_index=True)
    cleaned_df = normalize_dataframe(combined_df)
    output_path = write_excel(cleaned_df, reference_date)
    logging.info(
        "Base higienizada pre-contencioso gerada em: %s (%s registros).",
        output_path,
        len(cleaned_df),
    )
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_base_higienizada_pre_contencioso()
