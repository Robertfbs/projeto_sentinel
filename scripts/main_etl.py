import glob
import hashlib
import logging
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from create_database import setup_database
from load_database import upsert_sqlite


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


BASE_DIR = Path(__file__).resolve().parent.parent
PASTA_RAW = BASE_DIR / "01_raw"
PASTA_SILVER = BASE_DIR / "02_silver"
DB_PATH = BASE_DIR / "03_database" / "pre_contencioso.db"

PREFIXO_ARQUIVO = "ANALYTICS_BASE_TICKETS"
JANELA_MAXIMA_VINCULO_DIAS = 7

RELATORIOS = {
    "solicitacao": {
        "include": [f"{PREFIXO_ARQUIVO}*.xlsx"],
        "exclude_terms": ["NOTIFICACAO"],
    },
    "notificacao": {
        "include": [f"{PREFIXO_ARQUIVO}*NOTIFICACAO*.xlsx", "*NOTIFICACAO*.xlsx"],
        "exclude_terms": [],
    },
}

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
    config = RELATORIOS[ticket_kind]
    arquivos: list[str] = []

    for pattern in config["include"]:
        arquivos.extend(glob.glob(os.path.join(str(PASTA_RAW), pattern)))

    arquivos = sorted(set(arquivos))
    if config["exclude_terms"]:
        arquivos = [
            arquivo for arquivo in arquivos
            if not any(term.upper() in Path(arquivo).name.upper() for term in config["exclude_terms"])
        ]

    if not arquivos:
        logging.warning("Nenhum arquivo encontrado para o relatorio de %s.", ticket_kind.upper())
        return pd.DataFrame()

    dfs = []
    for arquivo in arquivos:
        df = pd.read_excel(arquivo)
        df["arquivo_origem"] = Path(arquivo).name
        dfs.append(df)

    df_final = pd.concat(dfs, ignore_index=True)
    logging.info(
        "Extracao concluida para %s: %s linhas lidas em %s arquivo(s).",
        ticket_kind.upper(),
        len(df_final),
        len(arquivos),
    )
    return df_final


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
        "numero_da_os": "numero_os",
        "resultado_tratativa_segundo_nivel": "resultado_tratativa",
        "audiencia": "audiencia",
        "tipo_de_audiencia": "tipo_audiencia",
        "data_da_audiencia_carimbo_de_data_hora": "data_audiencia",
        "preposto_name": "preposto",
        "local_do_procon": "local_procon",
        "data_de_reagendamento_carimbo_de_data_hora": "data_reagendamento",
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
        "tipo_manifestacao",
        "numero_os",
        "resultado_tratativa",
        "audiencia",
        "tipo_audiencia",
        "data_audiencia",
        "preposto",
        "local_procon",
        "data_reagendamento",
        "arquivo_origem",
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

    for column in ["data_criacao", "data_resolucao", "data_audiencia", "data_reagendamento"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["matricula"] = df["matricula"].apply(normalize_identifier)
    df["numero_os"] = df["numero_os"].apply(normalize_identifier)

    if "tipo_manifestacao" in df.columns:
        tamanho_original = len(df)
        df = df[df["tipo_manifestacao"].astype(str).str.upper() != "ANEXO"].copy()
        logging.info("Removidos %s tickets do tipo ANEXO em %s.", tamanho_original - len(df), ticket_kind.upper())

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
                "protocolo_agenersa",
                "protocolo_procon",
                "protocolo_defensoria",
                "protocolo_codecon",
                "case_jec",
            ],
        ),
        axis=1,
    )

    return df


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


