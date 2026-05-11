OPEN_AUDIENCES_SQL = """
SELECT
    :start_date AS periodo_inicial,
    :end_date AS periodo_final,
    date(COALESCE(:reference_date, 'now', 'localtime')) AS data_referencia,
    COUNT(
        DISTINCT CASE
            WHEN date(COALESCE(a.data_reagendamento, a.data_audiencia)) >= date(COALESCE(:reference_date, 'now', 'localtime'))
                 OR UPPER(TRIM(COALESCE(t.status, ''))) IN ('OPEN', 'HOLD', 'PENDING', 'NEW')
            THEN a.audiencia_id
        END
    ) AS qtde_audiencias_em_aberto,
    COUNT(
        DISTINCT CASE
            WHEN date(COALESCE(a.data_reagendamento, a.data_audiencia)) >= date(COALESCE(:reference_date, 'now', 'localtime'))
            THEN a.audiencia_id
        END
    ) AS qtde_audiencias_somente_data_futura,
    COUNT(
        DISTINCT CASE
            WHEN UPPER(TRIM(COALESCE(t.status, ''))) IN ('OPEN', 'HOLD', 'PENDING', 'NEW')
            THEN a.audiencia_id
        END
    ) AS qtde_audiencias_ticket_aberto
FROM audiencias AS a
INNER JOIN tickets AS t
    ON t.ticket_id = a.ticket_id
WHERE
    COALESCE(t.flag_arquivado_relatorio, 0) = 0
    AND (
        t.formulario_ticket IS NULL
        OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
    )
"""


PROCON_FUNNEL_SQL = """
WITH base AS (
    SELECT
        t.ticket_id
    FROM tickets AS t
    WHERE NULLIF(TRIM(t.protocolo_procon), '') IS NOT NULL
      AND COALESCE(t.flag_arquivado_relatorio, 0) = 0
      AND (
          t.formulario_ticket IS NULL
          OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
      )
      AND COALESCE(date(t.data_entrada_reclamacao), date(t.data_criacao))
          BETWEEN :start_date AND :end_date
),
com_audiencia AS (
    SELECT DISTINCT
        b.ticket_id
    FROM base AS b
    INNER JOIN audiencias AS a
        ON a.ticket_id = b.ticket_id
)
SELECT
    :start_date AS periodo_inicial,
    :end_date AS periodo_final,
    (SELECT COUNT(*) FROM base) AS qtde_tickets_procon_periodo,
    (SELECT COUNT(*) FROM com_audiencia) AS qtde_tickets_procon_com_audiencia,
    (
        (SELECT COUNT(*) FROM base)
        - (SELECT COUNT(*) FROM com_audiencia)
    ) AS qtde_tickets_procon_sem_audiencia,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM com_audiencia)
        / NULLIF((SELECT COUNT(*) FROM base), 0),
        2
    ) AS taxa_conversao_pct
"""


PRODUCTIVITY_SQL = """
WITH base AS (
    SELECT
        COALESCE(NULLIF(TRIM(atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
        date(data_resolucao) AS data_base
    FROM tickets
    WHERE data_resolucao IS NOT NULL
      AND COALESCE(flag_arquivado_relatorio, 0) = 0
      AND (
          formulario_ticket IS NULL
          OR UPPER(TRIM(COALESCE(formulario_ticket, ''))) LIKE 'SOLICIT%'
      )
      AND date(data_resolucao) BETWEEN :start_date AND :end_date
)
SELECT
    'DIARIA' AS granularidade,
    data_base AS periodo_inicio,
    strftime('%Y-%m-%d', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    strftime('%m', data_base) AS mes,
    atribuido,
    COUNT(*) AS tickets_resolvidos
FROM base
GROUP BY
    atribuido,
    data_base

UNION ALL

SELECT
    'SEMANAL' AS granularidade,
    date(
        data_base,
        '-' || ((CAST(strftime('%w', data_base) AS INTEGER) + 6) % 7) || ' days'
    ) AS periodo_inicio,
    strftime('%Y', data_base) || '-S' || strftime('%W', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    NULL AS mes,
    atribuido,
    COUNT(*) AS tickets_resolvidos
FROM base
GROUP BY
    atribuido,
    strftime('%Y', data_base),
    strftime('%W', data_base)

UNION ALL

SELECT
    'MENSAL' AS granularidade,
    date(data_base, 'start of month') AS periodo_inicio,
    strftime('%Y-%m', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    NULL AS semana,
    strftime('%m', data_base) AS mes,
    atribuido,
    COUNT(*) AS tickets_resolvidos
FROM base
GROUP BY
    atribuido,
    strftime('%Y-%m', data_base)
"""


