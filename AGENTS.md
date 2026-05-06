# AGENTS.md

Guia para agentes de IA ao trabalhar no **Projeto Sentinel**.

O Sentinel é um **projeto de dados** baseado em **Python + SQLite + Excel + Power BI**, com arquitetura **Bronze > Silver > Gold** e foco em CX, pré-contencioso, auditoria de dados e consumo analítico executivo.

## Prioridades

- Preserve integralmente as regras de negócio já validadas.
- Faça apenas mudanças aditivas e não destrutivas.
- Nunca trate artefatos de outros stacks presentes no repositório como arquitetura oficial do Sentinel.
- O banco oficial do projeto é `03_database/pre_contencioso.db`.
- Outputs executivos e analíticos devem sempre refletir a Gold oficial.
- Correções recorrentes devem ser persistidas no ETL, não apenas no banco.
- Não execute comandos Git destrutivos sem permissão explícita do usuário.

## Stack Oficial do Sentinel

- Python 3.10+
- pandas
- sqlite3
- openpyxl
- xlsxwriter
- Excel como origem manual e saída executiva
- Power BI como consumo analítico

## Arquitetura Oficial

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

## Componentes Canônicos

- `scripts/main_etl.py`
- `scripts/create_database.py`
- `scripts/load_database.py`
- `scripts/pipeline_sources.py`
- `scripts/pipeline_common.py`
- `scripts/gss_matching.py`
- `scripts/analytics/*`
- `03_database/pre_contencioso.db`
- `outputs/*`

## Estruturas Auxiliares Presentes no Repositório

O repositório contém também:
- `.agents/skills`
- `.agents/rules`
- `mcp`
- `frontend`
- `backend`
- `e2e`
- artefatos Bun/Vite/Playwright

Esses itens **não substituem** a arquitetura oficial do Sentinel. Só podem ser usados quando forem explicitamente adaptados ao domínio e ao stack do projeto de dados.

## Skills Relevantes do Sentinel

Preferir as skills específicas do projeto:
- `cria-prd-sentinel`
- `cria-techspec-sentinel`
- `valida-dados-sentinel`
- `executa-etl-sentinel`
- `gera-relatorio-sentinel`
- `valida-contrato-dados-sentinel`

## Regras Operacionais

- `ANEXO` e `Informativo::Anexo` ficam fora do executivo.
- A Gold é a fonte oficial de verdade do produto.
- Não use update direto no banco como caminho padrão.
- Toda mudança recorrente deve virar regra persistida no ETL.
- Relatórios devem refletir a Gold e seguir suas regras temporais já validadas.

## Anti-padrões

1. Usar stacks paralelos do repositório como referência canônica do Sentinel.
2. Corrigir repetidamente no banco sem persistir no ETL.
3. Gerar outputs sem reconciliar com a Gold.
4. Tratar dado auditável como dado executivo.
5. Ignorar contratos de dados e mudanças de layout das origens.
