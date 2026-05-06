# Glossario

Referencia de termos tecnicos, de negocio e siglas utilizados no Projeto Sentinel.

[Voltar ao indice](README.md)

---

## Termos de Negocio

| Termo | Definicao |
|---|---|
| **SOLICITACAO** | Ticket Zendesk do tipo "solicitacao" — representa a reclamacao ou demanda principal do cliente. E o fato central da analise operacional N2. |
| **NOTIFICACAO** | Ticket Zendesk do tipo "notificacao" — representa uma comunicacao formal associada a uma solicitacao. Vinculada a solicitacao por regras de matching. |
| **ANEXO** | Ticket classificado como anexo informativo, arquivado logicamente (`flag_arquivado_relatorio = 1`). Nao deve compor indicadores operacionais. |
| **Matricula** | Identificador unico do cliente no sistema comercial. Chave principal para enriquecimento e agrupamento territorial. |
| **Bloco** | Divisao territorial derivada do prefixo da matricula. `40*` = Bloco 4, `10*` = Bloco 1. |
| **Case** | Agrupador logico de tickets. O `case_id` e definido com prioridade para `protocolo_agenersa`; na ausencia, assume `ticket_id`. |
| **Protocolo Agenersa** | Protocolo da agencia reguladora Agenersa, extraido do ticket. Tem prioridade na definicao do `case_id`. |
| **Protocolo Procon** | Protocolo do orgao de defesa do consumidor Procon. |
| **Protocolo Defensoria** | Protocolo da Defensoria Publica. |
| **Protocolo Codecon** | Protocolo do Codecon (orgao regulador). |
| **Case JEC** | Identificador gerado para Juizado Especial Civel. |
| **Vinculacao** | Processo de associar uma NOTIFICACAO a sua SOLICITACAO correspondente, utilizando 5 niveis de prioridade com janela maxima de 7 dias. |
| **Enriquecimento** | Complemento de dados faltantes no ticket Zendesk a partir da base comercial GSS, sem sobrescrever valores validos existentes. |
| **Ordem de Servico (O.S.)** | Registro de servico no sistema GSS. Quando ausente no Zendesk, pode ser inferida por matching com scoring. |
| **Preposto** | Representante designado para comparecer em audiencia judicial ou administrativa. |
| **Audiencia** | Sessao judicial ou administrativa agendada, com dados de data, local, tipo e preposto. |
| **Manifestacao Institucional** | Reclamacao ou demanda recebida por orgaos institucionais (Agenersa, Procon, Defensoria, Codecon, JEC). |
| **Concessionaria** | Empresa concessionaria de servico publico associada ao ticket. |
| **Superintendencia ADR** | Area administrativa responsavel pelo atendimento regional. |
| **Canais de Atrito** | Canais pelos quais o cliente manifestou insatisfacao ou contato. |

---

## Termos Tecnicos

| Termo | Definicao |
|---|---|
| **Bronze** | Camada de dados brutos, sem tratamento. Corresponde ao diretorio `01_raw/`. |
| **Silver** | Camada de dados tratados, normalizados e deduplicados. Corresponde ao diretorio `02_silver/`. |
| **Gold** | Camada final analitica, consumivel por BI. Corresponde ao banco `03_database/pre_contencioso.db`. |
| **ETL** | Extract, Transform, Load — processo de extracao, transformacao e carga de dados. |
| **UPSERT** | Operacao que insere um registro se nao existir ou atualiza se ja existir, com base na chave primaria. Garante idempotencia. |
| **Deduplicacao** | Remocao de linhas duplicadas, mantendo a ultima ocorrencia (`keep last`) com ordenacao controlada. |
| **Normalizacao de colunas** | Padronizacao de nomes de coluna tolerando variacoes de acento, caixa e nomes equivalentes. |
| **Scoring** | Calculo de pontuacao para matching de O.S., combinando proximidade de data, similaridade textual e status. |
| **Pipeline** | Sequencia ordenada de etapas de processamento de dados, orquestrada pelo `main_etl.py`. |
| **Descoberta dinamica** | Mecanismo do `pipeline_sources.py` para localizar automaticamente arquivos por prefixo em `01_raw/`. |
| **flag_arquivado_relatorio** | Flag binario (0/1) que indica se o ticket deve ser excluido dos indicadores analiticos. |
| **D-1** | Regra de data de referencia: o relatorio executivo considera dados ate o dia anterior a execucao. |
| **Data lineage** | Rastreabilidade da origem e transformacoes aplicadas a cada campo do banco Gold. |
| **Chave de negocio** | Campo ou conjunto de campos que identificam univocamente um registro no contexto de negocio (ex: `ticket_id`, `matricula`). |

---

## Siglas

| Sigla | Significado |
|---|---|
| **CX** | Customer Experience (Experiencia do Cliente) |
| **GSS** | Sistema comercial usado para enriquecimento de dados por matricula |
| **O.S.** | Ordem de Servico |
| **ADR** | Area/Superintendencia de atendimento regional |
| **N1** | Nivel 1 de atendimento Zendesk (primeiro contato) |
| **N2** | Nivel 2 de atendimento Zendesk (tratamento especializado — operacao principal) |
| **BI** | Business Intelligence |
| **MER** | Modelo Entidade-Relacionamento |
| **PK** | Primary Key (chave primaria) |
| **FK** | Foreign Key (chave estrangeira) |
| **UK** | Unique Key (chave unica) |
| **JEC** | Juizado Especial Civel |

---

## Valores de Status Possiveis

### status_vinculo (vinculacao NOTIFICACAO-SOLICITACAO)

| Valor | Significado |
|---|---|
| `VINCULADO` | Vinculo estabelecido com sucesso entre NOTIFICACAO e SOLICITACAO |
| `AMBIGUO` | Multiplos candidatos sem margem suficiente para escolha automatica |
| `SEM_VINCULO` | Nenhum candidato encontrado dentro da janela de 7 dias |
| `NOTIFICACAO_NAO_CARREGADA` | NOTIFICACAO referenciada nao esta presente na carga atual |

### criterio_vinculo

| Valor | Significado |
|---|---|
| `MANUAL` | Vinculo definido pela tabela `ticket_vinculos_manuais` |
| `CHAVE_EXPLICITA` | Vinculo por chave explicita comum entre tickets |
| `MATRICULA_PROTOCOLO` | Vinculo por `matricula + protocolo_referencia` |
| `MATRICULA_ASSUNTO` | Vinculo por `matricula + assunto_normalizado` |

### origem_numero_os (matching O.S.)

| Valor | Significado |
|---|---|
| `ZENDESK` | O.S. veio preenchida diretamente do Zendesk |
| `GSS_MATCHING` | O.S. inferida por matching com scoring na base GSS |

### status_vinculo_os

| Valor | Significado |
|---|---|
| `ORIGINAL` | O.S. original do Zendesk, mantida sem alteracao |
| `INFERIDO` | O.S. atribuida por matching com confianca suficiente |
| `NAO_ENCONTRADO` | Nenhuma O.S. candidata com pontuacao suficiente |

[Voltar ao indice](README.md)
