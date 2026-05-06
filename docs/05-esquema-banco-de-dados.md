# Esquema do Banco de Dados

**Audiencia**: AMBOS (Desenvolvedores e Analistas)

[Voltar ao indice](README.md) | [Anterior: Regras de Negocio](04-regras-de-negocio.md) | [Proximo: Linhagem de Dados](06-linhagem-de-dados.md)

---

## Visao Geral

| Propriedade | Valor |
|---|---|
| **Motor** | SQLite |
| **Banco** | `03_database/pre_contencioso.db` |
| **Total de tabelas** | 10 |
| **Total aproximado de campos** | ~170 |

### Categorias de tabelas

| Categoria | Tabelas |
|---|---|
| Dominio | `clientes`, `cases` |
| Operacionais | `tickets`, `tickets_notificacao`, `audiencias` |
| Auxiliares de rastreabilidade | `ticket_assunto`, `ticket_relacionamentos`, `ticket_vinculos_manuais` |
| Historica | `tickets_n1` |
| Legada | `gss_ordens_servico` |

**Diagrama ER completo:** [ver MER anotado](diagramas/mer-completo.md)

---

## Tabelas de Dominio

### clientes

**Finalidade**: Base de matriculas unicas de clientes. Tabela dimensional.
**Chave primaria**: `matricula`
**Chave UPSERT**: `matricula`
**Cardinalidade**: 1 linha = 1 cliente unico

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `matricula` | TEXT | PK | Identificador unico do cliente no sistema comercial | Zendesk N2 (extraido dos tickets) |

---

### cases

**Finalidade**: Agrupador logico de tickets. Permite agrupar reclamacoes por protocolo institucional.
**Chave primaria**: `case_id`
**Chave UPSERT**: `case_id`
**Cardinalidade**: 1 linha = 1 case logico

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `case_id` | TEXT | PK | ID do case. Prioridade: `protocolo_agenersa` > `ticket_id` | Derivado ETL |
| `protocolo_agenersa` | TEXT | — | Protocolo da Agenersa, quando existente | Zendesk N2 |

---

## Tabelas Operacionais

### tickets

**Finalidade**: Tabela fato principal da operacao N2. Contem tickets de SOLICITACAO.
**Chave primaria**: `ticket_id`
**Chave UPSERT**: `ticket_id`
**Cardinalidade**: 1 linha = 1 ticket de solicitacao