def process_and_load() -> None:
    setup_database()
    PASTA_SILVER.mkdir(exist_ok=True)

    df_raw_solicitacao = extract_zendesk_reports("solicitacao")
    df_raw_notificacao = extract_zendesk_reports("notificacao")

    if df_raw_solicitacao.empty and df_raw_notificacao.empty:
        logging.warning("Nenhum relatorio encontrado na pasta 01_raw.")
        return

    df_solicitacao = transform_data(df_raw_solicitacao, "solicitacao")
    df_notificacao = transform_data(df_raw_notificacao, "notificacao")

    if not df_solicitacao.empty:
        caminho_silver_solicitacao = PASTA_SILVER / f"{PREFIXO_ARQUIVO}_processed.xlsx"
        df_solicitacao.to_excel(caminho_silver_solicitacao, index=False)
        logging.info("Arquivo Silver de solicitacao salvo: %s", caminho_silver_solicitacao.name)

    if not df_notificacao.empty:
        caminho_silver_notificacao = PASTA_SILVER / f"{PREFIXO_ARQUIVO}_NOTIFICACAO_processed.xlsx"
        df_notificacao.to_excel(caminho_silver_notificacao, index=False)
        logging.info("Arquivo Silver de notificacao salvo: %s", caminho_silver_notificacao.name)

    with sqlite3.connect(DB_PATH) as conn:
        manual_links_df = load_manual_links(conn)
        relationships_df = build_ticket_relationships(
            solicitacoes_df=df_solicitacao,
            notificacoes_df=df_notificacao,
            manual_links_df=manual_links_df,
        )

        if not relationships_df.empty:
            caminho_silver_vinculos = PASTA_SILVER / f"{PREFIXO_ARQUIVO}_VINCULOS_processed.xlsx"
            relationships_df.to_excel(caminho_silver_vinculos, index=False)
            logging.info("Arquivo Silver de vinculos salvo: %s", caminho_silver_vinculos.name)

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

        if not df_notificacao.empty:
            cols_notificacao = [
                "ticket_id",
                "case_id",
                "matricula",
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
                "protocolo_procon",
                "protocolo_defensoria",
                "protocolo_codecon",
                "case_jec",
                "arquivo_origem",
            ]
            df_notificacao_db = prepare_for_sqlite(
                df_notificacao[cols_notificacao].drop_duplicates(subset=["ticket_id"]),
                ["data_criacao", "data_resolucao"],
            )
            upsert_sqlite(df_notificacao_db, "tickets_notificacao", "ticket_id", conn)

        if not df_solicitacao.empty and "data_audiencia" in df_solicitacao.columns:
            cols_aud = [
                "ticket_id",
                "audiencia",
                "data_audiencia",
                "preposto",
                "local_procon",
                "tipo_audiencia",
                "data_reagendamento",
            ]
            cols_aud_exist = [column for column in cols_aud if column in df_solicitacao.columns]
            df_audiencias = (
                df_solicitacao.dropna(subset=["data_audiencia"])[cols_aud_exist]
                .drop_duplicates(subset=["ticket_id"])
                .copy()
            )
            if not df_audiencias.empty:
                df_audiencias = prepare_for_sqlite(df_audiencias, ["data_audiencia", "data_reagendamento"])
                upsert_sqlite(df_audiencias, "audiencias", "ticket_id", conn)

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
            df_relacionamentos_db = relationships_df[relacionamento_cols].copy()
            df_relacionamentos_db = prepare_for_sqlite(
                df_relacionamentos_db,
                ["data_entrada_reclamacao", "data_criacao_solicitacao", "data_criacao_notificacao"],
            )

            df_tickets = df_solicitacao.copy()
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
                df_tickets[cols_tickets].drop_duplicates(subset=["ticket_id"]),
                [
                    "data_criacao",
                    "data_resolucao",
                    "data_entrada_reclamacao",
                    "data_criacao_solicitacao",
                    "data_criacao_notificacao",
                ],
            )
            upsert_sqlite(df_tickets_db, "tickets", "ticket_id", conn)
            upsert_sqlite(df_relacionamentos_db, "ticket_relacionamentos", "ticket_solicitacao_id", conn)


if __name__ == "__main__":
    process_and_load()
