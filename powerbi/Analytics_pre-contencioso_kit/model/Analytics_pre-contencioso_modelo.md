# Modelo de Dados - Analytics_pre-contencioso

## Objetivo

Definir um modelo estrela executavel no Power BI a partir do banco SQLite
`pre_contencioso.db`, priorizando simplicidade, governanca e performance.

## Tabela fato principal

### fTicketsSolicitacao

Granularidade:

- 1 linha = 1 ticket de solicitacao valido para analise executiva

Filtros de negocio aplicados na origem SQL:

- `formulario_ticket` iniciado por `SOLICIT`
- `tipo_manifestacao <> 'ANEXO'`
- `classificacao_notificacoes <> 'Informativo::ANEXO'`
- `flag_arquivado_relatorio = 0`

## Tabela fato complementar

### fAudiencias

Granularidade:

- 1 linha = 1 audiencia associada a um ticket valido

Uso recomendado:

- paginas de audiencia
- metricas de pendencia
- acompanhamento de agenda

## Dimensoes

### dCalendario

Relacao ativa recomendada:

- `dCalendario[Data]` -> `fTicketsSolicitacao[data_entrada]`

Relacoes inativas recomendadas:

- `dCalendario[Data]` -> `fTicketsSolicitacao[data_criacao]`
- `dCalendario[Data]` -> `fTicketsSolicitacao[data_resolucao]`
- `dCalendario[Data]` -> `fAudiencias[data_audiencia]`

Justificativa:

- `data_entrada` e a melhor data padrao para leitura executiva de inflow;
- outras datas podem ser ativadas em medidas especificas com `USERELATIONSHIP`.

### dCanal

Chave logica:

- `canal_original`

Exibicao recomendada:

- `canal_normalizado`

### dAssunto

Chave logica:

- `assunto_original`

Exibicao recomendada:

- `assunto_normalizado`

### dColaborador

Chave logica:

- `colaborador`

### dStatus

Chave logica:

- `status`

Campo derivado:

- `status_grupo` = `Aberto`, `Fechado`, `Outros`

### dLocalizacao

Chaves logicas:

- `municipio`
- `bairro`
- `bloco`

## Relacionamentos recomendados

Todos os relacionamentos devem ser `single direction` a partir das dimensoes
para os fatos.

1. `dCanal[canal_original]` -> `fTicketsSolicitacao[tipo_solicitacao]`
2. `dAssunto[assunto_original]` -> `fTicketsSolicitacao[assunto]`
3. `dColaborador[colaborador]` -> `fTicketsSolicitacao[atribuido]`
4. `dStatus[status]` -> `fTicketsSolicitacao[status]`
5. `dLocalizacao[municipio]` -> `fTicketsSolicitacao[municipio]`
6. `dCalendario[Data]` -> `fTicketsSolicitacao[data_entrada]` (ativa)
7. `dCalendario[Data]` -> `fTicketsSolicitacao[data_resolucao]` (inativa)
8. `dCalendario[Data]` -> `fAudiencias[data_audiencia]` (inativa)

Observacao:

`dLocalizacao` nao e uma dimensao geoespacial perfeita porque bairro nao e unico
globalmente. Para mapas mais precisos, o ideal e uma dimensao geografica futura
com chave surrogate.

## Campos recomendados para ocultar

Ocultar no modelo:

- `ticket_id`
- `case_id`
- `ticket_notificacao_id`
- `numero_os_original`
- `numero_os_gss`
- `score_vinculo_os`
- `criterio_vinculo_os`
- `confianca_vinculo`
- `criterio_vinculo`
- `status_vinculo`
- campos de protocolo que nao serao usados em visual executivo

## Paginas sugeridas

1. `Visao Geral`
2. `Produtividade`
3. `Canais`
4. `Assuntos`
5. `Audiencias`
6. `Geografia`

## SLA / Prazo

O modelo nao inclui medidas oficiais de `dentro do prazo` e `fora do prazo`
porque o projeto ainda nao possui uma coluna estruturada e confiavel de
vencimento por ticket.

Quando a camada de prazo for criada no DW, a recomendacao e adicionar:

- uma dimensao/regra de prazo;
- um fato de vencimento por ticket;
- colunas de confianca e fonte do prazo.