#### Bloco: Identificacao

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_id` | INTEGER | PK | Identificador unico do ticket no Zendesk | Zendesk direto |
| `case_id` | TEXT | FK → cases | ID do case logico | Derivado ETL |
| `matricula` | TEXT | FK → clientes | Matricula do cliente | Zendesk direto |
| `bloco` | TEXT | — | Bloco territorial (derivado da matricula: 40→Bloco 4, 10→Bloco 1) | Derivado ETL |
| `formulario_ticket` | TEXT | — | Nome do formulario Zendesk (identifica tipo: SOLICITACAO/NOTIFICACAO) | Zendesk direto |

#### Bloco: Datas

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `data_criacao` | DATETIME | — | Data de criacao do ticket no Zendesk | Zendesk direto |
| `data_resolucao` | DATETIME | — | Data de resolucao do ticket | Zendesk direto |
| `data_entrada_reclamacao` | DATETIME | — | Data de entrada da reclamacao (acompanha `data_criacao` da SOLICITACAO vinculada) | Derivado vinculacao |
| `data_criacao_solicitacao` | DATETIME | — | Data de criacao da SOLICITACAO (preservada na vinculacao) | Derivado vinculacao |
| `data_criacao_notificacao` | DATETIME | — | Data original de criacao da NOTIFICACAO vinculada | Derivado vinculacao |

#### Bloco: Operacional

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `status` | TEXT | — | Status atual do ticket no Zendesk | Zendesk direto |
| `atribuido` | TEXT | — | Analista atribuido ao ticket | Zendesk direto |
| `titulo` | TEXT | — | Titulo do ticket | Zendesk direto |
| `assunto` | TEXT | — | Assunto principal do ticket (1o assunto apos deduplicacao) | Zendesk direto |
| `tipo_conversa` | TEXT | — | Tipo de conversa no Zendesk | Zendesk direto |
| `tipo_solicitacao` | TEXT | — | Tipo de solicitacao | Zendesk direto |
| `tipo_manifestacao` | TEXT | — | Tipo de manifestacao (ANEXO indica arquivamento) | Zendesk direto |
| `resultado_tratativa` | TEXT | — | Resultado da tratativa do ticket | Zendesk direto |
| `tags_ticket` | TEXT | — | Tags associadas ao ticket | Zendesk direto |
| `grupo_tickets` | TEXT | — | Grupo de tickets no Zendesk | Zendesk direto |
| `superintendencia_adr` | TEXT | — | Superintendencia/ADR responsavel | Zendesk direto |
| `canal_origem` | TEXT | — | Canal de origem da reclamacao | Zendesk direto |
| `cpf_cliente` | TEXT | — | CPF do cliente | Zendesk direto |
| `passou_nivel_1` | TEXT | — | Indica se o ticket passou pelo N1 antes | Zendesk direto |
| `canais_de_atrito` | TEXT | — | Canais de atrito do cliente | Zendesk direto |
| `protocolo_referencia_informado` | TEXT | — | Protocolo de referencia informado pelo cliente | Zendesk direto |
| `motivo_espera` | TEXT | — | Motivo de espera, se aplicavel | Zendesk direto |
| `prioridade_ticket` | TEXT | — | Nivel de prioridade do ticket | Zendesk direto |
| `controle_interno` | TEXT | — | Informacao de controle interno | Zendesk direto |
| `concessionaria` | TEXT | — | Concessionaria associada | Zendesk direto |

#### Bloco: Classificacao

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `classificacao_solicitacoes` | TEXT | — | Classificacao das solicitacoes | Zendesk direto |
| `classificacao_notificacoes` | TEXT | — | Classificacao das notificacoes (usado na regra de ANEXO) | Zendesk direto |
| `flag_arquivado_relatorio` | INTEGER | — | 0 = ativo; 1 = arquivado (excluido de indicadores) | Derivado ETL |
| `qtde_assuntos_ticket` | INTEGER | — | Quantidade de assuntos distintos do ticket | Derivado ETL |
| `flag_multiplos_assuntos` | INTEGER | — | 1 se tem mais de um assunto, 0 caso contrario | Derivado ETL |

#### Bloco: Protocolos Institucionais

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `protocolo_procon` | TEXT | — | Protocolo do Procon extraido do ticket | Derivado ETL |
| `protocolo_defensoria` | TEXT | — | Protocolo da Defensoria Publica | Derivado ETL |
| `protocolo_codecon` | TEXT | — | Protocolo do Codecon | Derivado ETL |
| `case_jec` | TEXT | — | Identificador do Juizado Especial Civel | Derivado ETL |

#### Bloco: Endereco e Contato (enriquecidos por GSS)

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `bairro` | TEXT | — | Bairro do cliente | Zendesk ou GSS (enriquecimento) |
| `municipio` | TEXT | — | Municipio | Zendesk ou GSS (enriquecimento) |
| `logradouro` | TEXT | — | Logradouro | Zendesk ou GSS (enriquecimento) |
| `endereco` | TEXT | — | Endereco completo | Zendesk ou GSS (enriquecimento) |
| `numero_porta` | TEXT | — | Numero da porta | Zendesk ou GSS (enriquecimento) |
| `complemento` | TEXT | — | Complemento do endereco | Zendesk ou GSS (enriquecimento) |
| `telefone` | TEXT | — | Telefone de contato | Zendesk ou GSS (enriquecimento) |
| `nome_cliente_gss` | TEXT | — | Nome do cliente na base GSS | GSS (enriquecimento) |
| `nome_requerente_gss` | TEXT | — | Nome do requerente na base GSS | GSS (enriquecimento) |

#### Bloco: O.S. e Matching GSS

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `numero_os` | TEXT | — | Numero da O.S. (original ou inferido) | Zendesk ou GSS matching |
| `numero_os_original` | TEXT | — | Numero da O.S. original do Zendesk | Zendesk direto |
| `numero_os_gss` | TEXT | — | Numero da O.S. atribuido pelo matching GSS | GSS matching |
| `gss_os_id` | TEXT | — | ID unico da O.S. na base GSS | GSS matching |
| `origem_numero_os` | TEXT | — | `ZENDESK` ou `GSS_MATCHING` | Derivado ETL |
| `status_vinculo_os` | TEXT | — | `ORIGINAL`, `INFERIDO` ou `NAO_ENCONTRADO` | Derivado ETL |
| `score_vinculo_os` | REAL | — | Pontuacao numerica do matching | Derivado ETL |
| `criterio_vinculo_os` | TEXT | — | Descricao do criterio de match utilizado | Derivado ETL |

#### Bloco: Vinculacao NOTIFICACAO-SOLICITACAO

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_solicitacao_id` | INTEGER | — | ID da SOLICITACAO vinculada | Derivado vinculacao |
| `ticket_notificacao_id` | INTEGER | — | ID da NOTIFICACAO vinculada | Derivado vinculacao |
| `dias_defasagem_abertura` | INTEGER | — | Dias entre criacao da SOLICITACAO e NOTIFICACAO | Derivado vinculacao |
| `criterio_vinculo` | TEXT | — | Criterio usado: MANUAL, CHAVE_EXPLICITA, MATRICULA_PROTOCOLO, MATRICULA_ASSUNTO | Derivado vinculacao |
| `confianca_vinculo` | REAL | — | Score numerico de confianca do vinculo | Derivado vinculacao |
| `status_vinculo` | TEXT | — | VINCULADO, AMBIGUO, SEM_VINCULO ou NOTIFICACAO_NAO_CARREGADA | Derivado vinculacao |

