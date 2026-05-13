import logging

import pandas as pd

from pipeline_common import (
    deduplicate_latest,
    derive_bloco,
    ensure_columns,
    first_not_null,
    normalize_column_name,
    normalize_identifier,
    normalize_subject,
    normalize_text,
    normalize_token_set,
)


GSS_REQUIRED_COLUMNS = [
    "numero_os",
    "ano_os",
    "matricula",
    "data_emissao",
    "servico_executado",
    "nome_cliente",
    "nome_requerente",
    "telefone",
    "endereco_requerente",
    "nome_logradouro",
    "numero_porta",
    "complemento",
    "bairro",
    "municipio",
    "data_agendamento",
    "data_impressao",
    "previsao_conclusao",
    "data_execucao",
    "executor",
    "entrada_setor",
    "data_pedido",
    "atendente",
    "solicitacao_associada",
    "tipo_solicitacao_gss",
    "arquivo_origem",
    "arquivo_mtime",
]

# Calibracao do matching automatico GSS x Zendesk.
# Origem: validacao com a area de pre-contencioso (out/2025).
GSS_MATCH_MIN_SCORE = 0.55      # score minimo para considerar match valido
GSS_MATCH_MIN_MARGIN = 0.10     # margem absoluta minima sobre o segundo colocado
GSS_WEIGHT_DATE = 0.50
GSS_WEIGHT_SERVICE = 0.35
GSS_WEIGHT_STATUS = 0.15
# Bandas de proximidade temporal entre data do ticket e da OS (em dias).
GSS_DATE_SCORE_BANDS: tuple[tuple[int, float], ...] = (
    (3, 1.0),
    (7, 0.85),
    (15, 0.65),
    (30, 0.40),
    (60, 0.20),
)


GSS_ENRICHMENT_COLUMN_MAP = {
    "bairro": "bairro",
    "municipio": "municipio",
    "nome_logradouro": "logradouro",
    "endereco_requerente": "endereco",
    "numero_porta": "numero_porta",
    "complemento": "complemento",
    "telefone": "telefone",
    "nome_cliente": "nome_cliente_gss",
    "nome_requerente": "nome_requerente_gss",
}

GSS_COLUMN_RENAME_CANDIDATES = {
    "no_da_o_s": "numero_os",
    "ano_da_o_s": "ano_os",
    "matricula": "matricula",
    "dt_emissao": "data_emissao",
    "servico_executado": "servico_executado",
    "nome_cliente": "nome_cliente",
    "nome_requerente": "nome_requerente",
    "telefone": "telefone",
    "endereco_do_requerente": "endereco_requerente",
    "nome_logradouro": "nome_logradouro",
    "numero_da_porta": "numero_porta",
    "desc_complemento": "complemento",
    "nome_do_bairro": "bairro",
    "nome_da_localidade": "municipio",
    "dt_agendamento": "data_agendamento",
    "dt_impressao": "data_impressao",
    "prev_conclusao": "previsao_conclusao",
    "dt_execucao": "data_execucao",
    "executor": "executor",
    "entrada_no_setor": "entrada_setor",
    "data_pedido": "data_pedido",
    "atendente": "atendente",
    "solicitacao_associada": "solicitacao_associada",
    "tipo_de_solicitacao": "tipo_solicitacao_gss",
}


def _ensure_columns_with_defaults(
    df: pd.DataFrame,
    defaults: dict[str, object],
) -> pd.DataFrame:
    prepared = df.copy()
    for column, default in defaults.items():
        if column not in prepared.columns:
            prepared[column] = default
    return prepared


def _join_text_parts(values: list[object]) -> str:
    return " ".join(
        str(value).strip()
        for value in values
        if pd.notna(value) and str(value).strip()
    )


