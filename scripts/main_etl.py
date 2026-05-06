import hashlib
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from analytics.relatorio_diario_pre_contencioso import generate_daily_pre_contencioso_report
from analytics.produtividade_semanal import generate_produtividade_semanal_report
from analytics.base_higienizada_pre_contencioso import generate_base_higienizada_pre_contencioso
from analytics.powerbi_semantic_exports import generate_powerbi_semantic_exports
from analytics.gold_ai_ready import generate_gold_ai_ready
from business_rules import (
    apply_classification_audit_rules as br_apply_classification_audit_rules,
    apply_ticket_manual_overrides as br_apply_ticket_manual_overrides,
    build_archive_flag as br_build_archive_flag,
    build_classification_audit_records as br_build_classification_audit_records,
    build_operational_audit_records,
    filter_removed_tickets as br_filter_removed_tickets,
    purge_removed_tickets as br_purge_removed_tickets,
)
from contracts import ContractValidationError, DataContractValidator
from create_database import setup_database
from gss_matching import (
    enrich_tickets_from_gss,
    filter_raw_gss_for_ticket_enrichment,
    transform_gss_data,
)
from load_database import (
    persist_ticket_history,
    sync_current_ticket_version_metadata,
    upsert_sqlite,
)
from observability import EtlRunTracker, StepTimer, StructuredLogger, configure_structured_logging
from pipeline_common import (
    deduplicate_latest,
    derive_bloco,
    first_not_null,
    normalize_column_name,
    normalize_identifier,
    normalize_subject,
    normalize_text,
    serialize_datetime,
)
from pipeline_sources import extract_source_reports, find_source_files
from repository import DatabaseRepository


configure_structured_logging()


BASE_DIR = Path(__file__).resolve().parent.parent
PASTA_RAW = BASE_DIR / "01_raw"
PASTA_SILVER = BASE_DIR / "02_silver"
DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"

JANELA_MAXIMA_VINCULO_DIAS = 7

SILVER_FILES = {
    "geral": "ANALYTICS_BASE_TICKETS_GERAL_processed.xlsx",
    "n1": "ANALYTICS_BASE_TICKETS_N1_processed.xlsx",
    "audiencias": "PRE_CONTENCIOSO_AUDIENCIAS_processed.xlsx",
    "ticket_assunto": "ANALYTICS_BASE_TICKETS_ASSUNTOS_processed.xlsx",
    "vinculos": "ANALYTICS_BASE_TICKETS_VINCULOS_processed.xlsx",
}

LEGACY_SILVER_FILES = [
    "ANALYTICS_BASE_TICKETS_GERAL_SOLICITACAO_processed.xlsx",
    "ANALYTICS_BASE_TICKETS_GERAL_NOTIFICACAO_processed.xlsx",
    "ANALYTICS_BASE_TICKETS_processed.xlsx",
    "ANALYTICS_BASE_TICKETS_NOTIFICACAO_processed.xlsx",
    "Base_GSS_processed.xlsx",
]

EXPLICIT_LINK_KEY_CANDIDATES = [
    "id_reclamacao",
    "id_manifestacao",
    "chave_reclamacao",
    "ticket_relacionado_id",
    "ticket_relacionado",
    "external_id",
    "id_externo",
    "protocolo_reclamacao",
]


@dataclass(frozen=True)
class LinkRule:
    name: str
    columns: tuple[str, ...]
    confidence: float
    use_date_window: bool = True


AUTO_LINK_RULES = [
    LinkRule("matricula_protocolo", ("matricula", "protocolo_referencia"), 0.95, True),
    LinkRule("titulo_normalizado", ("matricula", "assunto_normalizado"), 0.85, True),
]


def build_explicit_link_key(df: pd.DataFrame) -> pd.Series:
    normalized_columns = {normalize_column_name(column): column for column in df.columns}
    series = pd.Series([None] * len(df), index=df.index, dtype="object")

    for candidate in EXPLICIT_LINK_KEY_CANDIDATES:
        original_column = normalized_columns.get(candidate)
        if not original_column:
            continue

        candidate_values = (
            df[original_column]
            .astype("string")
            .str.strip()
            .replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
        )
        series = series.combine_first(candidate_values)

    return series


def extract_zendesk_reports(ticket_kind: str) -> pd.DataFrame:
    logging.warning(
        "extract_zendesk_reports(%s) foi mantida apenas por compatibilidade. "
        "O pipeline atual usa o relatorio GERAL via descoberta dinamica por prefixo.",
        ticket_kind,
    )
    return extract_source_reports(PASTA_RAW, "zendesk_geral")