---

### tickets_notificacao

**Finalidade**: Persistencia dos tickets de NOTIFICACAO. Estrutura similar a `tickets`, sem campos de matching O.S. e vinculacao.
**Chave primaria**: `ticket_id`
**Chave UPSERT**: `ticket_id`
**Cardinalidade**: 1 linha = 1 ticket de notificacao

#### Campos

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_id` | INTEGER | PK | ID do ticket de notificacao | Zendesk direto |
| `case_id` | TEXT | — | ID do case logico | Derivado ETL |
| `matricula` | TEXT | — | Matricula do cliente | Zendesk direto |
| `bloco` | TEXT | — | Bloco territorial derivado | Derivado ETL |
| `numero_os` | TEXT | — | Numero da O.S. | Zendesk direto |
| `data_criacao` | DATETIME | — | Data de criacao do ticket | Zendesk direto |
| `data_resolucao` | DATETIME | — | Data de resolucao | Zendesk direto |
| `status` | TEXT | — | Status atual | Zendesk direto |
| `atribuido` | TEXT | — | Analista atribuido | Zendesk direto |
| `titulo` | TEXT | — | Titulo do ticket | Zendesk direto |
| `assunto` | TEXT | — | Assunto principal | Zendesk direto |
| `tipo_conversa` | TEXT | — | Tipo de conversa | Zendesk direto |
| `tipo_solicitacao` | TEXT | — | Tipo de solicitacao | Zendesk direto |
| `tipo_manifestacao` | TEXT | — | Tipo de manifestacao | Zendesk direto |
| `resultado_tratativa` | TEXT | — | Resultado da tratativa | Zendesk direto |
| `tags_ticket` | TEXT | — | Tags do ticket | Zendesk direto |
| `grupo_tickets` | TEXT | — | Grupo de tickets | Zendesk direto |
| `superintendencia_adr` | TEXT | — | Superintendencia responsavel | Zendesk direto |
| `canal_origem` | TEXT | — | Canal de origem | Zendesk direto |
| `cpf_cliente` | TEXT | — | CPF do cliente | Zendesk direto |
| `passou_nivel_1` | TEXT | — | Passou pelo N1 | Zendesk direto |
| `canais_de_atrito` | TEXT | — | Canais de atrito | Zendesk direto |
| `protocolo_referencia_informado` | TEXT | — | Protocolo de referencia | Zendesk direto |
| `motivo_espera` | TEXT | — | Motivo de espera | Zendesk direto |
| `prioridade_ticket` | TEXT | — | Prioridade | Zendesk direto |
| `controle_interno` | TEXT | — | Controle interno | Zendesk direto |
| `concessionaria` | TEXT | — | Concessionaria | Zendesk direto |
| `classificacao_solicitacoes` | TEXT | — | Classificacao de solicitacoes | Zendesk direto |
| `bairro` | TEXT | — | Bairro | Zendesk ou GSS |
| `municipio` | TEXT | — | Municipio | Zendesk ou GSS |
| `logradouro` | TEXT | — | Logradouro | Zendesk ou GSS |
| `endereco` | TEXT | — | Endereco | Zendesk ou GSS |
| `numero_porta` | TEXT | — | Numero porta | Zendesk ou GSS |
| `complemento` | TEXT | — | Complemento | Zendesk ou GSS |
| `telefone` | TEXT | — | Telefone | Zendesk ou GSS |
| `nome_cliente_gss` | TEXT | — | Nome cliente GSS | GSS |
| `nome_requerente_gss` | TEXT | — | Nome requerente GSS | GSS |
| `formulario_ticket` | TEXT | — | Formulario Zendesk | Zendesk direto |
| `classificacao_notificacoes` | TEXT | — | Classificacao das notificacoes | Zendesk direto |
| `flag_arquivado_relatorio` | INTEGER | — | Flag de arquivamento | Derivado ETL |
| `protocolo_procon` | TEXT | — | Protocolo Procon | Derivado ETL |
| `protocolo_defensoria` | TEXT | — | Protocolo Defensoria | Derivado ETL |
| `protocolo_codecon` | TEXT | — | Protocolo Codecon | Derivado ETL |
| `case_jec` | TEXT | — | Case JEC | Derivado ETL |
| `arquivo_origem` | TEXT | — | Nome do arquivo de origem | Metadado ETL |
| `data_carga` | DATETIME | — | Timestamp da carga | Metadado ETL |

**Diferencas vs. `tickets`:** Nao possui campos de matching O.S. (numero_os_original, numero_os_gss, gss_os_id, origem_numero_os, status_vinculo_os, score_vinculo_os, criterio_vinculo_os) nem campos de vinculacao (ticket_solicitacao_id, ticket_notificacao_id, dias_defasagem_abertura, criterio_vinculo, confianca_vinculo, status_vinculo, data_entrada_reclamacao, data_criacao_solicitacao, data_criacao_notificacao). Possui campos extras de auditoria (arquivo_origem, data_carga).

---

### audiencias

**Finalidade**: Agenda de audiencias judiciais e administrativas, com suporte a reagendamentos.
**Chave primaria**: `audiencia_id`
**Chave unica**: `ticket_id`
**Chave UPSERT**: `ticket_id`
**Cardinalidade**: 1 linha = 1 audiencia por ticket (0 ou 1 por ticket)

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `audiencia_id` | INTEGER | PK | ID unico da audiencia | Auto-gerado |
| `ticket_id` | INTEGER | UK | Ticket associado a audiencia | Zendesk direto |
| `ticket_audiencia_id` | INTEGER | — | ID do ticket da audiencia | Fonte audiencias |
| `ticket_relacionado_id` | INTEGER | — | ID do ticket relacionado | Fonte audiencias |
| `audiencia` | TEXT | — | Descricao/nome da audiencia | Fonte audiencias |
| `data_audiencia` | DATETIME | — | Data agendada para a audiencia | Fonte audiencias |
| `status_ticket` | TEXT | — | Status do ticket no contexto da audiencia | Fonte audiencias |
| `preposto_id` | TEXT | — | ID do preposto designado | Fonte audiencias |
| `preposto` | TEXT | — | Nome do preposto | Fonte audiencias |
| `local_procon` | TEXT | — | Local da audiencia (ex: unidade Procon) | Fonte audiencias |
| `tipo_audiencia` | TEXT | — | Classificacao do tipo de audiencia | Fonte audiencias |
| `atribuido` | TEXT | — | Analista atribuido | Fonte audiencias |
| `data_reagendamento` | DATETIME | — | Data de reagendamento (quando houver) | Fonte audiencias |
| `arquivo_origem` | TEXT | — | Nome do arquivo de origem | Metadado ETL |

---

## Tabelas Auxiliares de Rastreabilidade

### ticket_assunto

**Finalidade**: Preserva todos os assuntos distintos de cada ticket, resolvendo o problema de duplicidade por assunto.
**Chave primaria**: `ticket_assunto_id`
**Chave UPSERT**: `ticket_assunto_id`
**Cardinalidade**: 1 linha = 1 assunto de 1 ticket (N linhas por ticket_id)

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_assunto_id` | TEXT | PK | ID composto unico (ticket_id + assunto) | Derivado ETL |
| `ticket_id` | INTEGER | FK → tickets | Ticket pai | Zendesk direto |
| `formulario_ticket` | TEXT | — | Formulario do ticket (SOLICITACAO/NOTIFICACAO) | Zendesk direto |
| `assunto_raw` | TEXT | — | Assunto original, sem normalizacao | Zendesk direto |
| `assunto_normalizado` | TEXT | — | Assunto apos normalizacao padrao | Derivado ETL |
| `ordem_assunto` | INTEGER | — | Posicao ordinal do assunto no ticket | Derivado ETL |
| `flag_assunto_principal` | INTEGER | — | 1 para o primeiro assunto, 0 para demais | Derivado ETL |
| `arquivo_origem` | TEXT | — | Nome do arquivo de origem | Metadado ETL |
| `data_carga` | DATETIME | — | Timestamp da carga | Metadado ETL |

