# Projeto Sentinel

Plataforma de dados em Python + SQLite para consolidacao, tratamento, enriquecimento e persistencia analitica de tickets Zendesk relacionados a CX, pre-contencioso e manifestacoes institucionais.

O projeto foi estruturado como um mini data warehouse operacional, com foco em rastreabilidade de reclamacoes, preservacao do contexto transacional dos tickets, enriquecimento complementar com dados comerciais e entrega de uma base Gold consumivel por Power BI.

## Escopo Atual

O estado atual do projeto cobre quatro frentes principais:

1. Ingestao dinamica de multiplos arquivos brutos em `01_raw`, identificados por prefixo.
2. Tratamento e normalizacao de dados Zendesk N2, Zendesk N1, audiencias e GSS.
3. Persistencia relacional em SQLite com UPSERT incremental.
4. Camada analitica auxiliar em Python para geracao de relatorios executivos em Excel.

O desenho privilegia alteracoes aditivas, baixo acoplamento, reprocessamento seguro e compatibilidade com o consumo atual em BI.

## Objetivo do Banco Analitico

O banco `03_database/pre_contencioso.db` foi desenhado para responder, com rastreabilidade, perguntas operacionais e estrategicas como:

- volume real de tickets por periodo e por canal;
- evolucao de manifestacoes institucionais;
- relacao entre `NOTIFICACAO` e `SOLICITACAO`;
- produtividade operacional por analista;
- funil de protocolos institucionais;
- acompanhamentos com audiencia;
- enriquecimento territorial e comercial por matricula.

## Stack Tecnico

- Python 3.10+
- Pandas
- SQLite
- openpyxl
- xlsxwriter

## Arquitetura

O pipeline segue o modelo `Bronze -> Silver -> Gold`.

```text
Arquivos manuais (Zendesk / GSS)
        |
        v
01_raw  [Bronze]
        |
        v
main_etl.py
  - ingestao dinamica
  - padronizacao
  - deduplicacao
  - enriquecimento
  - vinculacao
        |
        v
02_silver [datasets tratados e auditoria]
        |
        v
03_database/pre_contencioso.db [Gold]
        |
        v
Power BI / Analises / scripts/analytics
```

## Estrutura do Projeto

```text
Projeto_Sentinel/
|-- 01_raw/
|-- 02_silver/
|-- 03_database/
|   `-- pre_contencioso.db
|-- outputs/
|-- scripts/
|   |-- create_database.py
|   |-- load_database.py
|   |-- main_etl.py
|   |-- pipeline_common.py
|   |-- pipeline_sources.py
|   |-- gss_matching.py
|   `-- analytics/
|       |-- __init__.py
|       |-- queries.py
|       `-- relatorio_executivo.py
|-- MER_Projeto_Sentinel.mmd
`-- README.md
```

## Fontes de Dados

### 1. Zendesk N2 - Relatorio Geral

Prefixo obrigatorio em `01_raw`:

- `ANALYTICS_BASE_TICKETS_GERAL`

Esse relatorio contem, na mesma extracao:

- tickets de `SOLICITACAO`;
- tickets de `NOTIFICACAO`;
- informacoes operacionais completas do N2;
- o campo `Formulário de ticket`, utilizado para separar logicamente os dois universos.

Observacao importante:

- o projeto nao gera mais dois arquivos Silver separados para o N2;
- o Silver consolidado do geral permanece em um unico arquivo;
- a separacao entre `SOLICITACAO` e `NOTIFICACAO` ocorre internamente no ETL para fins de carga no banco.

### 2. Zendesk N1

Prefixo obrigatorio:

- `ANALYTICS_BASE_TICKETS_N1`

O N1 e armazenado separadamente em `tickets_n1`, pois nao compoe a operacao principal do N2. O objetivo atual e arquivamento tecnico e manutencao historica para uso futuro.

### 3. Audiencias

Prefixo obrigatorio:

- `PRE_CONTENCIOSO_AUDIENCIAS`

Fonte dedicada para:

- data da audiencia;
- reagendamento;
- preposto;
- local;
- tipo de audiencia;
- chaves de relacionamento com ticket.

### 4. GSS / Base Comercial

Prefixo obrigatorio:

- `Base_GSS`

Uso atual:

- enriquecimento complementar por `matricula`;
- apoio ao preenchimento de O.S. ausente;
- complemento de endereco e contato;
- suporte analitico auxiliar.

Uso nao adotado no desenho atual:

- a base GSS nao e carregada integralmente como Silver operacional;
- a base GSS nao e mais persistida integralmente como parte ativa do fluxo Gold;
- o ETL filtra a base bruta apenas para as matriculas relevantes aos tickets da carga.

## Descoberta Dinamica de Arquivos

O modulo [pipeline_sources.py](E:/Projeto_Sentinel/scripts/pipeline_sources.py) localiza automaticamente arquivos por prefixo e extensao suportada.

Configuracao atual:

- `ANALYTICS_BASE_TICKETS_GERAL`
- `ANALYTICS_BASE_TICKETS_N1`
- `PRE_CONTENCIOSO_AUDIENCIAS`
- `Base_GSS`

Caracteristicas:

- aceita multiplos arquivos por prefixo;
- aceita variacoes de sufixo, data e versao no nome;
- registra `arquivo_origem`, `arquivo_mtime` e `fonte_raw` no momento da leitura;
- concatena todas as ocorrencias de uma mesma fonte antes da transformacao.

## Scripts Principais

### [create_database.py](E:/Projeto_Sentinel/scripts/create_database.py)

Responsavel por:

- criar o banco SQLite caso ainda nao exista;
- garantir tabelas, indices e colunas incrementais;
- manter compatibilidade retroativa com esquemas anteriores via `ALTER TABLE` aditivo.

### [load_database.py](E:/Projeto_Sentinel/scripts/load_database.py)

Responsavel por:

- executar UPSERT generico em SQLite;
- utilizar tabela temporaria via Pandas;
- atualizar apenas as colunas presentes no dataframe carregado;
- evitar duplicidade por chave primaria.

### [pipeline_common.py](E:/Projeto_Sentinel/scripts/pipeline_common.py)

Responsavel por utilitarios compartilhados:

- normalizacao de nomes de coluna;
- normalizacao de texto;
- padronizacao de identificadores;
- derivacao da coluna `bloco`;
- normalizacao de assuntos;
- selecao de primeiro valor nao nulo;
- serializacao de datas;
- garantia de colunas esperadas;
- deduplicacao `keep last` com ordenacao controlada.

### [pipeline_sources.py](E:/Projeto_Sentinel/scripts/pipeline_sources.py)

Responsavel por:

- localizar os arquivos corretos em `01_raw`;
- validar prefixos e extensoes;
- ler Excel para Pandas;
- concatenar datasets por fonte.

### [gss_matching.py](E:/Projeto_Sentinel/scripts/gss_matching.py)

Responsavel por duas funcoes distintas:

- enriquecimento complementar por `matricula` com dados de endereco e contato;
- matching de O.S. via regras de score quando `numero_os` estiver ausente no Zendesk.

### [main_etl.py](E:/Projeto_Sentinel/scripts/main_etl.py)

Orquestrador principal do pipeline. Executa a sequencia completa:

1. inicializacao do schema;
2. leitura das fontes brutas;
3. transformacao de N2, N1, audiencias e GSS;
4. construcao da tabela filha `ticket_assunto`;
5. deduplicacao por `ticket_id`;
6. enriquecimento complementar com GSS;
7. matching de O.S. para `SOLICITACAO`;
8. vinculacao entre `NOTIFICACAO` e `SOLICITACAO`;
9. geracao dos arquivos Silver;
10. UPSERT nas tabelas SQLite.

### Modulo analitico auxiliar

#### [queries.py](E:/Projeto_Sentinel/scripts/analytics/queries.py)

Reune consultas SQL executivas usadas pelo relatorio analitico.

#### [relatorio_executivo.py](E:/Projeto_Sentinel/scripts/analytics/relatorio_executivo.py)

Gera relatorio Excel em `outputs/`, com suporte a:

- execucao manual;
- execucao automatica;
- regra estrita de `D-1`;
- resumo executivo no terminal;
- abas analiticas;
- aba `DATA` para auditoria.

## Fluxo ETL Atual

### 1. Leitura e classificacao do relatorio geral

O ETL le o `ANALYTICS_BASE_TICKETS_GERAL` e aplica padronizacao de colunas com tolerancia a:

- variacao de acento;
- variacao de caixa;
- nomes equivalentes.

Em seguida, o dataset e separado internamente em:

- `SOLICITACAO`
- `NOTIFICACAO`

A identificacao utiliza o campo `formulario_ticket` por prefixo normalizado, e nao mais igualdade literal, para suportar valores reais como `Solicitações` e `Notificações`.

### 2. Arquivamento logico de ANEXO

Tickets classificados como anexo nao sao removidos do banco. Eles sao arquivados logicamente e ficam fora dos numeradores analiticos.

Regra atual:

- `tipo_manifestacao = ANEXO`
- ou `classificacao_notificacoes` contenha simultaneamente `INFORMATIVO` e `ANEXO`

Comportamento:

- o ticket permanece armazenado;
- `flag_arquivado_relatorio = 1`;
- nao deve compor entrada, resolucao, produtividade ou demais indicadores finais.

### 3. Protocolo institucional e chaves analiticas

O ETL preserva as regras ja validadas de:

- extracao de `protocolo_agenersa`;
- extracao de `protocolo_procon`;
- extracao de `protocolo_defensoria`;
- extracao de `protocolo_codecon`;
- geracao de `case_jec`.

O `case_id` e definido com prioridade para `protocolo_agenersa` e, na ausencia dele, assume `ticket_id`.

### 4. Tratamento de tickets duplicados por assunto

O Zendesk pode replicar a mesma reclamacao em varias linhas quando o mesmo `ticket_id` possui mais de uma tabulacao de assunto.

Decisao arquitetural adotada:

- `tickets` permanece com 1 linha por `ticket_id`;
- todos os assuntos distintos sao preservados em `ticket_assunto`.

Isso permite:

- contagem operacional correta de tickets;
- rastreabilidade real de todos os assuntos tratados;
- analise por assunto no Power BI sem inflar volume de tickets.

Campos de suporte em `tickets`:

- `qtde_assuntos_ticket`
- `flag_multiplos_assuntos`

### 5. Isolamento do N1

O N1 e processado e arquivado em `tickets_n1`, mas nao interfere nos indicadores do N2. Trata-se de uma camada historica/auxiliar, mantida para necessidades futuras e conciliacoes.

### 6. Enriquecimento complementar com GSS

O GSS nao sobrescreve dados validos do Zendesk.

Regra:

- para cada `matricula`, se o campo estiver vazio ou nulo no ticket;
- e existir valor util no GSS;
- o valor e preenchido no dataset final.

Colunas atualmente enriquecidas:

- `bairro`
- `municipio`
- `logradouro`
- `endereco`
- `numero_porta`
- `complemento`
- `telefone`
- `nome_cliente_gss`
- `nome_requerente_gss`

O contexto por matricula e construido selecionando a linha mais coerente do GSS com base em:

- completude informacional;
- `data_emissao`;
- `data_execucao`;
- `data_agendamento`;
- `gss_os_id`.

### 7. Enriquecimento de O.S. via GSS

Quando `numero_os` nao vier preenchido no Zendesk, o ETL tenta inferir a O.S. correta por `matricula`.

Estrategia:

- busca candidatas de O.S. na base filtrada do GSS;
- calcula score por proximidade de data;
- calcula score por similaridade textual entre ticket e servico;
- considera o status da O.S.;
- escolhe automaticamente apenas quando a pontuacao e a margem entre candidatas sao suficientes.

Saidas de auditoria:

- `numero_os_original`
- `numero_os_gss`
- `gss_os_id`
- `origem_numero_os`
- `status_vinculo_os`
- `score_vinculo_os`
- `criterio_vinculo_os`

### 8. Vinculo entre NOTIFICACAO e SOLICITACAO

O modelo atual preserva dois principios:

- a `SOLICITACAO` continua sendo o fato principal de analise;
- a `NOTIFICACAO` e mantida para rastreabilidade e relacionamento.

Prioridade de vinculo:

1. tabela manual `ticket_vinculos_manuais`;
2. chave explicita comum, se existir;
3. `matricula + protocolo_referencia`;
4. `matricula + assunto_normalizado`;
5. classificacao como `AMBIGUO`, `SEM_VINCULO` ou `NOTIFICACAO_NAO_CARREGADA` quando aplicavel.

Configuracao atual:

- janela maxima de vinculo: `7` dias;
- `data_entrada_reclamacao` acompanha a `data_criacao` da `SOLICITACAO`;
- `data_criacao_notificacao` preserva a data original da notificacao relacionada.

### 9. Derivacao da coluna Bloco

Regra absoluta de negocio:

- matricula iniciada por `40` -> `Bloco 4`
- matricula iniciada por `10` -> `Bloco 1`
- ausencia de matricula -> nulo

A coluna `bloco` e mantida em:

- `tickets`
- `tickets_notificacao`
- `tickets_n1`
- `gss_ordens_servico` (legado de compatibilidade)

## Arquivos Silver Gerados

Saidas atuais em `02_silver`:

- `ANALYTICS_BASE_TICKETS_GERAL_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_N1_processed.xlsx`
- `PRE_CONTENCIOSO_AUDIENCIAS_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_ASSUNTOS_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_VINCULOS_processed.xlsx`

Arquivos legados removidos automaticamente pelo ETL:

- `ANALYTICS_BASE_TICKETS_GERAL_SOLICITACAO_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_GERAL_NOTIFICACAO_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_NOTIFICACAO_processed.xlsx`
- `Base_GSS_processed.xlsx`

## Banco de Dados - Estrutura Atual

O schema Gold atual esta detalhado no arquivo [MER_Projeto_Sentinel.mmd](E:/Projeto_Sentinel/MER_Projeto_Sentinel.mmd).

### Tabelas de dominio

- `clientes`: base de matriculas unicas.
- `cases`: agrupador logico por `case_id`.

### Tabelas operacionais principais

- `tickets`: fato principal da operacao N2, no grao `1 linha = 1 ticket de solicitacao`.
- `tickets_notificacao`: persistencia dos tickets de notificacao.
- `audiencias`: agenda de audiencias e reagendamentos.

### Tabelas auxiliares de rastreabilidade

- `ticket_assunto`: todos os assuntos distintos por ticket.
- `ticket_relacionamentos`: resultado do vinculo entre solicitacao e notificacao.
- `ticket_vinculos_manuais`: overrides manuais de vinculo.
- `tickets_n1`: historico do N1, isolado do N2.

### Tabela legada de compatibilidade

- `gss_ordens_servico`: tabela mantida no schema por compatibilidade historica, mas nao faz parte da persistencia ativa do ETL atual.

## Principais Regras de Persistencia

Persistencia baseada em UPSERT:

- `clientes` por `matricula`
- `cases` por `case_id`
- `tickets` por `ticket_id`
- `tickets_notificacao` por `ticket_id`
- `tickets_n1` por `ticket_id`
- `ticket_assunto` por `ticket_assunto_id`
- `ticket_relacionamentos` por `ticket_solicitacao_id`
- `audiencias` por `ticket_id`

Beneficios:

- reprocessamento seguro;
- atualizacao incremental;
- ausencia de duplicidade por chave de negocio principal;
- compatibilidade com reposicoes de arquivos brutos.

## Execucao Operacional

### ETL principal

Com o projeto atualizado, a execucao padrao continua sendo apenas:

```bash
cd E:\Projeto_Sentinel
python scripts\main_etl.py
```

Esse comando:

- atualiza o schema;
- processa todas as fontes disponiveis em `01_raw`;
- gera os datasets Silver;
- persiste o Gold em SQLite.

### Modulo analitico

Relatorio executivo:

```bash
python scripts\analytics\relatorio_executivo.py
```

Ou em modo automatico:

```bash
python scripts\analytics\relatorio_executivo.py --auto
```

## Testes Automatizados

A suite de testes vive em `tests/unit/` e cobre os modulos criticos do pipeline.
Os testes sao escritos em `unittest` puro (sem dependencia de pytest), embora
rodem normalmente sob pytest tambem.

### Cobertura atual