def filter_raw_gss_for_ticket_enrichment(df_raw_gss: pd.DataFrame, tickets_df: pd.DataFrame) -> pd.DataFrame:
    if df_raw_gss.empty or tickets_df.empty:
        return pd.DataFrame()

    frame = df_raw_gss.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    normalized_columns = {normalize_column_name(column): column for column in frame.columns}
    matricula_column = normalized_columns.get("matricula")
    if not matricula_column:
        logging.warning("Coluna de matricula nao encontrada na base GSS. Filtro de enriquecimento nao aplicado.")
        return frame

    # Aplica a mesma normalizacao usada na coluna do GSS para evitar
    # mismatch por sufixo `.0`, espacos ou case.
    matriculas_alvo = {
        normalized
        for normalized in (
            normalize_identifier(value) for value in tickets_df["matricula"].dropna().tolist()
        )
        if normalized
    }
    if not matriculas_alvo:
        logging.info("Nenhuma matricula encontrada nos tickets para enriquecimento via GSS.")
        return frame.iloc[0:0].copy()

    frame[matricula_column] = frame[matricula_column].apply(normalize_identifier)
    filtered = frame[frame[matricula_column].isin(matriculas_alvo)].copy()
    logging.info(
        "Base GSS filtrada para enriquecimento: %s -> %s linhas (%s matriculas alvo).",
        len(df_raw_gss),
        len(filtered),
        len(matriculas_alvo),
    )
    return filtered


def enrich_with_gss(
    df_tickets: pd.DataFrame,
    df_gss: pd.DataFrame,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    if df_tickets.empty:
        return df_tickets

    active_column_map = column_map or GSS_ENRICHMENT_COLUMN_MAP
    enriched = _ensure_columns_with_defaults(
        df_tickets,
        {target_column: None for target_column in active_column_map.values()},
    )

    if df_gss.empty:
        logging.warning("Base GSS nao encontrada na carga atual. Enriquecimento complementar por matricula nao executado.")
        return enriched

    gss_context = build_gss_context(df_gss, active_column_map)
    if gss_context.empty:
        logging.warning("Base GSS sem contexto utilizavel por matricula. Enriquecimento complementar nao executado.")
        return enriched

    total_updates = 0
    context_by_matricula = gss_context.set_index("matricula")

    for source_column, target_column in active_column_map.items():
        lookup = context_by_matricula[source_column]
        missing_mask = (
            enriched[target_column].isna()
            | enriched[target_column].astype("string").str.strip().isin(["", "<NA>", "nan", "None"])
        )
        mapped_values = enriched.loc[missing_mask, "matricula"].map(lookup)
        fill_mask = mapped_values.notna() & mapped_values.astype("string").str.strip().ne("")
        if fill_mask.any():
            indices_to_fill = mapped_values.loc[fill_mask].index
            enriched.loc[indices_to_fill, target_column] = mapped_values.loc[fill_mask]
            total_updates += int(fill_mask.sum())

    logging.info("Enriquecimento complementar via GSS concluido: %s campos preenchidos.", total_updates)
    return enriched


def enrich_tickets_from_gss(
    tickets_df: pd.DataFrame,
    gss_df: pd.DataFrame,
    *,
    include_os_matching: bool,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    enriched = enrich_with_gss(tickets_df, gss_df, column_map=column_map)
    if include_os_matching:
        return enrich_tickets_with_gss(enriched, gss_df)
    return enriched


def build_gss_context(df_gss: pd.DataFrame, column_map: dict[str, str] | None = None) -> pd.DataFrame:
    if df_gss.empty:
        return pd.DataFrame(columns=["matricula"])

    active_column_map = column_map or GSS_ENRICHMENT_COLUMN_MAP
    source_columns = [column for column in active_column_map.keys() if column in df_gss.columns]
    if not source_columns:
        return pd.DataFrame(columns=["matricula"])

    context = df_gss.copy()
    for column in source_columns:
        context[column] = (
            context[column]
            .astype("string")
            .str.strip()
            .replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA, "None": pd.NA})
        )

    context["score_contexto"] = context[source_columns].notna().sum(axis=1)
    context = context.sort_values(
        ["score_contexto", "data_emissao", "data_execucao", "data_agendamento", "gss_os_id"],
        ascending=[False, False, False, False, False],
        kind="stable",
        na_position="last",
    ).copy()
    context = context.drop_duplicates(subset=["matricula"], keep="first").copy()
    return context[["matricula", *source_columns]]