---

### ticket_relacionamentos

**Finalidade**: Resultado do processo de vinculacao entre SOLICITACAO e NOTIFICACAO.
**Chave primaria**: `ticket_solicitacao_id`
**Chave UPSERT**: `ticket_solicitacao_id`
**Cardinalidade**: 1 linha = 1 resultado de vinculacao por SOLICITACAO

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_solicitacao_id` | INTEGER | PK | ID da SOLICITACAO (origem do vinculo) | Derivado vinculacao |
| `ticket_notificacao_id` | INTEGER | FK → tickets_notificacao | ID da NOTIFICACAO vinculada (pode ser nulo) | Derivado vinculacao |
| `status_vinculo` | TEXT | — | VINCULADO, AMBIGUO, SEM_VINCULO, NOTIFICACAO_NAO_CARREGADA | Derivado vinculacao |
| `criterio_vinculo` | TEXT | — | MANUAL, CHAVE_EXPLICITA, MATRICULA_PROTOCOLO, MATRICULA_ASSUNTO | Derivado vinculacao |
| `confianca_vinculo` | REAL | — | Score numerico de confianca | Derivado vinculacao |
| `data_entrada_reclamacao` | DATETIME | — | Data de entrada (segue data_criacao da SOLICITACAO) | Derivado vinculacao |
| `data_criacao_solicitacao` | DATETIME | — | Data de criacao da SOLICITACAO | Derivado vinculacao |
| `data_criacao_notificacao` | DATETIME | — | Data de criacao da NOTIFICACAO (preservada) | Derivado vinculacao |
| `dias_defasagem_abertura` | INTEGER | — | Dias entre criacao da SOLICITACAO e da NOTIFICACAO | Derivado vinculacao |
| `quantidade_candidatos` | INTEGER | — | Numero de candidatos avaliados no matching | Derivado vinculacao |
| `observacao` | TEXT | — | Notas adicionais do processo de vinculacao | Derivado vinculacao |
| `atualizado_em` | DATETIME | — | Timestamp da ultima atualizacao | Metadado ETL |

---

### ticket_vinculos_manuais

**Finalidade**: Overrides manuais de vinculacao. Tem prioridade absoluta sobre vinculacao automatica.
**Chave primaria**: `ticket_solicitacao_id`
**Chave UPSERT**: `ticket_solicitacao_id`
**Cardinalidade**: 1 linha = 1 override manual por SOLICITACAO

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_solicitacao_id` | INTEGER | PK | ID da SOLICITACAO | Manual (usuario) |
| `ticket_notificacao_id` | INTEGER | FK → tickets_notificacao | ID da NOTIFICACAO vinculada manualmente | Manual (usuario) |
| `justificativa` | TEXT | — | Justificativa do override manual | Manual (usuario) |
| `usuario` | TEXT | — | Usuario que realizou o override | Manual (usuario) |
| `atualizado_em` | DATETIME | — | Timestamp da ultima atualizacao | Manual (usuario) |

