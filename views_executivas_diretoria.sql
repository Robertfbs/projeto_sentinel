-- ============================================================
-- Projeto Sentinel
-- Views executivas para consumo no Power BI
-- Compatibilidade: SQLite
-- ============================================================

-- ============================================================
-- 1) Audiencias em aberto
-- Regra:
-- - Considera em aberto quando a data_audiencia e hoje ou futura
--   OU quando o ticket associado ainda nao esta Resolvido/Fechado.
-- - Como a tabela audiencias nao possui status_audiencia no schema atual,
--   a logica usa data_audiencia + status do ticket.
-- ============================================================
DROP VIEW IF EXISTS vw_audiencias_em_aberto;
CREATE VIEW vw_audiencias_em_aberto AS
SELECT
    date('now', 'localtime') AS data_referencia,
    COUNT(DISTINCT a.audiencia_id) AS qtde_audiencias_em_aberto
FROM audiencias AS a
INNER JOIN tickets AS t
    ON t.ticket_id = a.ticket_id
WHERE
    date(a.data_audiencia) >= date('now', 'localtime')
    OR UPPER(TRIM(COALESCE(t.status, ''))) NOT IN ('RESOLVIDO', 'FECHADO', 'RESOLVIDO/FECHADO');


-- ============================================================
-- 2) Funil PROCON -> Audiencia
-- Regra:
-- - Considera protocolos distintos de PROCON.
-- - Conta quantos protocolos existem no total e quantos evoluiram
--   para audiencia por meio de INNER JOIN entre tickets e audiencias.
-- ============================================================
DROP VIEW IF EXISTS vw_funil_procon_audiencia;
CREATE VIEW vw_funil_procon_audiencia AS
WITH base_procon AS (
    SELECT DISTINCT
        TRIM(t.protocolo_procon) AS protocolo_procon
    FROM tickets AS t
    WHERE NULLIF(TRIM(t.protocolo_procon), '') IS NOT NULL
),
procon_com_audiencia AS (
    SELECT DISTINCT
        TRIM(t.protocolo_procon) AS protocolo_procon
    FROM tickets AS t
    INNER JOIN audiencias AS a
        ON a.ticket_id = t.ticket_id
    WHERE NULLIF(TRIM(t.protocolo_procon), '') IS NOT NULL
)
SELECT
    date('now', 'localtime') AS data_referencia,
    (SELECT COUNT(*) FROM base_procon) AS qtde_protocolos_procon_total,
    (SELECT COUNT(*) FROM procon_com_audiencia) AS qtde_protocolos_procon_com_audiencia,
    (
        (SELECT COUNT(*) FROM base_procon)
        - (SELECT COUNT(*) FROM procon_com_audiencia)
    ) AS qtde_protocolos_procon_sem_audiencia,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM procon_com_audiencia)
        / NULLIF((SELECT COUNT(*) FROM base_procon), 0),
        2
    ) AS taxa_conversao_pct;


-- ============================================================
-- 3) Produtividade do time
-- Regra:
-- - Considera ticket resolvido quando data_resolucao nao e nula.
-- - A granularidade e entregue em uma unica view via UNION ALL:
--   DIARIA, SEMANAL e MENSAL.
-- - strftime('%Y-%m-%d') agrupa por dia.
-- - strftime('%Y') + strftime('%W') evita misturar semana 10 de anos diferentes.
-- - strftime('%Y-%m') agrupa por mes.
-- ============================================================
DROP VIEW IF EXISTS vw_produtividade_time_resolvidos;
CREATE VIEW vw_produtividade_time_resolvidos AS
WITH base AS (
    SELECT
        COALESCE(NULLIF(TRIM(atribuido), ''), 'NAO ATRIBUIDO') AS atribuido,
        date(data_resolucao) AS data_base
    FROM tickets
    WHERE data_resolucao IS NOT NULL
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
    strftime('%Y-%m', data_base);


-- ============================================================
-- 4) Volumetria de entrada (Inflow)
-- Regra:
-- - Usa data_entrada_reclamacao como data oficial de entrada.
-- - Se data_entrada_reclamacao estiver nula, usa data_criacao como fallback.
-- - Entrega total geral e subtotal por canal em uma unica view.
-- - strftime('%Y-%m-%d') = dia
-- - strftime('%Y') + strftime('%W') = semana
-- - strftime('%Y-%m') = mes
-- - strftime('%Y') = ano
-- ============================================================
DROP VIEW IF EXISTS vw_volumetria_entrada;
CREATE VIEW vw_volumetria_entrada AS
WITH base AS (
    SELECT
        COALESCE(date(data_entrada_reclamacao), date(data_criacao)) AS data_base,
        COALESCE(NULLIF(TRIM(tipo_solicitacao), ''), 'NAO INFORMADO') AS canal_entrada
    FROM tickets
    WHERE COALESCE(date(data_entrada_reclamacao), date(data_criacao)) IS NOT NULL
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
    canal_entrada;