def transform_data(df: pd.DataFrame, ticket_kind: str) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    mapa_colunas_normalizado = {
        "id_do_ticket": "ticket_id",
        "criacao_do_ticket_carimbo_de_data_hora": "data_criacao",
        "resolucao_do_ticket_carimbo_de_data_hora": "data_resolucao",
        "nome_do_atribuido": "atribuido",
        "assunto_do_ticket": "titulo",
        "assuntos_do_ticket": "assunto",
        "tipos_de_conversas": "tipo_conversa",
        "tipos_de_solicitacoes": "tipo_solicitacao",
        "status_do_ticket": "status",
        "matricula": "matricula",
        "tipo_de_manifestacao": "tipo_manifestacao",
        "formulario_de_ticket": "formulario_ticket",
        "classificacao_notificacoes": "classificacao_notificacoes",
        "classificacao_solicitacoes": "classificacao_solicitacoes",
        "numero_da_os": "numero_os",
        "resultado_tratativa_segundo_nivel": "resultado_tratativa",
        "audiencia": "audiencia",
        "tipo_de_audiencia": "tipo_audiencia",
        "data_da_audiencia_carimbo_de_data_hora": "data_audiencia",
        "preposto_name": "preposto",
        "local_do_procon": "local_procon",
        "data_de_reagendamento_carimbo_de_data_hora": "data_reagendamento",
        "tags_de_ticket": "tags_ticket",
        "grupo_de_tickets": "grupo_tickets",
        "superintendencia_adr": "superintendencia_adr",
        "canal_de_origem": "canal_origem",
        "cpf_cliente": "cpf_cliente",
        "passou_pelo_nivel_1": "passou_nivel_1",
        "canais_de_atrito": "canais_de_atrito",
        "protocolo_de_referencia": "protocolo_referencia_informado",
        "motivo_de_espera": "motivo_espera",
        "prioridade_do_ticket": "prioridade_ticket",
        "controle_interno": "controle_interno",
        "concessionaria": "concessionaria",
        "bairro": "bairro",
        "municipio": "municipio",
        "logradouro": "logradouro",
        "nome_logradouro": "logradouro",
        "endereco": "endereco",
        "endereco_do_requerente": "endereco",
        "numero_da_porta": "numero_porta",
        "numero_porta": "numero_porta",
        "complemento": "complemento",
        "desc_complemento": "complemento",
        "telefone": "telefone",
        "nome_do_solicitante": "nome_solicitante",
        "e_mail_do_solicitante": "email_solicitante",
        "tickets": "contagem_zendesk",
    }

    rename_map = {
        column: mapa_colunas_normalizado[normalize_column_name(column)]
        for column in df.columns
        if normalize_column_name(column) in mapa_colunas_normalizado
    }
    df = df.rename(columns=rename_map)

    required_columns = [
        "ticket_id",
        "data_criacao",
        "data_resolucao",
        "atribuido",
        "titulo",
        "assunto",
        "tipo_conversa",
        "tipo_solicitacao",
        "status",
        "matricula",
        "bloco",
        "tipo_manifestacao",
        "numero_os",
        "resultado_tratativa",
        "tags_ticket",
        "grupo_tickets",
        "superintendencia_adr",
        "canal_origem",
        "cpf_cliente",
        "passou_nivel_1",
        "canais_de_atrito",
        "protocolo_referencia_informado",
        "motivo_espera",
        "prioridade_ticket",
        "controle_interno",
        "concessionaria",
        "bairro",
        "municipio",
        "logradouro",
        "endereco",
        "numero_porta",
        "complemento",
        "telefone",
        "nome_cliente_gss",
        "nome_requerente_gss",
        "nome_solicitante",
        "email_solicitante",
        "classificacao_solicitacoes",
        "formulario_ticket",
        "classificacao_notificacoes",
        "audiencia",
        "tipo_audiencia",
        "data_audiencia",
        "preposto",
        "local_procon",
        "data_reagendamento",
        "arquivo_origem",
        "arquivo_mtime",
    ]
    for column in required_columns:
        if column not in df.columns:
            df[column] = None

    df = df.dropna(subset=["ticket_id"]).copy()
    df["ticket_id"] = pd.to_numeric(df["ticket_id"], errors="coerce")
    df = df.dropna(subset=["ticket_id"]).copy()
    df["ticket_id"] = df["ticket_id"].astype(int)
    df = br_filter_removed_tickets(df, context=f"transform_data_{ticket_kind}")

    df["tipo_ticket_zendesk"] = ticket_kind.upper()
    df["chave_explicita_vinculo"] = build_explicit_link_key(df)

    if "formulario_ticket" in df.columns:
        df["formulario_ticket"] = df["formulario_ticket"].astype("string").str.strip()
        formulario_norm = df["formulario_ticket"].apply(normalize_text)
        if formulario_norm.notna().any():
            prefixo_esperado = "SOLICIT" if ticket_kind == "solicitacao" else "NOTIFIC"
            tamanho_original = len(df)
            df = df[
                formulario_norm.isna()
                | formulario_norm.str.startswith(prefixo_esperado, na=False)
            ].copy()
            logging.info(
                "Removidos %s tickets de formulario divergente em %s.",
                tamanho_original - len(df),
                ticket_kind.upper(),
            )

    for column in ["data_criacao", "data_resolucao", "data_audiencia", "data_reagendamento"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["matricula"] = df["matricula"].apply(normalize_identifier)
    df["bloco"] = df["matricula"].apply(derive_bloco)
    df["numero_os"] = df["numero_os"].apply(normalize_identifier)
    df["cpf_cliente"] = df["cpf_cliente"].apply(normalize_identifier)
    df["protocolo_referencia_informado"] = (
        df["protocolo_referencia_informado"]
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
    )
    df["tipo_solicitacao"] = df.apply(
        lambda row: first_not_null(row, ["tipo_solicitacao", "classificacao_solicitacoes", "canais_de_atrito"]),
        axis=1,
    )

    df["flag_arquivado_relatorio"] = br_build_archive_flag(df)
    logging.info(
        "Marcados %s tickets para arquivamento logico em %s.",
        int(df["flag_arquivado_relatorio"].sum()),
        ticket_kind.upper(),
    )

    df = br_apply_ticket_manual_overrides(df, ticket_kind)

    if "titulo" in df.columns:
        df["protocolo_agenersa"] = df["titulo"].apply(
            lambda value: re.search(r"\d{10}", str(value)).group()
            if pd.notnull(value) and re.search(r"\d{10}", str(value))
            else None
        )
        df["protocolo_procon"] = df["titulo"].apply(
            lambda value: re.search(r"\d{2}\.\d{2}\.\d{4}\.\d{3}\.\d{5}-\d{3}", str(value)).group()
            if pd.notnull(value) and re.search(r"\d{2}\.\d{2}\.\d{4}\.\d{3}\.\d{5}-\d{3}", str(value))
            else None
        )
        df["protocolo_defensoria"] = df["titulo"].apply(
            lambda value: re.search(r"[Vv]\d{2,5}/\d{4}", str(value)).group()
            if pd.notnull(value) and re.search(r"[Vv]\d{2,5}/\d{4}", str(value))
            else None
        )
        df["protocolo_codecon"] = df["titulo"].apply(
            lambda value: re.search(r"\d{4,6}/\d{4}", str(value)).group()
            if pd.notnull(value) and re.search(r"\d{4,6}/\d{4}", str(value))
            else None
        )
    else:
        df["protocolo_agenersa"] = None
        df["protocolo_procon"] = None
        df["protocolo_defensoria"] = None
        df["protocolo_codecon"] = None

    df["case_id"] = df["protocolo_agenersa"].combine_first(df["ticket_id"].astype(str))

    def gerar_case_jec(row: pd.Series) -> str | None:
        canal = str(row.get("tipo_solicitacao", "")).upper()
        manifestacao = str(row.get("tipo_manifestacao", "")).upper()

        if "JEC" not in canal and "JEC" not in manifestacao:
            return None

        cpf = str(row.get("cpf_cliente", "")).strip()
        matricula = str(row.get("matricula", "")).strip()
        assunto = str(row.get("assunto", "")).strip().lower()
        texto_base = f"{cpf}|{matricula}|{assunto}".encode("utf-8")
        return hashlib.md5(texto_base).hexdigest()

    df["case_jec"] = df.apply(gerar_case_jec, axis=1)

    df["assunto_normalizado"] = df.apply(
        lambda row: normalize_subject(first_not_null(row, ["assunto", "titulo"])),
        axis=1,
    )
    df["protocolo_referencia"] = df.apply(
        lambda row: first_not_null(
            row,
            [
                "protocolo_referencia_informado",
                "protocolo_agenersa",
                "protocolo_procon",
                "protocolo_defensoria",
                "protocolo_codecon",
                "case_jec",
            ],
        ),
        axis=1,
    )

    if ticket_kind == "solicitacao":
        df = br_apply_classification_audit_rules(df)

    return df

def transform_n1_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    frame = df.copy()
    frame.columns = [str(column).strip() for column in frame.columns]

    mapa_colunas_normalizado = {
        "id_do_ticket": "ticket_id",
        "criacao_do_ticket_carimbo_de_data_hora": "data_criacao",
        "resolucao_do_ticket_carimbo_de_data_hora": "data_resolucao",
        "status_do_ticket": "status",
        "matricula": "matricula",
        "assunto_do_ticket": "titulo",
        "assuntos_do_ticket": "assunto",
        "grupo_de_tickets": "grupo_tickets",
        "canal_do_ticket": "canal_ticket",
        "canal_de_origem": "canal_origem",
        "formulario_de_ticket": "formulario_ticket",
        "tipo_do_ticket": "tipo_ticket",
        "sistema_conversationid": "conversation_id",
        "tipos_de_conversas": "tipo_conversa",
        "tickets": "contagem_zendesk",
    }

    rename_map = {
        column: mapa_colunas_normalizado[normalize_column_name(column)]
        for column in frame.columns
        if normalize_column_name(column) in mapa_colunas_normalizado
    }
    frame = frame.rename(columns=rename_map)

    required_columns = [
        "ticket_id",
        "matricula",
        "bloco",
        "data_criacao",
        "data_resolucao",
        "status",
        "titulo",
        "assunto",
        "grupo_tickets",
        "canal_ticket",
        "canal_origem",
        "formulario_ticket",
        "tipo_ticket",
        "conversation_id",
        "tipo_conversa",
        "arquivo_origem",
        "arquivo_mtime",
    ]
    for column in required_columns:
        if column not in frame.columns:
            frame[column] = None

    frame = frame.dropna(subset=["ticket_id"]).copy()
    frame["ticket_id"] = pd.to_numeric(frame["ticket_id"], errors="coerce")
    frame = frame.dropna(subset=["ticket_id"]).copy()
    frame["ticket_id"] = frame["ticket_id"].astype(int)
    frame = br_filter_removed_tickets(frame, context="transform_n1")
    frame["matricula"] = frame["matricula"].apply(normalize_identifier)
    frame["bloco"] = frame["matricula"].apply(derive_bloco)
    frame["data_criacao"] = pd.to_datetime(frame["data_criacao"], errors="coerce")
    frame["data_resolucao"] = pd.to_datetime(frame["data_resolucao"], errors="coerce")
    return frame


def transform_audiencias_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    frame = df.copy()
    frame.columns = [str(column).strip() for column in frame.columns]

    mapa_colunas_normalizado = {
        "id_do_ticket": "ticket_audiencia_id",
        "ticket_relacionado_id": "ticket_relacionado_id",
        "data_da_audiencia_carimbo_de_data_hora": "data_audiencia",
        "data_de_reagendamento_carimbo_de_data_hora": "data_reagendamento",
        "tipo_de_audiencia": "tipo_audiencia",
        "status_do_ticket": "status_ticket",
        "preposto_id": "preposto_id",
        "preposto_name": "preposto",
        "nome_do_atribuido": "atribuido",
        "tickets": "contagem_zendesk",
    }

    rename_map = {
        column: mapa_colunas_normalizado[normalize_column_name(column)]
        for column in frame.columns
        if normalize_column_name(column) in mapa_colunas_normalizado
    }
    frame = frame.rename(columns=rename_map)

    required_columns = [
        "ticket_audiencia_id",
        "ticket_relacionado_id",
        "data_audiencia",
        "data_reagendamento",
        "tipo_audiencia",
        "status_ticket",
        "preposto_id",
        "preposto",
        "atribuido",
        "arquivo_origem",
        "arquivo_mtime",
    ]
    for column in required_columns:
        if column not in frame.columns:
            frame[column] = None

    frame["ticket_audiencia_id"] = pd.to_numeric(frame["ticket_audiencia_id"], errors="coerce").astype("Int64")
    frame["ticket_relacionado_id"] = pd.to_numeric(frame["ticket_relacionado_id"], errors="coerce").astype("Int64")
    frame["ticket_id"] = frame["ticket_relacionado_id"].combine_first(frame["ticket_audiencia_id"])
    frame = frame.dropna(subset=["ticket_id"]).copy()
    frame["ticket_id"] = frame["ticket_id"].astype(int)
    frame = br_filter_removed_tickets(frame, context="transform_audiencias")
    frame["data_audiencia"] = pd.to_datetime(frame["data_audiencia"], errors="coerce")
    frame["data_reagendamento"] = pd.to_datetime(frame["data_reagendamento"], errors="coerce")
    frame["audiencia"] = "TRUE"
    frame["local_procon"] = None
    return frame


def build_ticket_assunto(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "ticket_assunto_id",
                "ticket_id",
                "formulario_ticket",
                "assunto_raw",
                "assunto_normalizado",
                "ordem_assunto",
                "flag_assunto_principal",
                "arquivo_origem",
            ]
        )

    frame = df.copy()
    frame["assunto_raw"] = frame.apply(
        lambda row: first_not_null(row, ["assunto", "titulo"]),
        axis=1,
    )
    frame["assunto_normalizado_item"] = frame["assunto_raw"].apply(normalize_subject)
    frame = frame.dropna(subset=["ticket_id", "assunto_normalizado_item"]).copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "ticket_assunto_id",
                "ticket_id",
                "formulario_ticket",
                "assunto_raw",
                "assunto_normalizado",
                "ordem_assunto",
                "flag_assunto_principal",
                "arquivo_origem",
            ]
        )

    frame = frame.sort_values(["arquivo_mtime", "ticket_id"], kind="stable")
    frame = frame.drop_duplicates(subset=["ticket_id", "assunto_normalizado_item"], keep="last").copy()

    frame["assunto_principal_ticket"] = frame.groupby("ticket_id")["assunto_normalizado_item"].transform("last")
    frame["preferencia_principal"] = (
        frame["assunto_normalizado_item"] == frame["assunto_principal_ticket"]
    ).astype(int)

    frame = frame.sort_values(
        ["ticket_id", "preferencia_principal", "arquivo_mtime", "assunto_normalizado_item"],
        ascending=[True, False, False, True],
        kind="stable",
    ).copy()
    frame["ordem_assunto"] = frame.groupby("ticket_id").cumcount() + 1
    frame["flag_assunto_principal"] = (frame["ordem_assunto"] == 1).astype(int)
    frame["ticket_assunto_id"] = frame.apply(
        lambda row: hashlib.md5(
            f"{int(row['ticket_id'])}|{row['assunto_normalizado_item']}".encode("utf-8")
        ).hexdigest(),
        axis=1,
    )
    frame["assunto_normalizado"] = frame["assunto_normalizado_item"]

    return frame[
        [
            "ticket_assunto_id",
            "ticket_id",
            "formulario_ticket",
            "assunto_raw",
            "assunto_normalizado",
            "ordem_assunto",
            "flag_assunto_principal",
            "arquivo_origem",
        ]
    ].copy()