INFLOW_SQL = """
WITH base AS (
    SELECT
        COALESCE(date(data_entrada_reclamacao), date(data_criacao)) AS data_base,
        COALESCE(NULLIF(TRIM(tipo_solicitacao), ''), 'NAO INFORMADO') AS canal_entrada
    FROM tickets
    WHERE COALESCE(date(data_entrada_reclamacao), date(data_criacao))
          BETWEEN :start_date AND :end_date
      AND COALESCE(flag_arquivado_relatorio, 0) = 0
      AND (
          formulario_ticket IS NULL
          OR UPPER(TRIM(COALESCE(formulario_ticket, ''))) LIKE 'SOLICIT%'
      )
)
SELECT
    'DIARIA' AS granularidade,
    data_base AS periodo_inicio,
    strftime('%Y-%m-%d', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    strftime('%m', data_base) AS mes,
    'TOTAL GERAL' AS canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY data_base

UNION ALL

SELECT
    'DIARIA' AS granularidade,
    data_base AS periodo_inicio,
    strftime('%Y-%m-%d', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    strftime('%m', data_base) AS mes,
    canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    data_base,
    canal_entrada

UNION ALL

SELECT
    'SEMANAL' AS granularidade,
    date(
        data_base,
        '-' || ((CAST(strftime('%w', data_base) AS INTEGER) + 6) % 7) || ' days'
    ) AS periodo_inicio,
    strftime('%Y', data_base) || '-S' || strftime('%W', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    NULL AS mes,
    'TOTAL GERAL' AS canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y', data_base),
    strftime('%W', data_base)

UNION ALL

SELECT
    'SEMANAL' AS granularidade,
    date(
        data_base,
        '-' || ((CAST(strftime('%w', data_base) AS INTEGER) + 6) % 7) || ' days'
    ) AS periodo_inicio,
    strftime('%Y', data_base) || '-S' || strftime('%W', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    strftime('%W', data_base) AS semana,
    NULL AS mes,
    canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y', data_base),
    strftime('%W', data_base),
    canal_entrada

UNION ALL

SELECT
    'MENSAL' AS granularidade,
    date(data_base, 'start of month') AS periodo_inicio,
    strftime('%Y-%m', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    NULL AS semana,
    strftime('%m', data_base) AS mes,
    'TOTAL GERAL' AS canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y-%m', data_base)

UNION ALL

SELECT
    'MENSAL' AS granularidade,
    date(data_base, 'start of month') AS periodo_inicio,
    strftime('%Y-%m', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    NULL AS semana,
    strftime('%m', data_base) AS mes,
    canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y-%m', data_base),
    canal_entrada

UNION ALL

SELECT
    'ANUAL' AS granularidade,
    date(data_base, 'start of year') AS periodo_inicio,
    strftime('%Y', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    NULL AS semana,
    NULL AS mes,
    'TOTAL GERAL' AS canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y', data_base)

UNION ALL

SELECT
    'ANUAL' AS granularidade,
    date(data_base, 'start of year') AS periodo_inicio,
    strftime('%Y', data_base) AS periodo_label,
    strftime('%Y', data_base) AS ano,
    NULL AS semana,
    NULL AS mes,
    canal_entrada,
    COUNT(*) AS qtde_tickets
FROM base
GROUP BY
    strftime('%Y', data_base),
    canal_entrada
"""


