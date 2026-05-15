from __future__ import annotations

import logging
import hashlib
import re
import sqlite3
from datetime import datetime

import pandas as pd

from pipeline_common import normalize_text


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
PRIVATE_ARCHIVE_GROUPS = {
    "[INTERNAL]TICKET PRIVADO OCEANO CANAIS DE ATRITO",
}
MANUAL_ARCHIVE_TICKET_IDS = {
    16153239,
    16272029,
    17661555,
    22471671,
}
GROUP_TICKET_MANUAL_CORRECTION_IDS = {
    16375648, 16967132, 17307055, 17314565, 17422188, 17431001, 17668859, 17723568, 17726761,
    17920735, 18767628, 18774389, 18776665, 18777336, 18791463, 18888200, 18895792, 18897156,
    18899968, 18902013, 18906329, 18951421, 18953455, 18982186, 19023502, 19039384, 19043289,
    19048077, 19049548, 20049504, 21582808, 36814147, 39903886, 39925052, 42068221, 42082851,
    17746470, 17749953, 17753513, 17758547, 24142547, 24653274, 25841195, 28438768, 28462584,
    31233932, 35193872, 38141384, 40851024, 43296042, 43809573, 43835771, 44397298, 44478288,
}
REMOVED_TICKET_IDS = {
    18948864,
    25127312,
    25127616,
    25128363,
    25130165,
    25492069,
    25835503,
    26062949,
    32872895,
    34326542,
    35478886,
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
    42726461: {"tipo_manifestacao": "ANEXO"},
    42156383: {"grupo_tickets": "[routing]Canais de Atrito N2"},
    18133869: {
        "atribuido": "Erica Mara de Souza Costa",
        "grupo_tickets": MANUAL_GROUP_TICKET_TARGET,
    },
}


def normalize_classification_value(value: object) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    if "::" in normalized:
        normalized = normalized.split("::")[-1].strip()
    normalized = re.sub(r"^\[[^\]]+\]\s*", "", normalized).strip()
    normalized = normalized.strip()
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
    normalized = normalize_classification_value(value)
    return normalized in CLASSIFICATION_AUDIT_TARGET_GROUPS