def build_ticket_assunto_metrics(ticket_assunto_df: pd.DataFrame) -> pd.DataFrame:
    if ticket_assunto_df.empty:
        return pd.DataFrame(columns=["ticket_id", "qtde_assuntos_ticket", "flag_multiplos_assuntos"])

    metrics = (
        ticket_assunto_df.groupby("ticket_id", dropna=False)
        .size()
        .reset_index(name="qtde_assuntos_ticket")
    )
    metrics["flag_multiplos_assuntos"] = (metrics["qtde_assuntos_ticket"] > 1).astype(int)
    return metrics


def save_silver_output(df: pd.DataFrame, file_name: str) -> None:
    if df.empty:
        return
    output_path = PASTA_SILVER / file_name
    temp_path = output_path.with_name(f"__tmp__{output_path.stem}.xlsx")
    if temp_path.exists():
        temp_path.unlink()

    df.to_excel(temp_path, index=False)
    try:
        if output_path.exists():
            output_path.unlink()
        temp_path.replace(output_path)
        logging.info("Arquivo Silver salvo: %s", output_path.name)
    except PermissionError:
        fallback_name = (
            f"{output_path.stem}_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}{output_path.suffix}"
        )
        fallback_path = output_path.with_name(fallback_name)
        temp_path.replace(fallback_path)
        logging.warning(
            "Arquivo Silver bloqueado para substituicao. Saida salva em fallback: %s",
            fallback_path.name,
        )


