# MCP Server Sentinel

Servidor MCP Python do Projeto Sentinel para expor contexto, analytics, relatórios governados e rascunhos de integração.

## Escopo

Tools registradas:
- `sentinel.health`: valida servidor, config e Gold oficial.
- `gold.list_tables`: lista tabelas e views da Gold.
- `gold.describe_table`: descreve colunas e contagem de uma tabela ou view.
- `analytics.weekly_productivity`: produtividade da semana útil anterior.
- `analytics.channel_volume`: volumetria de entrada por canal.
- `tickets.processed`: lista controlada de tickets processados sem PII.
- `etl.last_run`: última execução registrada em `etl_runs`/`etl_logs`.
- `reports.generate_weekly_productivity`: gera relatório semanal com confirmação.
- `reports.generate_executive`: gera relatório executivo com confirmação.
- `powerbi.export_semantic_model`: exporta camada semântica Power BI com confirmação.
- `integrations.teams.prepare_message`: prepara rascunho Teams, sem envio.
- `integrations.outlook.prepare_email`: prepara rascunho Outlook, sem envio.
- `integrations.planner.prepare_task`: prepara rascunho Planner, sem criação.

Resources registrados:
- `sentinel://project/readme`
- `sentinel://project/prd`
- `sentinel://project/techspec`
- `sentinel://schema/gold`
- `sentinel://rules/catalog`
- `sentinel://outputs/catalog`

Prompts registrados:
- `resumo_executivo_produtividade`
- `auditoria_tickets`
- `relatorio_executivo_corporativo`
- `rascunho_microsoft_teams`

## Garantias

- Nao executa ETL.
- Nao escreve na Gold.
- Nao aceita SQL livre.
- Usa `03_database/pre_contencioso.db` como unica Gold valida.
- Registra chamadas em `mcp_server/logs/mcp_audit.jsonl`.
- Geração de arquivos exige `confirmacao=True`.
- Integrações Microsoft operam em `draft_only`.

## Ambiente recomendado

```powershell
python -m venv .venv-mcp
.\.venv-mcp\Scripts\python.exe -m pip install "mcp[cli]" pandas xlsxwriter openpyxl
```

## Testes locais

```powershell
.\.venv-mcp\Scripts\python.exe -m unittest tests.unit.test_mcp_server
```

## Execucao

Rodar servidor MCP via CLI:

```powershell
.\.venv-mcp\Scripts\mcp.exe run mcp_server\server.py
```

Abrir com MCP Inspector:

```powershell
.\.venv-mcp\Scripts\mcp.exe dev mcp_server\server.py
```

Use o Inspector apenas depois dos testes locais passarem.

## Exemplos de uso seguro

Analytics read-only:

```text
analytics.weekly_productivity(reference_date="2026-05-13")
analytics.channel_volume(start_date="2026-05-01", end_date="2026-05-08")
tickets.processed(start_date="2026-05-01", end_date="2026-05-08", limit=20)
etl.last_run(log_limit=20)
```

Geração governada:

```text
reports.generate_weekly_productivity(confirmacao=True)
reports.generate_executive(confirmacao=True, start_date="2026-05-01", end_date="2026-05-08")
powerbi.export_semantic_model(confirmacao=True)
```

Nunca use `confirmacao=True` de forma automática; a confirmação deve refletir autorização humana.

Integrações Microsoft:

```text
integrations.teams.prepare_message(...)
integrations.outlook.prepare_email(...)
integrations.planner.prepare_task(...)
```

Essas tools apenas preparam rascunhos. Elas não enviam mensagens, não criam e-mails e não criam tarefas.
