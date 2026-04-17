import hashlib
import logging
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analytics.relatorio_diario_pre_contencioso import generate_daily_pre_contencioso_report
from analytics.produtividade_semanal import generate_produtividade_semanal_report
from analytics.base_higienizada_pre_contencioso import generate_base_higienizada_pre_contencioso
from create_database import setup_database
from gss_matching import (
    enrich_with_gss,
    enrich_tickets_with_gss,
    filter_raw_gss_for_ticket_enrichment,
    transform_gss_data,
)
from load_database import upsert_sqlite
from pipeline_common import deduplicate_latest, derive_bloco
from pipeline_sources import extract_source_reports


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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

CLASSIFICATION_AUDIT_EXCEPTION_TICKETS = {26062949, 35478886}
CLASSIFICATION_AUDIT_TARGET_GROUPS = {
    "OCEANO CANAIS DE ATRITO N2",
    "CANAIS DE ATRITO N2",
}
CLASSIFICATION_AUDIT_SUGGESTED_GROUP = "[routing]Oceano Canais de Atrito N2"
CLASSIFICATION_AUDIT_CHANNEL_PREFIXES = {
    "AGENCIA REGULADORA",
    "CEDOC",
    "CEJUSC",
    "CODECON",
    "DEFENSORIA",
    "JEC",
    "PROCON",
}
MANUAL_GROUP_TICKET_TARGET = "[routing]Oceano Canais de Atrito N2"
MANUAL_NOTIFICATION_ANEXO_CLASSIFICATION = "Informativo::Anexo"
GROUP_TICKET_MANUAL_CORRECTION_IDS = {
    16375648, 16967132, 17307055, 17314565, 17422188, 17431001, 17668859, 17723568, 17726761,
    17920735, 18767628, 18774389, 18776665, 18777336, 18791463, 18888200, 18895792, 18897156,
    18899968, 18902013, 18906329, 18951421, 18953455, 18982186, 19023502, 19039384, 19043289,
    19048077, 19049548, 20049504, 21582808, 36814147, 39903886, 39925052, 42068221, 42082851,
}
ANEXO_MANUAL_RECLASSIFICATION_IDS = {
    29306570, 19379693, 16915599, 17420825, 17809211, 20049854, 21834657, 22252482, 22824066,
    23010012, 23099939, 23105691, 23785142, 23865809, 24116065, 24128139, 24142849, 24353117,
    24365075, 24468098, 24571091, 24646895, 24747658, 24751324, 24789903, 24790716, 24879500,
    24884791, 24891285, 24892439, 24905575, 25044931, 25047117, 25063060, 25086266, 25103184,
    25113119, 25149739, 25159291, 25208568, 25494750, 25496341, 25542385, 25564952, 25567301,
    25567677, 25693412, 25693506, 25754933, 25779628, 25902665, 25935017, 25947870, 26210089,
    26321480, 26404598, 26405794, 26461797, 26597818, 26642509, 26644401, 26653097, 26659755,
    26663172, 26853844, 26855759, 27077018, 27113391, 27135129, 27135466, 27332047, 27450786,
    27463767, 27485856, 27724071, 27748030, 27800520, 27920800, 28075352, 28147303, 28329453,
    28572356, 28670398, 28677222, 28678865, 28886764, 28985721, 29126320, 29130337, 29267413,
    29369891, 29761580, 30032223, 30039956, 30225153, 30247871, 30344167, 30522032, 30604338,
    30832869, 30939954, 31246187, 31246202, 31324735, 31377072, 31612137, 31612342, 31615944,
    32037895, 32340768, 32419740, 32574043, 32905410, 33023739, 33191792, 33353937, 33356579,
    33357202, 33528536, 33560144, 33604130, 33702394, 33785792, 34004720, 34197791, 34288261,
    34522207, 34544363, 34788134, 34810082, 34934001, 35007402, 35009274, 35012010, 35039967,
    35145202, 35616001, 35741633, 35970075, 35977403, 36104189, 36106688, 36107312, 36373384,
    36374670, 36379430, 36379431, 36384975, 36594549, 36682734, 36844624, 36941064, 36944039,
    37228827, 37231704, 37505226, 37546384, 37551416, 37629170, 37646340, 37703947, 37705052,
    37708128, 37999249, 38038155, 38368159, 38398146, 38693336, 38893252, 38934229, 39505547,
    39508512, 39663867, 39702035, 39703072, 39768656, 39772002, 39839658, 39979285, 39982115,
    40144740, 40231768, 40767639, 40775798, 41133818, 20472600, 32819501, 35601565, 35649490,
    37714282, 37714346, 37801019,
}
MANUAL_TICKET_FIELD_OVERRIDES = {
    42726461: {
        "tipo_manifestacao": "ANEXO",
    },
    42156383: {
        "grupo_tickets": "[routing]Canais de Atrito N2",
    },
    18133869: {
        "atribuido": "Erica Mara de Souza Costa",
        "grupo_tickets": MANUAL_GROUP_TICKET_TARGET,
    },
}