DATA_SQL = """
SELECT
    :start_date AS periodo_inicial_param,
    :end_date AS periodo_final_param,
    date(COALESCE(:reference_date, 'now', 'localtime')) AS data_referencia_execucao,
    t.ticket_id,
    t.case_id,
    t.matricula,
    t.numero_os,
    t.data_criacao,
    t.data_resolucao,
    t.status,
    UPPER(TRIM(COALESCE(t.status, ''))) AS status_normalizado,
    t.atribuido,
    t.titulo,
    t.assunto,
    t.tipo_conversa,
    t.tipo_solicitacao,
    t.tipo_manifestacao,
    t.resultado_tratativa,
    t.formulario_ticket,
    t.classificacao_notificacoes,
    COALESCE(t.flag_arquivado_relatorio, 0) AS flag_arquivado_relatorio,
    t.protocolo_procon,
    t.protocolo_defensoria,
    t.protocolo_codecon,
    t.case_jec,
    t.ticket_solicitacao_id,
    t.ticket_notificacao_id,
    t.data_entrada_reclamacao,
    t.data_criacao_solicitacao,
    t.data_criacao_notificacao,
    t.dias_defasagem_abertura,
    t.criterio_vinculo,
    t.confianca_vinculo,
    t.status_vinculo,
    a.audiencia_id,
    a.audiencia,
    a.data_audiencia,
    a.data_reagendamento,
    date(COALESCE(a.data_reagendamento, a.data_audiencia)) AS data_audiencia_efetiva,
    a.preposto,
    a.local_procon,
    a.tipo_audiencia,
    COALESCE(date(t.data_entrada_reclamacao), date(t.data_criacao)) AS data_entrada_base,
    CASE
        WHEN COALESCE(date(t.data_entrada_reclamacao), date(t.data_criacao))
             BETWEEN :start_date AND :end_date
        THEN 1 ELSE 0
    END AS flag_periodo_entrada,
    CASE
        WHEN date(t.data_resolucao) BETWEEN :start_date AND :end_date
        THEN 1 ELSE 0
    END AS flag_periodo_resolucao,
    CASE
        WHEN NULLIF(TRIM(t.protocolo_procon), '') IS NOT NULL
        THEN 1 ELSE 0
    END AS flag_procon,
    CASE
        WHEN t.formulario_ticket IS NULL
             OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
        THEN 1 ELSE 0
    END AS flag_formulario_solicitacao,
    CASE
        WHEN a.audiencia_id IS NOT NULL
        THEN 1 ELSE 0
    END AS flag_tem_audiencia,
    CASE
        WHEN date(COALESCE(a.data_reagendamento, a.data_audiencia)) >= date(COALESCE(:reference_date, 'now', 'localtime'))
        THEN 1 ELSE 0
    END AS flag_audiencia_futura_ou_hoje,
    CASE
        WHEN UPPER(TRIM(COALESCE(t.status, ''))) IN ('OPEN', 'HOLD', 'PENDING', 'NEW')
        THEN 1 ELSE 0
    END AS flag_ticket_aberto,
    CASE
        WHEN a.audiencia_id IS NOT NULL
             AND (
                 date(COALESCE(a.data_reagendamento, a.data_audiencia)) >= date(COALESCE(:reference_date, 'now', 'localtime'))
                 OR UPPER(TRIM(COALESCE(t.status, ''))) IN ('OPEN', 'HOLD', 'PENDING', 'NEW')
             )
        THEN 1 ELSE 0
    END AS flag_audiencia_em_aberto_regra_atual,
    CASE
        WHEN a.audiencia_id IS NOT NULL
             AND date(COALESCE(a.data_reagendamento, a.data_audiencia)) >= date(COALESCE(:reference_date, 'now', 'localtime'))
        THEN 1 ELSE 0
    END AS flag_audiencia_em_aberto_data_futura,
    CASE
        WHEN COALESCE(t.flag_arquivado_relatorio, 0) = 0
             AND (
                 t.formulario_ticket IS NULL
                 OR UPPER(TRIM(COALESCE(t.formulario_ticket, ''))) LIKE 'SOLICIT%'
             )
        THEN 1 ELSE 0
    END AS flag_elegivel_relatorio
FROM tickets AS t
LEFT JOIN audiencias AS a
    ON a.ticket_id = t.ticket_id
ORDER BY
    flag_audiencia_em_aberto_regra_atual DESC,
    flag_periodo_entrada DESC,
    data_entrada_base DESC,
    t.ticket_id DESC
"""


REPORT_QUERIES = {
    "Audiencias em Aberto": OPEN_AUDIENCES_SQL,
    "Funil PROCON": PROCON_FUNNEL_SQL,
    "Produtividade": PRODUCTIVITY_SQL,
    "Inflow": INFLOW_SQL,
    "DATA": DATA_SQL,
}
