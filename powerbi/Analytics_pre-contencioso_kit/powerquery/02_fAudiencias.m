let
    Sql = "
SELECT
    t.ticket_id,
    DATE(COALESCE(t.data_entrada_reclamacao, t.data_criacao)) AS data_entrada,
    DATE(t.data_criacao) AS data_criacao,
    DATE(t.data_resolucao) AS data_resolucao,
    DATE(a.data_audiencia) AS data_audiencia,
    DATE(a.data_reagendamento) AS data_reagendamento,
    t.status,
    t.atribuido,
    t.tipo_solicitacao,
    t.assunto,
    t.tipo_manifestacao,
    t.municipio,
    t.bairro,
    a.audiencia,
    a.preposto,
    a.local_procon,
    a.tipo_audiencia
FROM audiencias a
INNER JOIN tickets t
    ON t.ticket_id = a.ticket_id
WHERE UPPER(COALESCE(t.formulario_ticket, '')) LIKE 'SOLICIT%'
  AND UPPER(COALESCE(t.tipo_manifestacao, '')) <> 'ANEXO'
  AND UPPER(COALESCE(t.classificacao_notificacoes, '')) <> 'INFORMATIVO::ANEXO'
  AND COALESCE(t.flag_arquivado_relatorio, 0) = 0;
",
    ConnectionString = "Driver={" & pSqliteDriverName & "};Database=" & pDbPath & ";",
    Source =
        Odbc.Query(ConnectionString, Sql)
in
    Source