---

## Tabela Historica

### tickets_n1

**Finalidade**: Arquivamento historico dos tickets N1. Isolada da operacao N2 — nao interfere em indicadores.
**Chave primaria**: `ticket_id`
**Chave UPSERT**: `ticket_id`
**Cardinalidade**: 1 linha = 1 ticket N1

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `ticket_id` | INTEGER | PK | ID do ticket N1 | Zendesk direto |
| `matricula` | TEXT | — | Matricula do cliente | Zendesk direto |
| `bloco` | TEXT | — | Bloco territorial derivado | Derivado ETL |
| `data_criacao` | DATETIME | — | Data de criacao | Zendesk direto |
| `data_resolucao` | DATETIME | — | Data de resolucao | Zendesk direto |
| `status` | TEXT | — | Status do ticket | Zendesk direto |
| `titulo` | TEXT | — | Titulo | Zendesk direto |
| `assunto` | TEXT | — | Assunto | Zendesk direto |
| `grupo_tickets` | TEXT | — | Grupo de tickets | Zendesk direto |
| `canal_ticket` | TEXT | — | Canal do ticket | Zendesk direto |
| `canal_origem` | TEXT | — | Canal de origem | Zendesk direto |
| `formulario_ticket` | TEXT | — | Formulario Zendesk | Zendesk direto |
| `tipo_ticket` | TEXT | — | Tipo do ticket | Zendesk direto |
| `conversation_id` | TEXT | — | ID da conversa | Zendesk direto |
| `tipo_conversa` | TEXT | — | Tipo de conversa | Zendesk direto |
| `arquivo_origem` | TEXT | — | Nome do arquivo de origem | Metadado ETL |
| `data_carga` | DATETIME | — | Timestamp da carga | Metadado ETL |

