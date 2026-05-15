# MCP do Projeto Sentinel

Esta pasta contém a base canônica de contexto para automação assistida do Sentinel.

Diretrizes:
- o MCP do Sentinel é uma camada de contexto e orquestração, não substitui o ETL atual;
- a fonte oficial continua sendo `03_database/pre_contencioso.db`;
- o stack oficial continua sendo Python + SQLite + Excel + Power BI;
- protótipos Node/PostgreSQL/random não fazem parte da implementação oficial.

Arquivos principais:
- `sentinel-mcp-architecture.md`
- `sentinel-context-registry.md`
- `sentinel-tool-catalog.md`
- `sentinel-agent-registry.md`
- `sentinel_mcp_manifest.py`
- `sentinel_mcp_server_stub.py`
- `sentinel_sqlite_tools.py`
