let
    Sql = "
SELECT
    t.ticket_id,
    t.case_id,
    t.matricula,
    t.numero_os,
    DATE(COALESCE(t.data_entrada_reclamacao, t.data_criacao)) AS data_entrada,
    DATE(t.data_criacao) AS data_criacao,
    DATE(t.data_resolucao) AS data_resolucao,
    t.status,
    t.atribuido,
    t.titulo,
    t.assunto,
    t.tipo_solicitacao,
    t.tipo_manifestacao,
    t.resultado_tratativa,
    t.protocolo_procon,
    t.protocolo_defensoria,
    t.protocolo_codecon,
    t.case_jec,
    t.formulario_ticket,
    t.classificacao_notificacoes,
    t.tags_ticket,
    t.grupo_tickets,
    t.canal_origem,
    t.canais_de_atrito,
    t.superintendencia_adr,
    t.prioridade_ticket,
    t.motivo_espera,
    t.classificacao_solicitacoes,
    t.bloco,
    t.qtde_assuntos_ticket,
    t.flag_multiplos_assuntos,
    t.bairro,
    t.municipio,
    t.logradouro,
    t.endereco,
    t.numero_porta,
    t.complemento,
    t.telefone,
    t.nome_cliente_gss,
    t.nome_requerente_gss,
    t.nome_solicitante,
    t.email_solicitante,
    t.numero_os_original,
    t.numero_os_gss,
    t.origem_numero_os,
    t.status_vinculo_os,
    t.score_vinculo_os,
    t.criterio_vinculo_os,
    t.ticket_notificacao_id,
    t.data_criacao_notificacao,
    t.status_vinculo,
    t.criterio_vinculo,
    t.confianca_vinculo,
    DATE(a.data_audiencia) AS data_audiencia,
    DATE(a.data_reagendamento) AS data_reagendamento,
    a.audiencia,
    a.preposto,
    a.local_procon,
    a.tipo_audiencia
FROM tickets t
LEFT JOIN audiencias a
    ON a.ticket_id = t.ticket_id
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