---

## Tabela Legada

### gss_ordens_servico

**Finalidade**: Tabela mantida no schema por **compatibilidade historica**. Nao faz parte da persistencia ativa do ETL atual.
**Chave primaria**: `gss_os_id`
**Chave UPSERT**: `gss_os_id`
**Cardinalidade**: 1 linha = 1 ordem de servico

| Campo | Tipo | Constraint | Descricao | Origem |
|---|---|---|---|---|
| `gss_os_id` | TEXT | PK | ID unico da O.S. na base GSS | GSS |
| `numero_os` | TEXT | — | Numero da O.S. | GSS |
| `ano_os` | TEXT | — | Ano da O.S. | GSS |
| `matricula` | TEXT | — | Matricula do cliente | GSS |
| `bloco` | TEXT | — | Bloco territorial derivado | Derivado ETL |
| `data_emissao` | DATETIME | — | Data de emissao da O.S. | GSS |
| `servico_executado` | TEXT | — | Descricao do servico executado | GSS |
| `nome_cliente` | TEXT | — | Nome do cliente | GSS |
| `nome_requerente` | TEXT | — | Nome do requerente | GSS |
| `telefone` | TEXT | — | Telefone de contato | GSS |
| `endereco_requerente` | TEXT | — | Endereco do requerente | GSS |
| `nome_logradouro` | TEXT | — | Nome do logradouro | GSS |
| `numero_porta` | TEXT | — | Numero da porta | GSS |
| `complemento` | TEXT | — | Complemento | GSS |
| `bairro` | TEXT | — | Bairro | GSS |
| `municipio` | TEXT | — | Municipio | GSS |
| `data_agendamento` | DATETIME | — | Data de agendamento | GSS |
| `data_impressao` | DATETIME | — | Data de impressao | GSS |
| `previsao_conclusao` | DATETIME | — | Previsao de conclusao | GSS |
| `data_execucao` | DATETIME | — | Data de execucao | GSS |
| `executor` | TEXT | — | Nome do executor | GSS |
| `entrada_setor` | DATETIME | — | Data de entrada no setor | GSS |
| `data_pedido` | TEXT | — | Data do pedido | GSS |
| `atendente` | TEXT | — | Nome do atendente | GSS |
| `solicitacao_associada` | TEXT | — | Solicitacao associada | GSS |
| `tipo_solicitacao_gss` | TEXT | — | Tipo de solicitacao no GSS | GSS |
| `status_os_gss` | TEXT | — | Status da O.S. no GSS | GSS |
| `servico_normalizado` | TEXT | — | Servico apos normalizacao | Derivado ETL |
| `arquivo_origem` | TEXT | — | Nome do arquivo de origem | Metadado ETL |
| `data_carga` | DATETIME | — | Timestamp da carga | Metadado ETL |

---

## Mapa de Relacionamentos

| Tabela Origem | Campo | Tabela Destino | Campo | Cardinalidade |
|---|---|---|---|---|
| `clientes` | `matricula` | `tickets` | `matricula` | 1:N |
| `cases` | `case_id` | `tickets` | `case_id` | 1:N |
| `tickets` | `ticket_id` | `audiencias` | `ticket_id` | 1:0..1 |
| `tickets` | `ticket_id` | `ticket_assunto` | `ticket_id` | 1:N |
| `tickets` | `ticket_id` | `ticket_relacionamentos` | `ticket_solicitacao_id` | 1:0..1 |
| `tickets_notificacao` | `ticket_id` | `ticket_relacionamentos` | `ticket_notificacao_id` | 1:N |
| `tickets` | `ticket_id` | `ticket_vinculos_manuais` | `ticket_solicitacao_id` | 1:0..1 |
| `tickets_notificacao` | `ticket_id` | `ticket_vinculos_manuais` | `ticket_notificacao_id` | 1:N |

**Tabelas sem FK formal:** `tickets_n1`, `gss_ordens_servico` (isoladas por design)

---

[Voltar ao indice](README.md) | [Anterior: Regras de Negocio](04-regras-de-negocio.md) | [Proximo: Linhagem de Dados](06-linhagem-de-dados.md)