| Arquivo | Modulo coberto | Foco |
|---|---|---|
| `tests/unit/test_pipeline_common.py` | `scripts/pipeline_common.py` | normalizacao de texto/identificadores, `derive_bloco`, `deduplicate_latest`, `serialize_datetime`, `first_not_null` |
| `tests/unit/test_db_utils.py` | `scripts/db_utils.py` | allowlist de tabelas, validacao de identificadores SQL, ativacao de PRAGMAs (`foreign_keys`, `journal_mode=WAL`) |
| `tests/unit/test_load_database.py` | `scripts/load_database.py` | UPSERT insert/update, rejeicao de tabela/coluna fora da allowlist, dataframe vazio |
| `tests/unit/test_business_rules.py` | `scripts/business_rules.py` | overrides manuais, flag de arquivamento, regras de auditoria |
| `tests/unit/test_contracts.py` | `scripts/contracts.py` | validacao de contratos de fonte (Zendesk, audiencias, GSS) |
| `tests/unit/test_gss_matching.py` | `scripts/gss_matching.py` | enriquecimento e matching de OS via score |
| `tests/unit/test_ticket_history.py` | `scripts/load_database.py` | versionamento SCD Tipo 2 do historico de tickets |
| `tests/unit/test_ticket_linking.py` | `scripts/main_etl.py` | vinculo `NOTIFICACAO -> SOLICITACAO` |

O `tests/conftest.py` injeta `scripts/` no `sys.path` automaticamente, entao
nao e preciso instalar o projeto como pacote para rodar a suite.

### Pre-requisitos

```bash
pip install pandas openpyxl xlsxwriter
# opcional, mas recomendado:
pip install pytest pytest-cov
```

### Como executar

A partir da raiz do repositorio:

```bash
# Toda a suite com unittest (built-in, sem dependencias extras)
python -m unittest discover -s tests/unit -p "test_*.py" -v

# Apenas um arquivo
python -m unittest tests.unit.test_pipeline_common -v

# Apenas um teste
python -m unittest tests.unit.test_db_utils.AllowlistTests.test_unknown_table_raises -v
```

Com pytest:

```bash
pytest tests/unit/                  # toda a suite
pytest tests/unit/ -k "normalize"   # filtra por nome
pytest tests/unit/ --cov=scripts    # com relatorio de cobertura
```

### Quando adicionar um teste

Adicione um novo arquivo `tests/unit/test_<modulo>.py` quando:

- introduzir uma regra de negocio nova em `business_rules.py` ou `gss_matching.py`;
- alterar normalizacao em `pipeline_common.py` (ex.: novo formato de matricula);
- mexer em `db_utils.py` ou `load_database.py` (qualquer mudanca em SQL ou allowlist);
- adicionar uma nova fonte e seu contrato em `contracts.py`.

Os testes devem usar SQLite `:memory:` ou `tempfile.TemporaryDirectory`
para isolar o filesystem; nao apontar para `03_database/pre_contencioso.db`.

## Orientacoes de Conferencia

Ao comparar relatorio cru versus relatorio processado do Zendesk N2:

- nao comparar volume bruto de linhas;
- comparar `ticket_id` distinto;
- considerar que tickets com multiplos assuntos geram repeticao no cru e sao consolidados no Gold.

Para analise de assuntos:

- usar `ticket_assunto`, nao `tickets`.

Para analise de entradas e resolucoes:

- usar `tickets` e filtrar `flag_arquivado_relatorio = 0`.

## Observacoes Tecnicas Relevantes

- `UserWarning` de parsing em `data_reagendamento` nao interrompe o pipeline, mas indica heterogeneidade de formato na origem.
- a base GSS pode conter ruido em alguns campos textuais, especialmente telefone e nome do requerente, o que demanda saneamento adicional se esses atributos forem usados em visualizacoes finais.
- o ETL atual ordena arquivos por `mtime`; para cenarios com muitos fragmentos do N1, recomenda-se futura evolucao para ordenacao pela data embutida no nome do arquivo.

## Proximos Passos Recomendados

- camada de views Gold para Power BI;
- padronizacao de data de referencia por dominio de negocio;
- saneamento adicional da qualidade textual do GSS;
- versao de auditoria operacional para reconciliacao de vinculos ambiguos;
- estrategia formal de versionamento de cargas por lote.

## Anexos Tecnicos

- README tecnico do projeto: [README.md](E:/Projeto_Sentinel/README.md)
- MER detalhado do schema: [MER_Projeto_Sentinel.mmd](E:/Projeto_Sentinel/MER_Projeto_Sentinel.mmd)
- banco Gold: [pre_contencioso.db](E:/Projeto_Sentinel/03_database/pre_contencioso.db)