def transform_gss_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=GSS_REQUIRED_COLUMNS + ["gss_os_id", "status_os_gss", "servico_normalizado"])

    frame = df.copy()
    frame.columns = [str(column).strip() for column in frame.columns]

    rename_map = {
        column: GSS_COLUMN_RENAME_CANDIDATES[normalize_column_name(column)]
        for column in frame.columns
        if normalize_column_name(column) in GSS_COLUMN_RENAME_CANDIDATES
    }
    frame = frame.rename(columns=rename_map)
    frame = ensure_columns(frame, GSS_REQUIRED_COLUMNS)

    for column in [
        "data_emissao",
        "data_agendamento",
        "data_impressao",
        "previsao_conclusao",
        "data_execucao",
        "entrada_setor",
    ]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")

    frame["matricula"] = frame["matricula"].map(normalize_identifier)
    frame["numero_os"] = frame["numero_os"].map(normalize_identifier)
    frame["ano_os"] = frame["ano_os"].map(normalize_identifier)
    frame["bloco"] = frame["matricula"].map(derive_bloco)

    # Vetorizado: combina ano-numero quando ano existir; do contrario usa numero_os.
    _ano_str = frame["ano_os"].fillna("").astype(str)
    _num_str = frame["numero_os"].fillna("").astype(str)
    _has_ano = _ano_str.str.len() > 0
    _has_num = _num_str.str.len() > 0
    frame["gss_os_id"] = frame["numero_os"]
    _both = _has_ano & _has_num
    frame.loc[_both, "gss_os_id"] = (_ano_str + "-" + _num_str)[_both]

    frame["status_os_gss"] = _derive_status_os_vectorized(frame)
    frame["servico_normalizado"] = (
        frame[["servico_executado", "solicitacao_associada", "tipo_solicitacao_gss"]]
        .apply(lambda row: normalize_subject(_join_text_parts(row.tolist())), axis=1)
    )

    frame = frame.dropna(subset=["numero_os"]).copy()
    frame = deduplicate_latest(frame, subset=["gss_os_id"], sort_columns=["arquivo_mtime", "gss_os_id"])
    # Pre-computa tokens da OS uma vez para evitar recalculo no loop por ticket.
    if not frame.empty:
        frame["_service_tokens"] = frame["servico_normalizado"].map(normalize_token_set)
    return frame


def _derive_status_os(row: pd.Series) -> str | None:
    if pd.notna(row.get("data_execucao")):
        return "EXECUTADA"
    if pd.notna(row.get("previsao_conclusao")):
        if row["previsao_conclusao"] < pd.Timestamp.now().normalize():
            return "PENDENTE_VENCIDA"
        return "PENDENTE"
    if pd.notna(row.get("data_emissao")):
        return "PENDENTE"
    return None


def _derive_status_os_vectorized(frame: pd.DataFrame) -> pd.Series:
    """Versao vetorizada de ``_derive_status_os`` (ordem de prioridade preservada)."""
    today = pd.Timestamp.now().normalize()
    has_exec = frame["data_execucao"].notna()
    has_prev = frame["previsao_conclusao"].notna()
    has_emis = frame["data_emissao"].notna()
    prev_vencida = has_prev & (frame["previsao_conclusao"] < today)

    status = pd.Series([None] * len(frame), index=frame.index, dtype="object")
    status.loc[has_emis] = "PENDENTE"
    status.loc[has_prev & ~prev_vencida] = "PENDENTE"
    status.loc[prev_vencida] = "PENDENTE_VENCIDA"
    status.loc[has_exec] = "EXECUTADA"
    return status


