# Projeto Sentinel

Mini Data Warehouse analitico para tratamento de manifestacoes recebidas via Zendesk, com foco em operacao de CX, pre-contencioso e consumo em Power BI.

O projeto consolida relatorios operacionais, padroniza dados, extrai protocolos institucionais, relaciona tickets de `NOTIFICACAO` e `SOLICITACAO` e persiste tudo em um banco SQLite pronto para analise.

## Objetivo

Garantir uma base analitica confiavel para medir volume, SLA, aging e evolucao de manifestacoes regulatorias e institucionais, preservando:

- a data oficial de entrada da reclamacao a partir da `NOTIFICACAO`
- os dados analiticos completos da `SOLICITACAO`
- a rastreabilidade entre os dois tickets da mesma reclamacao

## Stack

- Python 3.10+
- Pandas
- SQLite
- openpyxl
- xlsxwriter

## Arquitetura

O pipeline segue o padrao `Bronze > Silver > Gold`.

- `01_raw/`: relatorios brutos exportados do Zendesk
- `02_silver/`: arquivos tratados e enriquecidos
- `03_database/`: banco SQLite final
- `scripts/`: motor ETL

Fluxo:

```text
Zendesk Export
   ->
01_raw
   ->
ETL Python
   ->
02_silver
   ->
SQLite
   ->
Power BI / Analytics
```

## Estrutura do projeto

```text
Projeto_Sentinel/
|-- 01_raw/
|-- 02_silver/
|-- 03_database/
|   `-- pre_contencioso.db
|-- scripts/
|   |-- create_database.py
|   |-- load_database.py
|   `-- main_etl.py
|-- .gitignore
`-- README.md
```

## Entradas esperadas

O ETL suporta dois tipos de relatorio Zendesk:

- `SOLICITACAO`: arquivos com prefixo `ANALYTICS_BASE_TICKETS` e sem `NOTIFICACAO` no nome
- `NOTIFICACAO`: arquivos com `NOTIFICACAO` no nome, por exemplo `ANALYTICS_BASE_TICKETS_NOTIFICACAO_mar_2026.xlsx`

Os arquivos devem ser salvos em `01_raw/`.

## Como executar

### 1. Instalar dependencias

```bash
pip install pandas openpyxl xlsxwriter
```

### 2. Adicionar os arquivos do Zendesk

Copie os relatorios para `01_raw/`.

### 3. Rodar o pipeline

```bash
python scripts/main_etl.py
```

## O que o pipeline faz

### Ingestao

- le relatorios separados de `SOLICITACAO` e `NOTIFICACAO`
- padroniza nomes de colunas, mesmo com variacoes de acentuacao
- remove tickets do tipo `ANEXO`

### Enriquecimento

Mantem as regras ja existentes:

- extracao de protocolo Agenersa
- extracao de protocolo PROCON
- extracao de protocolo Defensoria
- extracao de protocolo CODECON
- geracao de `case_jec`

### Relacionamento entre tickets

O vinculo entre `NOTIFICACAO` e `SOLICITACAO` segue esta prioridade:

1. chave explicita comum, se existir no relatorio
2. `matricula + numero_os`
3. `matricula + protocolo_referencia`
4. `matricula + assunto_normalizado`
5. vinculo manual para casos ambiguos

Regras de seguranca:

- a `data_criacao` original do ticket nao e sobrescrita
- a data oficial da reclamacao vai para `data_entrada_reclamacao`
- o ticket analitico continua sendo a `SOLICITACAO`
- vinculos ambiguos nao sao forcados automaticamente

## Modelo de dados

### Tabelas principais

- `clientes`: dimensao basica por matricula
- `cases`: agrupamento logico dos tickets
- `tickets`: fato principal da `SOLICITACAO`
- `tickets_notificacao`: persistencia e auditoria da `NOTIFICACAO`
- `ticket_relacionamentos`: resultado do vinculo entre os dois tickets
- `ticket_vinculos_manuais`: override manual para casos ambiguos
- `audiencias`: informacoes de audiencia vinculadas ao ticket de solicitacao

### Campos analiticos de vinculo

Na tabela `tickets`, os principais campos adicionados para analise sao:

- `ticket_solicitacao_id`
- `ticket_notificacao_id`
- `data_entrada_reclamacao`
- `data_criacao_solicitacao`
- `dias_defasagem_abertura`
- `criterio_vinculo`
- `confianca_vinculo`
- `status_vinculo`

## Regras de persistencia

- UPSERT por chave primaria
- `tickets`: UPSERT por `ticket_id`
- `tickets_notificacao`: UPSERT por `ticket_id`
- `ticket_relacionamentos`: UPSERT por `ticket_solicitacao_id`
- `audiencias`: UPSERT por `ticket_id`

Isso permite reprocessamento sem duplicidade e atualizacao incremental dos dados.

## Saidas geradas

Na pasta `02_silver/`, o pipeline pode gerar:

- `ANALYTICS_BASE_TICKETS_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_NOTIFICACAO_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_VINCULOS_processed.xlsx`

No banco `03_database/pre_contencioso.db`, a base final fica pronta para consumo em Power BI.

## Uso analitico recomendado

Para indicadores de entrada, SLA e aging:

- use `tickets` como tabela fato principal
- use `data_entrada_reclamacao` como data oficial da reclamacao
- mantenha `data_criacao` como data original do ticket de solicitacao
- monitore `status_vinculo` para identificar `VINCULADO`, `MANUAL`, `AMBIGUO`, `SEM_VINCULO` e `NOTIFICACAO_NAO_CARREGADA`

## Operacao assistida

Casos ambiguos podem ser resolvidos pela tabela `ticket_vinculos_manuais`, que tem precedencia sobre os criterios automaticos.

Exemplo de uso:

```sql
INSERT INTO ticket_vinculos_manuais (
    ticket_solicitacao_id,
    ticket_notificacao_id,
    justificativa,
    usuario
) VALUES (
    200123,
    100987,
    'Validado manualmente pela operacao',
    'analytics'
);
```

## Observacoes

- o projeto foi desenhado para manter compatibilidade com o consumo atual no Power BI
- as mudancas de vinculo foram implementadas de forma aditiva, sem remover colunas existentes
- o banco pode ser recriado ou atualizado executando `python scripts/create_database.py`

## Autor

Equipe Analytics - Pre-Contencioso