def cleanup_legacy_silver_files() -> None:
    for file_name in LEGACY_SILVER_FILES:
        legacy_path = PASTA_SILVER / file_name
        if legacy_path.exists():
            legacy_path.unlink()
            logging.info("Arquivo Silver legado removido: %s", legacy_path.name)


def filter_candidates_by_window(
    notifications_df: pd.DataFrame,
    solicitacao_data_criacao: pd.Timestamp | None,
) -> pd.DataFrame:
    if pd.isna(solicitacao_data_criacao):
        return notifications_df.iloc[0:0].copy()

    data_minima = solicitacao_data_criacao - pd.Timedelta(days=JANELA_MAXIMA_VINCULO_DIAS)
    filtro = (
        notifications_df["data_criacao"].notna()
        & (notifications_df["data_criacao"] <= solicitacao_data_criacao)
        & (notifications_df["data_criacao"] >= data_minima)
    )
    return notifications_df.loc[filtro].copy()


def load_manual_links(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        manual_df = pd.read_sql_query(
            """
            SELECT ticket_solicitacao_id, ticket_notificacao_id, justificativa, usuario, atualizado_em
            FROM ticket_vinculos_manuais
            """,
            conn,
        )
        if manual_df.empty:
            return manual_df

        manual_df["ticket_solicitacao_id"] = pd.to_numeric(
            manual_df["ticket_solicitacao_id"], errors="coerce"
        ).astype("Int64")
        manual_df["ticket_notificacao_id"] = pd.to_numeric(
            manual_df["ticket_notificacao_id"], errors="coerce"
        ).astype("Int64")
        return manual_df.dropna(subset=["ticket_solicitacao_id", "ticket_notificacao_id"]).copy()
    except Exception:
        return pd.DataFrame(
            columns=[
                "ticket_solicitacao_id",
                "ticket_notificacao_id",
                "justificativa",
                "usuario",
                "atualizado_em",
            ]
        )


def build_relationship_record(
    solicitacao: pd.Series,
    status_vinculo: str,
    criterio_vinculo: str | None = None,
    confianca_vinculo: float | None = None,
    ticket_notificacao_id: int | None = None,
    data_criacao_notificacao: pd.Timestamp | None = None,
    quantidade_candidatos: int = 0,
    observacao: str | None = None,
) -> dict:
    data_criacao_solicitacao = solicitacao.get("data_criacao")
    data_entrada_reclamacao = data_criacao_solicitacao

    dias_defasagem = None
    if pd.notna(data_criacao_notificacao) and pd.notna(data_criacao_solicitacao):
        dias_defasagem = int((data_criacao_solicitacao.normalize() - data_criacao_notificacao.normalize()).days)

    return {
        "ticket_solicitacao_id": int(solicitacao["ticket_id"]),
        "ticket_notificacao_id": int(ticket_notificacao_id) if ticket_notificacao_id is not None else None,
        "status_vinculo": status_vinculo,
        "criterio_vinculo": criterio_vinculo,
        "confianca_vinculo": confianca_vinculo,
        "data_entrada_reclamacao": data_entrada_reclamacao,
        "data_criacao_solicitacao": data_criacao_solicitacao,
        "data_criacao_notificacao": data_criacao_notificacao,
        "dias_defasagem_abertura": dias_defasagem,
        "quantidade_candidatos": quantidade_candidatos,
        "observacao": observacao,
    }


def build_ticket_relationships(
    solicitacoes_df: pd.DataFrame,
    notificacoes_df: pd.DataFrame,
    manual_links_df: pd.DataFrame,
) -> pd.DataFrame:
    if solicitacoes_df.empty:
        return pd.DataFrame()

    if notificacoes_df.empty:
        relationships = [
            build_relationship_record(
                solicitacao=row,
                status_vinculo="NOTIFICACAO_NAO_CARREGADA",
                observacao="Relatorio de notificacao nao foi encontrado na carga atual.",
            )
            for _, row in solicitacoes_df.sort_values(["data_criacao", "ticket_id"]).iterrows()
        ]
        return pd.DataFrame(relationships)

    notifications = notificacoes_df.copy()
    notifications["ticket_id"] = notifications["ticket_id"].astype(int)

    manual_map = {
        int(row["ticket_solicitacao_id"]): row
        for _, row in manual_links_df.iterrows()
    }
    notification_by_id = notifications.set_index("ticket_id", drop=False)
    used_notification_ids: set[int] = set()
    relationships: list[dict] = []

    solicitacoes_ordenadas = solicitacoes_df.sort_values(["data_criacao", "ticket_id"]).copy()

    for _, solicitacao in solicitacoes_ordenadas.iterrows():
        ticket_solicitacao_id = int(solicitacao["ticket_id"])
        manual_row = manual_map.get(ticket_solicitacao_id)

        if manual_row is not None:
            notification_id = int(manual_row["ticket_notificacao_id"])
            notification = notification_by_id.loc[notification_id] if notification_id in notification_by_id.index else None
            if notification is not None:
                used_notification_ids.add(notification_id)
                relationships.append(
                    build_relationship_record(
                        solicitacao=solicitacao,
                        status_vinculo="MANUAL",
                        criterio_vinculo="manual",
                        confianca_vinculo=1.0,
                        ticket_notificacao_id=notification_id,
                        data_criacao_notificacao=notification["data_criacao"],
                        quantidade_candidatos=1,
                        observacao=manual_row.get("justificativa"),
                    )
                )
                continue

            relationships.append(
                build_relationship_record(
                    solicitacao=solicitacao,
                    status_vinculo="SEM_VINCULO",
                    criterio_vinculo="manual_invalido",
                    confianca_vinculo=0.0,
                    quantidade_candidatos=0,
                    observacao="Vinculo manual aponta para ticket de notificacao inexistente na base carregada.",
                )
            )
            continue

        automatic_notifications = notifications[
            ~notifications["ticket_id"].isin(used_notification_ids)
        ].copy()

        linked_record = None

        for rule in AUTO_LINK_RULES:
            candidates = automatic_notifications

            for column in rule.columns:
                value = solicitacao.get(column)
                if pd.isna(value) or value is None or str(value).strip() == "":
                    candidates = candidates.iloc[0:0].copy()
                    break
                candidates = candidates[candidates[column] == value]

            if rule.use_date_window and not candidates.empty:
                candidates = filter_candidates_by_window(candidates, solicitacao.get("data_criacao"))

            if candidates.empty:
                continue

            candidates = candidates.sort_values(["data_criacao", "ticket_id"])

            if len(candidates) == 1:
                notification = candidates.iloc[0]
                notification_id = int(notification["ticket_id"])
                used_notification_ids.add(notification_id)
                linked_record = build_relationship_record(
                    solicitacao=solicitacao,
                    status_vinculo="VINCULADO",
                    criterio_vinculo=rule.name,
                    confianca_vinculo=rule.confidence,
                    ticket_notificacao_id=notification_id,
                    data_criacao_notificacao=notification["data_criacao"],
                    quantidade_candidatos=1,
                    observacao=None,
                )
            else:
                candidate_ids = ", ".join(map(str, candidates["ticket_id"].tolist()[:10]))
                linked_record = build_relationship_record(
                    solicitacao=solicitacao,
                    status_vinculo="AMBIGUO",
                    criterio_vinculo=rule.name,
                    confianca_vinculo=rule.confidence,
                    quantidade_candidatos=len(candidates),
                    observacao=f"Candidatos encontrados para analise manual: {candidate_ids}",
                )
            break

        if linked_record is None:
            linked_record = build_relationship_record(
                solicitacao=solicitacao,
                status_vinculo="SEM_VINCULO",
                quantidade_candidatos=0,
                observacao="Nenhum criterio automatico encontrou notificacao correspondente.",
            )

        relationships.append(linked_record)

    relationships_df = pd.DataFrame(relationships)
    return relationships_df


def prepare_for_sqlite(df: pd.DataFrame, datetime_columns: list[str]) -> pd.DataFrame:
    prepared = df.copy()
    for column in datetime_columns:
        if column in prepared.columns:
            prepared[column] = prepared[column].apply(serialize_datetime)
    return prepared


def backfill_bloco(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    for table_name in ["tickets", "tickets_notificacao", "tickets_n1"]:
        cursor.execute(
            f"""
            UPDATE {table_name}
            SET bloco = CASE
                WHEN COALESCE(TRIM(matricula), '') LIKE '40%' THEN 'Bloco 4'
                WHEN COALESCE(TRIM(matricula), '') LIKE '10%' THEN 'Bloco 1'
                ELSE NULL
            END
            WHERE bloco IS NULL OR bloco NOT IN ('Bloco 1', 'Bloco 4')
            """
        )
    conn.commit()


def validate_source_contracts(
    raw_frames: dict[str, pd.DataFrame],
    run_id: str,
    step_logger: StructuredLogger,
) -> tuple[int, dict[str, int], list[str]]:
    validator = DataContractValidator()
    source_file_counts: dict[str, int] = {}
    missing_sources: list[str] = []
    total_files = 0

    for source_name, frame in raw_frames.items():
        source_files = find_source_files(PASTA_RAW, source_name)
        source_file_counts[source_name] = len(source_files)
        total_files += len(source_files)

        if frame.empty:
            missing_sources.append(source_name)
            step_logger.log_step(
                run_id,
                etapa=f"contract_validation_{source_name}",
                status="EMPTY",
                volume=0,
                detalhes={"source_name": source_name, "files_found": len(source_files)},
                nivel="WARNING",
            )
            continue

        issues = validator.validate_source(source_name, frame)
        if issues:
            for issue in issues:
                step_logger.log_step(
                    run_id,
                    etapa=f"contract_validation_{source_name}",
                    status="FAILED",
                    volume=len(frame),
                    erro=issue.message,
                    detalhes=issue.details,
                    nivel="ERROR",
                )
            raise ContractValidationError(source_name, issues)

        step_logger.log_step(
            run_id,
            etapa=f"contract_validation_{source_name}",
            status="SUCCESS",
            volume=len(frame),
            detalhes={"source_name": source_name, "files_found": len(source_files)},
        )

    return total_files, source_file_counts, missing_sources


def summarize_processed_records(frames: list[pd.DataFrame]) -> int:
    total = 0
    for frame in frames:
        if isinstance(frame, pd.DataFrame):
            total += len(frame)
    return total


def process_and_load() -> None:
    setup_database()
    PASTA_SILVER.mkdir(exist_ok=True)
    process_timer = StepTimer()
    run_id: str | None = None
    source_file_counts: dict[str, int] = {}
    missing_sources: list[str] = []

    with DatabaseRepository(DB_PATH) as repo:
        tracker = EtlRunTracker(repo)
        step_logger = StructuredLogger(repo)
        run_id = tracker.start_run("main_etl")

        try:
            extraction_timer = StepTimer()
            df_raw_geral = extract_source_reports(PASTA_RAW, "zendesk_geral")
            df_raw_n1 = extract_source_reports(PASTA_RAW, "zendesk_n1")
            df_raw_audiencias = extract_source_reports(PASTA_RAW, "audiencias")
            df_raw_gss = extract_source_reports(PASTA_RAW, "gss")
            raw_frames = {
                "zendesk_geral": df_raw_geral,
                "zendesk_n1": df_raw_n1,
                "audiencias": df_raw_audiencias,
                "gss": df_raw_gss,
            }
            step_logger.log_step(
                run_id,
                etapa="extract_sources",
                status="SUCCESS",
                volume=summarize_processed_records(list(raw_frames.values())),
                tempo_etapa=extraction_timer.elapsed(),
            )

            total_files, source_file_counts, missing_sources = validate_source_contracts(
                raw_frames,
                run_id,
                step_logger,
            )

            if df_raw_geral.empty and df_raw_n1.empty and df_raw_audiencias.empty and df_raw_gss.empty:
                logging.warning("Nenhum relatorio encontrado na pasta 01_raw.")
                tracker.finish_run(
                    run_id,
                    status="PARTIAL",
                    tempo_execucao=process_timer.elapsed(),
                    qtd_registros_processados=0,
                    erro="Nenhum relatorio encontrado em 01_raw.",
                    qtd_arquivos_lidos=0,
                    qtd_fontes_processadas=0,
                )
                return

            transform_timer = StepTimer()
            df_solicitacao = transform_data(df_raw_geral, "solicitacao")
            df_notificacao = transform_data(df_raw_geral, "notificacao")
            df_n1 = transform_n1_data(df_raw_n1)
            df_audiencias = transform_audiencias_data(df_raw_audiencias)
            df_ticket_assunto = build_ticket_assunto(df_solicitacao)
            df_ticket_assunto_metrics = build_ticket_assunto_metrics(df_ticket_assunto)
            step_logger.log_step(
                run_id,
                etapa="transform_sources",
                status="SUCCESS",
                volume=summarize_processed_records(
                    [df_solicitacao, df_notificacao, df_n1, df_audiencias, df_ticket_assunto]
                ),
                tempo_etapa=transform_timer.elapsed(),
            )

            if not df_solicitacao.empty:
                df_solicitacao = deduplicate_latest(df_solicitacao, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])
            if not df_notificacao.empty:
                df_notificacao = deduplicate_latest(df_notificacao, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])
            if not df_n1.empty:
                df_n1 = deduplicate_latest(df_n1, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])
            if not df_audiencias.empty:
                df_audiencias = deduplicate_latest(df_audiencias, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])

            gss_timer = StepTimer()
            df_tickets_para_gss = pd.concat(
                [
                    df_solicitacao[["matricula", "numero_os"]] if not df_solicitacao.empty else pd.DataFrame(columns=["matricula", "numero_os"]),
                    df_notificacao[["matricula", "numero_os"]] if not df_notificacao.empty else pd.DataFrame(columns=["matricula", "numero_os"]),
                ],
                ignore_index=True,
            )
            df_raw_gss_filtrado = filter_raw_gss_for_ticket_enrichment(df_raw_gss, df_tickets_para_gss)
            df_gss = transform_gss_data(df_raw_gss_filtrado)
            if not df_gss.empty:
                df_gss = deduplicate_latest(df_gss, subset=["gss_os_id"], sort_columns=["arquivo_mtime", "gss_os_id"])
            step_logger.log_step(
                run_id,
                etapa="transform_gss",
                status="SUCCESS",
                volume=len(df_gss),
                tempo_etapa=gss_timer.elapsed(),
            )

            with sqlite3.connect(DB_PATH) as conn:
                manual_links_df = load_manual_links(conn)

            relationship_timer = StepTimer()
            relationships_df = build_ticket_relationships(
                solicitacoes_df=df_solicitacao,
                notificacoes_df=df_notificacao,
                manual_links_df=manual_links_df,
            )
            step_logger.log_step(
                run_id,
                etapa="build_relationships",
                status="SUCCESS",
                volume=len(relationships_df),
                tempo_etapa=relationship_timer.elapsed(),
            )

            if not df_solicitacao.empty:
                df_solicitacao = enrich_tickets_from_gss(
                    df_solicitacao,
                    df_gss,
                    include_os_matching=True,
                )
                if not df_ticket_assunto_metrics.empty:
                    df_solicitacao = df_solicitacao.merge(
                        df_ticket_assunto_metrics,
                        how="left",
                        on="ticket_id",
                    )
                else:
                    df_solicitacao["qtde_assuntos_ticket"] = 1
                    df_solicitacao["flag_multiplos_assuntos"] = 0

                df_solicitacao["qtde_assuntos_ticket"] = (
                    pd.to_numeric(df_solicitacao["qtde_assuntos_ticket"], errors="coerce")
                    .fillna(1)
                    .astype(int)
                )
                df_solicitacao["flag_multiplos_assuntos"] = (
                    pd.to_numeric(df_solicitacao["flag_multiplos_assuntos"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )

            if not df_notificacao.empty:
                df_notificacao = enrich_tickets_from_gss(
                    df_notificacao,
                    df_gss,
                    include_os_matching=False,
                )

            silver_timer = StepTimer()
            df_geral_silver = pd.concat([df_solicitacao, df_notificacao], ignore_index=True, sort=False)
            if not df_geral_silver.empty:
                df_geral_silver = df_geral_silver.sort_values(
                    ["data_criacao", "ticket_id"],
                    kind="stable",
                    na_position="last",
                ).copy()

            save_silver_output(df_geral_silver, SILVER_FILES["geral"])
            save_silver_output(df_n1, SILVER_FILES["n1"])
            save_silver_output(df_audiencias, SILVER_FILES["audiencias"])
            save_silver_output(df_ticket_assunto, SILVER_FILES["ticket_assunto"])
            save_silver_output(relationships_df, SILVER_FILES["vinculos"])
            cleanup_legacy_silver_files()
            step_logger.log_step(
                run_id,
                etapa="save_silver",
                status="SUCCESS",
                volume=summarize_processed_records(
                    [df_geral_silver, df_n1, df_audiencias, df_ticket_assunto, relationships_df]
                ),
                tempo_etapa=silver_timer.elapsed(),
            )

            persistence_timer = StepTimer()
            with sqlite3.connect(DB_PATH) as conn:
                df_clientes_base = pd.concat(
                    [
                        df_solicitacao[["matricula"]] if "matricula" in df_solicitacao.columns else pd.DataFrame(),
                        df_notificacao[["matricula"]] if "matricula" in df_notificacao.columns else pd.DataFrame(),
                    ],
                    ignore_index=True,
                )
                if not df_clientes_base.empty:
                    df_clientes = df_clientes_base.dropna().drop_duplicates()
                    upsert_sqlite(df_clientes, "clientes", "matricula", conn)

                df_cases_base = pd.concat(
                    [
                        df_solicitacao[["case_id", "protocolo_agenersa"]] if not df_solicitacao.empty else pd.DataFrame(),
                        df_notificacao[["case_id", "protocolo_agenersa"]] if not df_notificacao.empty else pd.DataFrame(),
                    ],
                    ignore_index=True,
                )
                if not df_cases_base.empty:
                    df_cases = df_cases_base.dropna(subset=["case_id"]).drop_duplicates()
                    upsert_sqlite(df_cases, "cases", "case_id", conn)

                if not df_n1.empty:
                    cols_n1 = [
                        "ticket_id",
                        "matricula",
                        "bloco",
                        "data_criacao",
                        "data_resolucao",
                        "status",
                        "titulo",
                        "assunto",
                        "grupo_tickets",
                        "canal_ticket",
                        "canal_origem",
                        "formulario_ticket",
                        "tipo_ticket",
                        "conversation_id",
                        "tipo_conversa",
                        "arquivo_origem",
                    ]
                    df_n1_db = prepare_for_sqlite(
                        df_n1[cols_n1].drop_duplicates(subset=["ticket_id"], keep="last"),
                        ["data_criacao", "data_resolucao"],
                    )
                    upsert_sqlite(df_n1_db, "tickets_n1", "ticket_id", conn)

                if not df_notificacao.empty:
                    cols_notificacao = [
                        "ticket_id",
                        "case_id",
                        "matricula",
                        "bloco",
                        "numero_os",
                        "data_criacao",
                        "data_resolucao",
                        "status",
                        "atribuido",
                        "titulo",
                        "assunto",
                        "tipo_conversa",
                        "tipo_solicitacao",
                        "tipo_manifestacao",
                        "resultado_tratativa",
                        "tags_ticket",
                        "grupo_tickets",
                        "superintendencia_adr",
                        "canal_origem",
                        "cpf_cliente",
                        "passou_nivel_1",
                        "canais_de_atrito",
                        "protocolo_referencia_informado",
                        "motivo_espera",
                        "prioridade_ticket",
                        "controle_interno",
                        "concessionaria",
                        "classificacao_solicitacoes",
                        "bairro",
                        "municipio",
                        "logradouro",
                        "endereco",
                        "numero_porta",
                        "complemento",
                        "telefone",
                        "nome_cliente_gss",
                        "nome_requerente_gss",
                        "nome_solicitante",
                        "email_solicitante",
                        "formulario_ticket",
                        "classificacao_notificacoes",
                        "flag_arquivado_relatorio",
                        "protocolo_procon",
                        "protocolo_defensoria",
                        "protocolo_codecon",
                        "case_jec",
                        "arquivo_origem",
                    ]
                    df_notificacao_db = prepare_for_sqlite(
                        df_notificacao[cols_notificacao].drop_duplicates(subset=["ticket_id"], keep="last"),
                        ["data_criacao", "data_resolucao"],
                    )
                    upsert_sqlite(df_notificacao_db, "tickets_notificacao", "ticket_id", conn)

                if not df_ticket_assunto.empty:
                    cols_ticket_assunto = [
                        "ticket_assunto_id",
                        "ticket_id",
                        "formulario_ticket",
                        "assunto_raw",
                        "assunto_normalizado",
                        "ordem_assunto",
                        "flag_assunto_principal",
                        "arquivo_origem",
                    ]
                    df_ticket_assunto_db = df_ticket_assunto[cols_ticket_assunto].drop_duplicates(
                        subset=["ticket_assunto_id"],
                        keep="last",
                    )
                    upsert_sqlite(df_ticket_assunto_db, "ticket_assunto", "ticket_assunto_id", conn)

                if not df_audiencias.empty:
                    cols_aud = [
                        "ticket_id",
                        "ticket_audiencia_id",
                        "ticket_relacionado_id",
                        "audiencia",
                        "data_audiencia",
                        "status_ticket",
                        "preposto_id",
                        "preposto",
                        "local_procon",
                        "tipo_audiencia",
                        "atribuido",
                        "data_reagendamento",
                        "arquivo_origem",
                    ]
                    df_audiencias_db = prepare_for_sqlite(
                        df_audiencias[cols_aud].drop_duplicates(subset=["ticket_id"], keep="last"),
                        ["data_audiencia", "data_reagendamento"],
                    )
                    upsert_sqlite(df_audiencias_db, "audiencias", "ticket_id", conn)

                if not df_solicitacao.empty:
                    relacionamento_cols = [
                        "ticket_solicitacao_id",
                        "ticket_notificacao_id",
                        "status_vinculo",
                        "criterio_vinculo",
                        "confianca_vinculo",
                        "data_entrada_reclamacao",
                        "data_criacao_solicitacao",
                        "data_criacao_notificacao",
                        "dias_defasagem_abertura",
                        "quantidade_candidatos",
                        "observacao",
                    ]
                    if not relationships_df.empty:
                        df_relacionamentos_db = relationships_df[relacionamento_cols].copy()
                        df_relacionamentos_db = prepare_for_sqlite(
                            df_relacionamentos_db,
                            ["data_entrada_reclamacao", "data_criacao_solicitacao", "data_criacao_notificacao"],
                        )
                    else:
                        df_relacionamentos_db = pd.DataFrame(columns=relacionamento_cols)

                    df_tickets = df_solicitacao.copy()
                    if not relationships_df.empty:
                        df_tickets = df_tickets.merge(
                            relationships_df[
                                [
                                    "ticket_solicitacao_id",
                                    "ticket_notificacao_id",
                                    "data_entrada_reclamacao",
                                    "data_criacao_solicitacao",
                                    "data_criacao_notificacao",
                                    "dias_defasagem_abertura",
                                    "criterio_vinculo",
                                    "confianca_vinculo",
                                    "status_vinculo",
                                ]
                            ],
                            how="left",
                            left_on="ticket_id",
                            right_on="ticket_solicitacao_id",
                        )
                    else:
                        df_tickets["ticket_solicitacao_id"] = df_tickets["ticket_id"]
                        df_tickets["ticket_notificacao_id"] = None
                        df_tickets["data_entrada_reclamacao"] = df_tickets["data_criacao"]
                        df_tickets["data_criacao_solicitacao"] = df_tickets["data_criacao"]
                        df_tickets["data_criacao_notificacao"] = None
                        df_tickets["dias_defasagem_abertura"] = None
                        df_tickets["criterio_vinculo"] = None
                        df_tickets["confianca_vinculo"] = None
                        df_tickets["status_vinculo"] = "NOTIFICACAO_NAO_CARREGADA"

                    df_tickets["ticket_solicitacao_id"] = df_tickets["ticket_id"]

                    if "data_criacao_solicitacao" not in df_tickets or df_tickets["data_criacao_solicitacao"].isna().all():
                        df_tickets["data_criacao_solicitacao"] = df_tickets["data_criacao"]
                    else:
                        df_tickets["data_criacao_solicitacao"] = df_tickets["data_criacao_solicitacao"].fillna(
                            df_tickets["data_criacao"]
                        )

                    cols_tickets = [
                        "ticket_id",
                        "case_id",
                        "matricula",
                        "bloco",
                        "numero_os",
                        "numero_os_original",
                        "numero_os_gss",
                        "gss_os_id",
                        "origem_numero_os",
                        "status_vinculo_os",
                        "score_vinculo_os",
                        "criterio_vinculo_os",
                        "data_criacao",
                        "data_resolucao",
                        "status",
                        "atribuido",
                        "titulo",
                        "assunto",
                        "tipo_conversa",
                        "tipo_solicitacao",
                        "tipo_manifestacao",
                        "resultado_tratativa",
                        "tags_ticket",
                        "grupo_tickets",
                        "superintendencia_adr",
                        "canal_origem",
                        "cpf_cliente",
                        "passou_nivel_1",
                        "canais_de_atrito",
                        "protocolo_referencia_informado",
                        "motivo_espera",
                        "prioridade_ticket",
                        "controle_interno",
                        "concessionaria",
                        "classificacao_solicitacoes",
                        "bairro",
                        "municipio",
                        "logradouro",
                        "endereco",
                        "numero_porta",
                        "complemento",
                        "telefone",
                        "nome_cliente_gss",
                        "nome_requerente_gss",
                        "nome_solicitante",
                        "email_solicitante",
                        "formulario_ticket",
                        "classificacao_notificacoes",
                        "flag_arquivado_relatorio",
                        "flag_auditoria_classificacao",
                        "motivo_auditoria_classificacao",
                        "status_auditoria_classificacao",
                        "grupo_sugerido_auditoria",
                        "tipo_solicitacao_original_auditoria",
                        "data_auditoria_classificacao",
                        "qtde_assuntos_ticket",
                        "flag_multiplos_assuntos",
                        "protocolo_procon",
                        "protocolo_defensoria",
                        "protocolo_codecon",
                        "case_jec",
                        "ticket_solicitacao_id",
                        "ticket_notificacao_id",
                        "data_entrada_reclamacao",
                        "data_criacao_solicitacao",
                        "data_criacao_notificacao",
                        "dias_defasagem_abertura",
                        "criterio_vinculo",
                        "confianca_vinculo",
                        "status_vinculo",
                    ]

                    df_tickets_db = prepare_for_sqlite(
                        df_tickets[cols_tickets].drop_duplicates(subset=["ticket_id"], keep="last"),
                        [
                            "data_criacao",
                            "data_resolucao",
                            "data_entrada_reclamacao",
                            "data_criacao_solicitacao",
                            "data_criacao_notificacao",
                        ],
                    )
                    upsert_sqlite(df_tickets_db, "tickets", "ticket_id", conn)

                    effective_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    changed_ticket_ids = persist_ticket_history(df_tickets_db, conn, run_id, effective_at)
                    sync_current_ticket_version_metadata(
                        df_tickets_db["ticket_id"].dropna().astype(int).tolist(),
                        changed_ticket_ids,
                        conn,
                        effective_at,
                    )

                    df_auditoria_classificacao = br_build_classification_audit_records(df_tickets)
                    if not df_auditoria_classificacao.empty:
                        df_auditoria_classificacao_db = prepare_for_sqlite(
                            df_auditoria_classificacao,
                            ["data_criacao", "data_resolucao"],
                        )
                        upsert_sqlite(
                            df_auditoria_classificacao_db,
                            "tickets_auditoria_classificacao",
                            "ticket_id",
                            conn,
                        )

                    df_auditoria_operacional = build_operational_audit_records(df_tickets)
                    if not df_auditoria_operacional.empty:
                        df_auditoria_operacional_db = prepare_for_sqlite(
                            df_auditoria_operacional,
                            ["data_identificacao", "data_validacao"],
                        )
                        upsert_sqlite(
                            df_auditoria_operacional_db,
                            "tickets_auditoria_operacional",
                            "auditoria_operacional_key",
                            conn,
                        )

                    if not df_relacionamentos_db.empty:
                        upsert_sqlite(df_relacionamentos_db, "ticket_relacionamentos", "ticket_solicitacao_id", conn)

                br_purge_removed_tickets(conn)
                backfill_bloco(conn)

            step_logger.log_step(
                run_id,
                etapa="persist_gold",
                status="SUCCESS",
                volume=summarize_processed_records(
                    [df_solicitacao, df_notificacao, df_n1, df_audiencias, df_ticket_assunto, relationships_df]
                ),
                tempo_etapa=persistence_timer.elapsed(),
            )

            analytics_timer = StepTimer()
            optional_output_failures: list[str] = []
            generate_daily_pre_contencioso_report(DB_PATH)
            generate_produtividade_semanal_report(DB_PATH)
            generate_base_higienizada_pre_contencioso(DB_PATH)
            try:
                generate_powerbi_semantic_exports(DB_PATH)
            except Exception as exc:
                optional_output_failures.append(f"semantic_exports: {exc}")
                step_logger.log_step(
                    run_id,
                    etapa="generate_semantic_exports",
                    status="FAILED",
                    erro=str(exc),
                    nivel="WARNING",
                )
            try:
                generate_gold_ai_ready(DB_PATH)
            except Exception as exc:
                optional_output_failures.append(f"gold_ai_ready: {exc}")
                step_logger.log_step(
                    run_id,
                    etapa="generate_ai_ready",
                    status="FAILED",
                    erro=str(exc),
                    nivel="WARNING",
                )
            step_logger.log_step(
                run_id,
                etapa="generate_outputs",
                status="SUCCESS",
                tempo_etapa=analytics_timer.elapsed(),
                detalhes={"optional_output_failures": optional_output_failures},
            )

            total_processed = summarize_processed_records(
                [df_solicitacao, df_notificacao, df_n1, df_audiencias, df_ticket_assunto, relationships_df, df_gss]
            )
            final_status = "PARTIAL" if missing_sources or optional_output_failures else "SUCCESS"
            tracker.finish_run(
                run_id,
                status=final_status,
                tempo_execucao=process_timer.elapsed(),
                qtd_registros_processados=total_processed,
                erro="; ".join(optional_output_failures) if optional_output_failures else None,
                qtd_arquivos_lidos=total_files,
                qtd_fontes_processadas=len([name for name, count in source_file_counts.items() if count > 0]),
            )
        except ContractValidationError as exc:
            step_logger.log_step(
                run_id,
                etapa="validate_contracts",
                status="FAILED",
                erro=str(exc),
                detalhes={
                    "source_name": exc.source_name,
                    "issues": [issue.details | {"message": issue.message, "code": issue.code} for issue in exc.issues],
                },
                nivel="ERROR",
            )
            tracker.finish_run(
                run_id,
                status="FAILED",
                tempo_execucao=process_timer.elapsed(),
                qtd_registros_processados=0,
                erro=str(exc),
                qtd_arquivos_lidos=sum(source_file_counts.values()) if source_file_counts else None,
                qtd_fontes_processadas=len([name for name, count in source_file_counts.items() if count > 0]),
            )
            raise
        except Exception as exc:
            step_logger.log_step(
                run_id,
                etapa="process_and_load",
                status="FAILED",
                erro=str(exc),
                nivel="ERROR",
            )
            tracker.finish_run(
                run_id,
                status="FAILED",
                tempo_execucao=process_timer.elapsed(),
                qtd_registros_processados=0,
                erro=str(exc),
                qtd_arquivos_lidos=sum(source_file_counts.values()) if source_file_counts else None,
                qtd_fontes_processadas=len([name for name, count in source_file_counts.items() if count > 0]),
            )
            raise


if __name__ == "__main__":
    process_and_load()