def enrich_tickets_with_gss(tickets_df: pd.DataFrame, gss_df: pd.DataFrame) -> pd.DataFrame:
    if tickets_df.empty:
        return tickets_df

    enriched = _ensure_columns_with_defaults(
        tickets_df,
        {
            "numero_os_original": None,
            "numero_os_gss": None,
            "gss_os_id": None,
            "origem_numero_os": None,
            "status_vinculo_os": None,
            "score_vinculo_os": None,
            "criterio_vinculo_os": None,
        },
    )

    enriched["numero_os_original"] = enriched["numero_os"].map(normalize_identifier)

    if gss_df.empty:
        logging.warning("Base GSS nao encontrada na carga atual. Enriquecimento de O.S nao executado.")
        enriched["origem_numero_os"] = enriched["numero_os_original"].apply(
            lambda value: "ZENDESK" if value else None
        )
        enriched["status_vinculo_os"] = enriched["numero_os_original"].apply(
            lambda value: "ZENDESK_ORIGINAL" if value else "GSS_NAO_CARREGADO"
        )
        return enriched

    gss = gss_df.copy()
    gss_by_matricula = {
        matricula: group.sort_values(["data_emissao", "gss_os_id"], ascending=[False, False], kind="stable")
        for matricula, group in gss.groupby("matricula", dropna=True)
    }

    gss_by_os = {
        numero_os: group.sort_values(["data_emissao", "gss_os_id"], ascending=[False, False], kind="stable")
        for numero_os, group in gss.groupby("numero_os", dropna=True)
    }

    resultados: list[dict[str, object]] = []

    for _, ticket in enriched.iterrows():
        numero_os_original = ticket.get("numero_os_original")
        matricula = ticket.get("matricula")
        resultado = {
            "numero_os": numero_os_original,
            "numero_os_original": numero_os_original,
            "numero_os_gss": None,
            "gss_os_id": None,
            "origem_numero_os": "ZENDESK" if numero_os_original else None,
            "status_vinculo_os": "ZENDESK_ORIGINAL" if numero_os_original else "SEM_MATCH",
            "score_vinculo_os": 1.0 if numero_os_original else None,
            "criterio_vinculo_os": "numero_os_informado_no_zendesk" if numero_os_original else "sem_match",
        }

        if numero_os_original:
            exact_candidates = gss_by_os.get(numero_os_original)
            if exact_candidates is not None and not exact_candidates.empty:
                exact_match = _prefer_same_matricula(exact_candidates, matricula)
                resultado.update(
                    {
                        "numero_os_gss": exact_match["numero_os"],
                        "gss_os_id": exact_match["gss_os_id"],
                        "status_vinculo_os": "MATCH_EXATO_ZENDESK_GSS",
                        "score_vinculo_os": 1.0,
                        "criterio_vinculo_os": "numero_os_exato",
                    }
                )
            resultados.append(resultado)
            continue

        if not matricula:
            resultado.update(
                {
                    "status_vinculo_os": "SEM_MATRICULA",
                    "criterio_vinculo_os": "matricula_ausente",
                }
            )
            resultados.append(resultado)
            continue

        candidates = gss_by_matricula.get(matricula)
        if candidates is None or candidates.empty:
            resultado.update(
                {
                    "status_vinculo_os": "SEM_CANDIDATO_GSS",
                    "criterio_vinculo_os": "nenhuma_os_para_matricula",
                }
            )
            resultados.append(resultado)
            continue

        scored_candidates = _score_gss_candidates(ticket, candidates)
        best_candidate = scored_candidates.iloc[0]
        second_score = float(scored_candidates.iloc[1]["score_match"]) if len(scored_candidates) > 1 else 0.0
        margin = float(best_candidate["score_match"]) - second_score

        if float(best_candidate["score_match"]) >= GSS_MATCH_MIN_SCORE and margin >= GSS_MATCH_MIN_MARGIN:
            resultado.update(
                {
                    "numero_os": best_candidate["numero_os"],
                    "numero_os_gss": best_candidate["numero_os"],
                    "gss_os_id": best_candidate["gss_os_id"],
                    "origem_numero_os": "GSS_MATCH",
                    "status_vinculo_os": "MATCH_AUTOMATICO",
                    "score_vinculo_os": round(float(best_candidate["score_match"]), 4),
                    "criterio_vinculo_os": best_candidate["criterio_match"],
                }
            )
        elif float(best_candidate["score_match"]) >= GSS_MATCH_MIN_SCORE:
            resultado.update(
                {
                    "numero_os_gss": best_candidate["numero_os"],
                    "gss_os_id": best_candidate["gss_os_id"],
                    "origem_numero_os": None,
                    "status_vinculo_os": "AMBIGUO",
                    "score_vinculo_os": round(float(best_candidate["score_match"]), 4),
                    "criterio_vinculo_os": best_candidate["criterio_match"],
                }
            )
        else:
            resultado.update(
                {
                    "status_vinculo_os": "SEM_MATCH",
                    "score_vinculo_os": round(float(best_candidate["score_match"]), 4),
                    "criterio_vinculo_os": best_candidate["criterio_match"],
                }
            )

        resultados.append(resultado)

    enrichment_df = pd.DataFrame(resultados, index=enriched.index)
    for column in enrichment_df.columns:
        enriched[column] = enrichment_df[column]

    total_matches = int((enriched["status_vinculo_os"] == "MATCH_AUTOMATICO").sum())
    total_ambiguos = int((enriched["status_vinculo_os"] == "AMBIGUO").sum())
    logging.info(
        "Enriquecimento GSS concluido: %s matches automaticos e %s casos ambiguos.",
        total_matches,
        total_ambiguos,
    )
    return enriched