def normalize_column_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized


def normalize_text(value: object) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text or None


def normalize_identifier(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    return normalized.replace(".0", "")


def normalize_subject(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    normalized = re.sub(r"[^A-Z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def normalize_classification_value(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None

    if "::" in normalized:
        normalized = normalized.split("::")[-1].strip()

    normalized = re.sub(r"^\[[^\]]+\]\s*", "", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def is_governance_channel(value: object) -> bool:
    normalized = normalize_classification_value(value)
    if normalized is None:
        return False

    return any(
        normalized == channel_prefix or normalized.startswith(f"{channel_prefix} ")
        for channel_prefix in CLASSIFICATION_AUDIT_CHANNEL_PREFIXES
    )


def is_expected_n2_group(value: object) -> bool:
    return normalize_classification_value(value) in CLASSIFICATION_AUDIT_TARGET_GROUPS


def apply_ticket_manual_overrides(df: pd.DataFrame, ticket_kind: str) -> pd.DataFrame:
    if df.empty:
        return df

    frame = df.copy()
    ticket_ids = pd.to_numeric(frame["ticket_id"], errors="coerce")
    override_count = 0

    group_mask = ticket_ids.isin(GROUP_TICKET_MANUAL_CORRECTION_IDS)
    if group_mask.any():
        if "grupo_tickets" not in frame.columns:
            frame["grupo_tickets"] = None
        frame.loc[group_mask, "grupo_tickets"] = MANUAL_GROUP_TICKET_TARGET
        override_count += int(group_mask.sum())

    anexo_mask = ticket_ids.isin(ANEXO_MANUAL_RECLASSIFICATION_IDS)
    if anexo_mask.any():
        if ticket_kind == "solicitacao":
            if "tipo_manifestacao" not in frame.columns:
                frame["tipo_manifestacao"] = None
            frame.loc[anexo_mask, "tipo_manifestacao"] = "ANEXO"
        elif ticket_kind == "notificacao":
            if "classificacao_notificacoes" not in frame.columns:
                frame["classificacao_notificacoes"] = None
            frame.loc[anexo_mask, "classificacao_notificacoes"] = MANUAL_NOTIFICATION_ANEXO_CLASSIFICATION
        override_count += int(anexo_mask.sum())

    for ticket_id, overrides in MANUAL_TICKET_FIELD_OVERRIDES.items():
        mask = ticket_ids == ticket_id
        if not mask.any():
            continue

        for column, value in overrides.items():
            if column not in frame.columns:
                frame[column] = None
            frame.loc[mask, column] = value
        override_count += int(mask.sum())

    if override_count:
        tipo_manifestacao_norm = frame["tipo_manifestacao"].apply(normalize_text)
        classificacao_notificacoes_norm = (
            frame["classificacao_notificacoes"].apply(normalize_text)
            if "classificacao_notificacoes" in frame.columns
            else pd.Series([None] * len(frame), index=frame.index)
        )
        frame["flag_arquivado_relatorio"] = (
            (tipo_manifestacao_norm == "ANEXO")
            | (
                classificacao_notificacoes_norm.fillna("").str.contains("INFORMATIVO", na=False)
                & classificacao_notificacoes_norm.fillna("").str.contains("ANEXO", na=False)
            )
        ).astype(int)
        logging.info("Aplicados overrides manuais de ticket em %s registro(s).", override_count)

    return frame


def first_not_null(row: pd.Series, columns: list[str]) -> str | None:
    for column in columns:
        value = row.get(column)
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return None


def serialize_datetime(value: object) -> str | None:
    if pd.isna(value):
        return None

    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None

    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


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

    tipo_manifestacao_norm = df["tipo_manifestacao"].apply(normalize_text) if "tipo_manifestacao" in df.columns else pd.Series([None] * len(df), index=df.index)
    classificacao_notificacoes_norm = (
        df["classificacao_notificacoes"].apply(normalize_text)
        if "classificacao_notificacoes" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    df["flag_arquivado_relatorio"] = (
        (tipo_manifestacao_norm == "ANEXO")
        | (
            classificacao_notificacoes_norm.fillna("").str.contains("INFORMATIVO", na=False)
            & classificacao_notificacoes_norm.fillna("").str.contains("ANEXO", na=False)
        )
    ).astype(int)
    logging.info(
        "Marcados %s tickets para arquivamento logico em %s.",
        int(df["flag_arquivado_relatorio"].sum()),
        ticket_kind.upper(),
    )

    df = apply_ticket_manual_overrides(df, ticket_kind)

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
        df = apply_classification_audit_rules(df)

    return df


def apply_classification_audit_rules(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    frame = df.copy()
    required_audit_columns = {
        "flag_auditoria_classificacao": 0,
        "motivo_auditoria_classificacao": None,
        "status_auditoria_classificacao": None,
        "grupo_sugerido_auditoria": None,
        "tipo_solicitacao_original_auditoria": None,
        "data_auditoria_classificacao": None,
        "origem_regra_auditoria": None,
        "canal_normalizado_auditoria": None,
        "observacao_auditoria_classificacao": None,
    }
    for column, default in required_audit_columns.items():
        if column not in frame.columns:
            frame[column] = default

    ticket_ids = pd.to_numeric(frame["ticket_id"], errors="coerce")
    specific_exception_mask = ticket_ids.isin(CLASSIFICATION_AUDIT_EXCEPTION_TICKETS)

    governance_channel_mask = frame["tipo_solicitacao"].apply(is_governance_channel)
    unexpected_group_mask = ~frame["grupo_tickets"].apply(is_expected_n2_group)
    active_metric_mask = (
        pd.to_numeric(frame["flag_arquivado_relatorio"], errors="coerce")
        .fillna(0)
        .astype(int)
        == 0
    )
    automatic_audit_mask = (
        governance_channel_mask
        & unexpected_group_mask
        & ~specific_exception_mask
        & active_metric_mask
    )
    audit_mask = specific_exception_mask | automatic_audit_mask

    frame.loc[:, "flag_auditoria_classificacao"] = 0
    frame.loc[:, "motivo_auditoria_classificacao"] = None
    frame.loc[:, "status_auditoria_classificacao"] = None
    frame.loc[:, "grupo_sugerido_auditoria"] = None
    frame.loc[:, "tipo_solicitacao_original_auditoria"] = None
    frame.loc[:, "data_auditoria_classificacao"] = None
    frame.loc[:, "origem_regra_auditoria"] = None
    frame.loc[:, "canal_normalizado_auditoria"] = None
    frame.loc[:, "observacao_auditoria_classificacao"] = None

    if not audit_mask.any():
        return frame

    original_tipo_solicitacao = frame.loc[audit_mask, "tipo_solicitacao"].copy()
    frame.loc[audit_mask, "flag_auditoria_classificacao"] = 1
    frame.loc[audit_mask, "flag_arquivado_relatorio"] = 1
    frame.loc[audit_mask, "status_auditoria_classificacao"] = "PENDENTE_VALIDACAO"
    frame.loc[audit_mask, "data_auditoria_classificacao"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    frame.loc[audit_mask, "tipo_solicitacao_original_auditoria"] = original_tipo_solicitacao
    frame.loc[audit_mask, "canal_normalizado_auditoria"] = original_tipo_solicitacao.apply(
        normalize_classification_value
    )

    frame.loc[specific_exception_mask, "tipo_solicitacao"] = "Reclame Aqui"
    frame.loc[specific_exception_mask, "origem_regra_auditoria"] = "EXCECAO_OPERACIONAL"
    frame.loc[specific_exception_mask, "motivo_auditoria_classificacao"] = "EXCECAO_OPERACIONAL_RECLAME_AQUI"
    frame.loc[
        specific_exception_mask,
        "observacao_auditoria_classificacao",
    ] = "Ticket encerrado incorretamente como canal de atrito no Zendesk; segregado para auditoria."

    frame.loc[automatic_audit_mask, "origem_regra_auditoria"] = "REGRA_AUTOMATICA_GRUPO_CANAL"
    frame.loc[automatic_audit_mask, "motivo_auditoria_classificacao"] = (
        "POSSIVEL_CLASSIFICACAO_INCORRETA_GRUPO_CANAL"
    )
    frame.loc[automatic_audit_mask, "grupo_sugerido_auditoria"] = CLASSIFICATION_AUDIT_SUGGESTED_GROUP
    frame.loc[
        automatic_audit_mask,
        "observacao_auditoria_classificacao",
    ] = "Validar grupo do ticket antes de eventual reclassificacao operacional."

    logging.info(
        "Tickets segregados para auditoria de classificacao: %s excecao operacional, %s regra automatica.",
        int(specific_exception_mask.sum()),
        int(automatic_audit_mask.sum()),
    )
    return frame


def build_classification_audit_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "flag_auditoria_classificacao" not in df.columns:
        return pd.DataFrame()

    audit_df = df[pd.to_numeric(df["flag_auditoria_classificacao"], errors="coerce").fillna(0).astype(int) == 1].copy()
    if audit_df.empty:
        return pd.DataFrame()

    records = pd.DataFrame(
        {
            "ticket_id": audit_df["ticket_id"],
            "origem_regra": audit_df["origem_regra_auditoria"],
            "status_auditoria": audit_df["status_auditoria_classificacao"],
            "motivo_auditoria": audit_df["motivo_auditoria_classificacao"],
            "tipo_solicitacao_original": audit_df["tipo_solicitacao_original_auditoria"],
            "tipo_solicitacao_atual": audit_df["tipo_solicitacao"],
            "grupo_tickets": audit_df["grupo_tickets"],
            "grupo_sugerido": audit_df["grupo_sugerido_auditoria"],
            "canal_normalizado": audit_df["canal_normalizado_auditoria"],
            "data_criacao": audit_df["data_criacao"],
            "data_resolucao": audit_df["data_resolucao"],
            "atribuido": audit_df["atribuido"],
            "titulo": audit_df["titulo"],
            "observacao": audit_df["observacao_auditoria_classificacao"],
            "arquivo_origem": audit_df["arquivo_origem"],
        }
    )
    return records.drop_duplicates(subset=["ticket_id"], keep="last")


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
    if output_path.exists():
        output_path.unlink()
    temp_path.replace(output_path)
    logging.info("Arquivo Silver salvo: %s", output_path.name)


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


def process_and_load() -> None:
    setup_database()
    PASTA_SILVER.mkdir(exist_ok=True)

    df_raw_geral = extract_source_reports(PASTA_RAW, "zendesk_geral")
    df_raw_n1 = extract_source_reports(PASTA_RAW, "zendesk_n1")
    df_raw_audiencias = extract_source_reports(PASTA_RAW, "audiencias")
    df_raw_gss = extract_source_reports(PASTA_RAW, "gss")

    if df_raw_geral.empty and df_raw_n1.empty and df_raw_audiencias.empty and df_raw_gss.empty:
        logging.warning("Nenhum relatorio encontrado na pasta 01_raw.")
        return

    df_solicitacao = transform_data(df_raw_geral, "solicitacao")
    df_notificacao = transform_data(df_raw_geral, "notificacao")
    df_n1 = transform_n1_data(df_raw_n1)
    df_audiencias = transform_audiencias_data(df_raw_audiencias)
    df_ticket_assunto = build_ticket_assunto(df_solicitacao)
    df_ticket_assunto_metrics = build_ticket_assunto_metrics(df_ticket_assunto)

    if not df_solicitacao.empty:
        df_solicitacao = deduplicate_latest(df_solicitacao, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])

    if not df_notificacao.empty:
        df_notificacao = deduplicate_latest(df_notificacao, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])

    if not df_n1.empty:
        df_n1 = deduplicate_latest(df_n1, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])

    if not df_audiencias.empty:
        df_audiencias = deduplicate_latest(df_audiencias, subset=["ticket_id"], sort_columns=["arquivo_mtime", "ticket_id"])

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

    with sqlite3.connect(DB_PATH) as conn:
        manual_links_df = load_manual_links(conn)

    relationships_df = build_ticket_relationships(
        solicitacoes_df=df_solicitacao,
        notificacoes_df=df_notificacao,
        manual_links_df=manual_links_df,
    )

    if not df_solicitacao.empty:
        df_solicitacao = enrich_with_gss(df_solicitacao, df_gss)
        df_solicitacao = enrich_tickets_with_gss(df_solicitacao, df_gss)
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
        df_notificacao = enrich_with_gss(df_notificacao, df_gss)

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

            df_auditoria_classificacao = build_classification_audit_records(df_tickets)
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

            if not df_relacionamentos_db.empty:
                upsert_sqlite(df_relacionamentos_db, "ticket_relacionamentos", "ticket_solicitacao_id", conn)

        backfill_bloco(conn)

    generate_daily_pre_contencioso_report(DB_PATH)
    generate_produtividade_semanal_report(DB_PATH)
    generate_base_higienizada_pre_contencioso(DB_PATH)


if __name__ == "__main__":
    process_and_load()