def build_archive_flag(df: pd.DataFrame) -> pd.Series:
    ticket_ids = (
        pd.to_numeric(df["ticket_id"], errors="coerce")
        if "ticket_id" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    tipo_manifestacao_norm = (
        df["tipo_manifestacao"].apply(normalize_text)
        if "tipo_manifestacao" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    classificacao_notificacoes_norm = (
        df["classificacao_notificacoes"].apply(normalize_text)
        if "classificacao_notificacoes" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    grupo_tickets_norm = (
        df["grupo_tickets"].apply(normalize_text)
        if "grupo_tickets" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )

    return (
        (tipo_manifestacao_norm == "ANEXO")
        | (
            classificacao_notificacoes_norm.fillna("").str.contains("INFORMATIVO", na=False)
            & classificacao_notificacoes_norm.fillna("").str.contains("ANEXO", na=False)
        )
        | grupo_tickets_norm.isin(PRIVATE_ARCHIVE_GROUPS)
        | ticket_ids.isin(MANUAL_ARCHIVE_TICKET_IDS)
    ).astype(int)


def filter_removed_tickets(
    df: pd.DataFrame,
    *,
    ticket_column: str = "ticket_id",
    context: str = "",
) -> pd.DataFrame:
    if df.empty or ticket_column not in df.columns:
        return df

    frame = df.copy()
    ticket_ids = pd.to_numeric(frame[ticket_column], errors="coerce")
    removed_mask = ticket_ids.isin(REMOVED_TICKET_IDS)
    if removed_mask.any():
        logging.info(
            "Removidos %s ticket(s) fora do escopo em %s.",
            int(removed_mask.sum()),
            context or ticket_column,
        )
        frame = frame.loc[~removed_mask].copy()
    return frame


def purge_removed_tickets(conn: sqlite3.Connection) -> None:
    removed_ids = sorted(REMOVED_TICKET_IDS)
    if not removed_ids:
        return

    placeholders = ",".join("?" for _ in removed_ids)
    cursor = conn.cursor()
    statements = [
        ("DELETE FROM ticket_assunto WHERE ticket_id IN ({ids})", removed_ids),
        (
            "DELETE FROM ticket_relacionamentos WHERE ticket_solicitacao_id IN ({ids}) OR ticket_notificacao_id IN ({ids})",
            removed_ids * 2,
        ),
        (
            "DELETE FROM ticket_vinculos_manuais WHERE ticket_solicitacao_id IN ({ids}) OR ticket_notificacao_id IN ({ids})",
            removed_ids * 2,
        ),
        ("DELETE FROM tickets_auditoria_classificacao WHERE ticket_id IN ({ids})", removed_ids),
        ("DELETE FROM tickets_auditoria_operacional WHERE ticket_id IN ({ids})", removed_ids),
        ("DELETE FROM tickets_historico WHERE ticket_id IN ({ids})", removed_ids),
        (
            "DELETE FROM audiencias WHERE ticket_id IN ({ids}) OR ticket_relacionado_id IN ({ids}) OR ticket_audiencia_id IN ({ids})",
            removed_ids * 3,
        ),
        ("DELETE FROM tickets WHERE ticket_id IN ({ids})", removed_ids),
        ("DELETE FROM tickets_notificacao WHERE ticket_id IN ({ids})", removed_ids),
        ("DELETE FROM tickets_n1 WHERE ticket_id IN ({ids})", removed_ids),
    ]

    total_deleted = 0
    for sql_template, params in statements:
        sql = sql_template.format(ids=placeholders)
        cursor.execute(sql, params)
        total_deleted += cursor.rowcount if cursor.rowcount > 0 else 0

    conn.commit()
    logging.info(
        "Purge governado de tickets fora do escopo concluido: %s registro(s) removido(s) em tabelas derivadas.",
        total_deleted,
    )


def purge_stale_audit_records(conn: sqlite3.Connection) -> None:
    """Remove pendencias de auditoria que nao existem mais no estado atual da Gold.

    As tabelas de auditoria sao alimentadas por UPSERT. Quando um ticket deixa de
    exigir auditoria em uma carga posterior, ele nao volta a aparecer no dataframe
    de auditoria e, sem esta reconciliacao, o registro antigo permaneceria como
    PENDENTE_VALIDACAO.
    """

    cursor = conn.cursor()
    statements = [
        """
        DELETE FROM tickets_auditoria_classificacao
        WHERE UPPER(TRIM(COALESCE(status_auditoria, ''))) = 'PENDENTE_VALIDACAO'
          AND NOT EXISTS (
              SELECT 1
              FROM tickets AS t
              WHERE t.ticket_id = tickets_auditoria_classificacao.ticket_id
                AND COALESCE(t.flag_auditoria_classificacao, 0) = 1
          )
        """,
        """
        DELETE FROM tickets_auditoria_operacional
        WHERE UPPER(TRIM(COALESCE(status_validacao, ''))) = 'PENDENTE_VALIDACAO'
          AND NOT EXISTS (
              SELECT 1
              FROM tickets AS t
              WHERE t.ticket_id = tickets_auditoria_operacional.ticket_id
                AND COALESCE(t.flag_auditoria_classificacao, 0) = 1
          )
        """,
    ]

    total_deleted = 0
    for sql in statements:
        cursor.execute(sql)
        total_deleted += cursor.rowcount if cursor.rowcount > 0 else 0

    if not conn.in_transaction:
        conn.commit()

    if total_deleted:
        logging.info(
            "Reconciliacao de auditoria removeu %s pendencia(s) obsoleta(s).",
            total_deleted,
        )


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
        frame["flag_arquivado_relatorio"] = build_archive_flag(frame)
        logging.info("Aplicados overrides manuais de ticket em %s registro(s).", override_count)
    return frame


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
    # Inicializa as colunas de auditoria sempre (sobrescreve valores anteriores
    # de uma execucao previa), garantindo idempotencia da regra.
    for column, default in required_audit_columns.items():
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
    automatic_audit_mask = governance_channel_mask & unexpected_group_mask & ~specific_exception_mask & active_metric_mask
    audit_mask = specific_exception_mask | automatic_audit_mask

    if not audit_mask.any():
        return frame

    audit_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    original_tipo_solicitacao = frame.loc[audit_mask, "tipo_solicitacao"].copy()
    frame.loc[audit_mask, "flag_auditoria_classificacao"] = 1
    frame.loc[audit_mask, "flag_arquivado_relatorio"] = 1
    frame.loc[audit_mask, "status_auditoria_classificacao"] = "PENDENTE_VALIDACAO"
    frame.loc[audit_mask, "data_auditoria_classificacao"] = audit_timestamp
    frame.loc[audit_mask, "tipo_solicitacao_original_auditoria"] = original_tipo_solicitacao
    frame.loc[audit_mask, "canal_normalizado_auditoria"] = original_tipo_solicitacao.apply(normalize_classification_value)

    frame.loc[specific_exception_mask, "tipo_solicitacao"] = "Reclame Aqui"
    frame.loc[specific_exception_mask, "origem_regra_auditoria"] = "EXCECAO_OPERACIONAL"
    frame.loc[specific_exception_mask, "motivo_auditoria_classificacao"] = "EXCECAO_OPERACIONAL_RECLAME_AQUI"
    frame.loc[specific_exception_mask, "observacao_auditoria_classificacao"] = (
        "Ticket encerrado incorretamente como canal de atrito no Zendesk; segregado para auditoria."
    )

    frame.loc[automatic_audit_mask, "origem_regra_auditoria"] = "REGRA_AUTOMATICA_GRUPO_CANAL"
    frame.loc[automatic_audit_mask, "motivo_auditoria_classificacao"] = (
        "POSSIVEL_CLASSIFICACAO_INCORRETA_GRUPO_CANAL"
    )
    frame.loc[automatic_audit_mask, "grupo_sugerido_auditoria"] = CLASSIFICATION_AUDIT_SUGGESTED_GROUP
    frame.loc[automatic_audit_mask, "observacao_auditoria_classificacao"] = (
        "Validar grupo do ticket antes de eventual reclassificacao operacional."
    )

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


def build_operational_audit_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "flag_auditoria_classificacao" not in df.columns:
        return pd.DataFrame()
    audit_df = df[pd.to_numeric(df["flag_auditoria_classificacao"], errors="coerce").fillna(0).astype(int) == 1].copy()
    if audit_df.empty:
        return pd.DataFrame()
    _key_series = (
        audit_df["ticket_id"].astype("Int64").astype(str)
        + "|"
        + audit_df["origem_regra_auditoria"].astype(str)
        + "|"
        + audit_df["motivo_auditoria_classificacao"].astype(str)
    )
    return pd.DataFrame(
        {
            "auditoria_operacional_key": _key_series.map(
                lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
            ),
            "ticket_id": audit_df["ticket_id"],
            "origem_regra": audit_df["origem_regra_auditoria"].fillna("AUDITORIA_CLASSIFICACAO"),
            "tipo_inconsistencia": audit_df["motivo_auditoria_classificacao"].fillna("CLASSIFICACAO_SUSPEITA"),
            "descricao_inconsistencia": audit_df["observacao_auditoria_classificacao"],
            "status_validacao": "PENDENTE_VALIDACAO",
            "data_identificacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_validacao": None,
            "validado_por": None,
            "acao_tomada": None,
            "observacao": audit_df["titulo"],
        }
    ).drop_duplicates(subset=["ticket_id", "tipo_inconsistencia"], keep="last")