def _prefer_same_matricula(candidates: pd.DataFrame, matricula: str | None) -> pd.Series:
    if matricula:
        same_matricula = candidates[candidates["matricula"] == matricula]
        if not same_matricula.empty:
            return same_matricula.iloc[0]
    return candidates.iloc[0]


def _score_gss_candidates(ticket: pd.Series, candidates: pd.DataFrame) -> pd.DataFrame:
    scored = candidates.copy()
    ticket_date = pd.to_datetime(
        first_not_null(ticket, ["data_entrada_reclamacao", "data_criacao_solicitacao", "data_criacao"]),
        errors="coerce",
    )
    ticket_status = normalize_text(ticket.get("status"))
    ticket_text = normalize_subject(
        _join_text_parts(
            [
                ticket.get("titulo"),
                ticket.get("assunto"),
                ticket.get("tipo_solicitacao"),
                ticket.get("tipo_manifestacao"),
                ticket.get("classificacao_solicitacoes"),
                ticket.get("canais_de_atrito"),
            ]
        )
    )
    ticket_tokens = normalize_token_set(ticket_text)

    # Pre-computa os tokens da OS uma unica vez por candidato (era recomputado
    # a cada ticket no caminho original).
    if "_service_tokens" not in scored.columns:
        scored["_service_tokens"] = scored["servico_normalizado"].map(normalize_token_set)

    scored["date_score"] = scored["data_emissao"].map(lambda value: _calculate_date_score(ticket_date, value))
    scored["service_score"] = scored["_service_tokens"].map(
        lambda tokens: _calculate_service_score(ticket_tokens, tokens)
    )
    scored["status_score"] = scored["status_os_gss"].map(
        lambda value: _calculate_status_score(ticket_status, value)
    )
    scored["score_match"] = (
        (GSS_WEIGHT_DATE * scored["date_score"])
        + (GSS_WEIGHT_SERVICE * scored["service_score"])
        + (GSS_WEIGHT_STATUS * scored["status_score"])
    )
    if scored["score_match"].isna().any():
        logging.warning(
            "Score GSS com NaN apos calculo (ticket=%s); preenchendo com 0.0.",
            ticket.get("ticket_id"),
        )
        scored["score_match"] = scored["score_match"].fillna(0.0)
    scored["criterio_match"] = (
        "matricula+score_servico_datas"
        + "|date=" + scored["date_score"].map(lambda v: f"{v:.2f}")
        + "|service=" + scored["service_score"].map(lambda v: f"{v:.2f}")
        + "|status=" + scored["status_score"].map(lambda v: f"{v:.2f}")
    )
    return scored.sort_values(
        ["score_match", "data_emissao", "gss_os_id"],
        ascending=[False, False, False],
        kind="stable",
    ).copy()


def _calculate_date_score(ticket_date: pd.Timestamp | None, os_date: pd.Timestamp | None) -> float:
    if pd.isna(ticket_date) or pd.isna(os_date):
        # Sem dado de data nao premiamos o candidato; voltar score neutro
        # so favorece OS antigas com dados incompletos.
        return 0.0

    distance = abs((ticket_date.normalize() - os_date.normalize()).days)
    for limit, score in GSS_DATE_SCORE_BANDS:
        if distance <= limit:
            return score
    return 0.0


def _calculate_service_score(ticket_tokens: set[str], service_tokens: set[str]) -> float:
    if not ticket_tokens or not service_tokens:
        return 0.0

    union = ticket_tokens | service_tokens
    if not union:
        return 0.0
    return len(ticket_tokens & service_tokens) / len(union)


def _calculate_status_score(ticket_status: str | None, status_os_gss: str | None) -> float:
    if status_os_gss is None:
        return 0.30

    if status_os_gss in {"PENDENTE", "PENDENTE_VENCIDA"}:
        return 1.0 if ticket_status in {"OPEN", "HOLD", "PENDING", "NEW"} else 0.75
    if status_os_gss == "EXECUTADA":
        return 0.60
    return 0.30
