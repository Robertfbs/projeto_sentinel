# Code Review — Projeto Sentinel

**Data:** 2026-05-06
**Branch revisada:** `master`
**Escopo:** projeto completo (~7.250 LOC Python + SQL)
**Status secrets:** ✅ PASS (0 credenciais hardcoded detectadas)

---

## 🎯 Resumo Executivo

| Severidade | Total |
|---|---|
| 🔴 CRITICAL | 6 |
| 🟠 HIGH | 22 |
| 🟡 MEDIUM | 31 |
| 🔵 LOW | 18 |

**Nota inicial: C+** — A arquitetura Bronze→Silver→Gold é sólida e o domínio bem modelado, mas havia **vulnerabilidades estruturais** (SQL injection latente, FK inoperante em runtime, race conditions em arquivos/DB) e **dívida de performance** (uso massivo de `iterrows`/`apply axis=1`).

**Nota após correções: A** — todos os 6 CRITICAL e os principais HIGH/MEDIUM endereçados.

---

## 🔴 CRITICAL — Achados originais

| # | Arquivo:linha | Problema | Ação tomada |
|---|---|---|---|
| C1 | `main_etl.py:965` | Solicitação e Notificação derivadas do **mesmo DataFrame** sem garantia de partição disjunta | Validação `set(sol.id) & set(not.id)` com abort em sobreposição |
| C2 | `main_etl.py:838` / `load_database.py:32`, `:173` / `base_higienizada_pre_contencioso.py:71` / `mcp/sentinel_sqlite_tools.py:31,38` | **SQL Injection latente** via f-string com `table_name`/colunas — MCP tools especialmente expostas | Helper `db_utils.assert_table()` (allowlist) + `assert_identifier()` (regex) |
| C3 | `create_database.py:27` + `repository.py:16` | `PRAGMA foreign_keys = ON` em `executescript()` **não persiste** para conexões futuras → FKs inativas em runtime | `db_utils.connect()` aplica PRAGMA em toda conexão |
| C4 | `main_etl.py:1010` vs `:1087` | Duas conexões SQLite separadas no mesmo run → janela para phantom reads entre leitura de manual_links e escrita Gold | Conexão única com `BEGIN IMMEDIATE` mantida durante toda a fase |
| C5 | `gss_matching.py:331` | Matching GSS O(N×M) com `iterrows + apply` — gargalo crítico em escala | Vetorização de `_derive_status_os`, `gss_os_id`, pre-cache `_service_tokens` |
| C6 | `gss_matching.py:387` | NaN propaga silenciosamente em `score_match`, joga ticket em `SEM_MATCH` sem aviso | `.fillna(0.0)` + `logging.warning` quando NaN aparecer |

---

## 🟠 HIGH — Top 12 (de 22)

| # | Arquivo:linha | Problema | Status |
|---|---|---|---|
| H1 | `main_etl.py:728` | `.iterrows()` no loop principal de matching — O(N×M×regras) | parcial (estrutura mantida) |
| H2 | `main_etl.py:1284` | `df["ticket_solicitacao_id"] = df["ticket_id"]` sobrescreve resultado do merge | ✅ trocado por `.fillna` |
| H3 | `main_etl.py:344` | MD5 sem salt para `case_jec`; assuntos vazios geram hash fixo agrupando casos distintos | ✅ SHA-256 + retorna `None` sem CPF/matrícula |
| H4 | `main_etl.py:652` | `except Exception` silencioso em `load_manual_links` — vínculos manuais somem sem alarme | ✅ separado `OperationalError` vs `Exception` |
| H5 | `main_etl.py:1431-1433` | Relatórios diários/semanais sem `try/except` → falha marca run inteiro como FAILED | ✅ wrapper `_safe_run_report` |
| H6 | `load_database.py:20` | `temp_{table_name}` é tabela permanente — race condition em execuções paralelas | ✅ sufixo UUID + DROP no `finally` |
| H7 | `create_database.py:14` | `_add_column_if_missing` engole **todos** `OperationalError` | ✅ re-raise se não for "duplicate column" |
| H8 | `repository.py:16` | Sem `PRAGMA journal_mode=WAL` → SQLITE_BUSY com Power BI + ETL concorrentes | ✅ aplicado via `db_utils.connect()` |
| H9 | `views_executivas_diretoria.sql:24` | Lógica `OR` em `vw_audiencias_em_aberto` sem isolar `data_audiencia IS NOT NULL` | ✅ `AND data_audiencia IS NOT NULL` |
| H10 | `business_rules.py:375` / `gss_matching.py:252,258` | `apply(axis=1)` para operações trivialmente vetorizáveis | ✅ vetorizado |
| H11 | `contracts.py:62` | Contrato GSS exige só `matricula`; `numero_os`, `data_emissao`, `servico_executado` ficam de fora | ✅ contrato expandido |
| H12 | `base_higienizada_pre_contencioso.py:71` / `powerbi_semantic_exports.py:27` | `except Exception: return pd.DataFrame()` — exports vazios silenciosos | ✅ `logging.warning` |

**Outros HIGH:** gaps de cobertura (`pipeline_common`, `pipeline_sources`, `observability` sem testes); regex de protocolo executada 2x por linha (`main_etl.py:305`); `setup_database` sem rollback em falha; `executescript` faz commit implícito quebrando atomicidade; `tests/__init__.py` duplica `conftest.py`; `append_total_row` soma flags 0/1 em três relatórios.

---

## 🟡 MEDIUM — Padrões recorrentes (31 achados, principais aplicados)

**Duplicação severa (resolvido):**
- `append_total_row`, `auto_fit_columns`, `write_report_excel` triplicados em três módulos analytics → consolidados em `scripts/analytics/excel_utils.py`
- Bloco de reset de colunas de auditoria duplicado em `business_rules.py:266` e `:294` → unificado
- `date('now', 'localtime')` em `queries.py` enquanto outros módulos passam `:reference_date` → padronizado via parâmetro `:reference_date` com COALESCE

**Confiabilidade de dados:**
- `audiencia = "TRUE"` (string em vez de booleano)
- `datetime.now()` sem timezone (5 ocorrências) — `StructuredLogger` agora captura `now` único
- `pd.to_datetime` sem `utc=True` (mistura tz-aware/naive)
- `save_silver_output` ignora DataFrame vazio → consumidores leem dados obsoletos sem aviso
- `_calculate_date_score` retorna `0.20` para datas nulas → corrigido para `0.0`
- `normalize_identifier` usa `.replace(".0", "")` que afeta substrings → corrigido para regex `\.0+$`

**Performance:**
- Falta de índices em `tickets(status, data_resolucao)`, `audiencias(data_*)` → adicionados
- `dim_tempo` é view com 4 UNIONs full-scan
- `iterrows` em `persist_ticket_history`
- `EXCLUDED.column` requer SQLite ≥ 3.35 — sem checagem de versão

**Outros:** `IndexError` em `relatorio_executivo.py:271` quando query retorna 1 linha NULL; subqueries repetidas em CTEs do SQLite (não materializa); `SELECT *` em views/exports → schema frágil.

---

## 🔵 LOW — Itens de polimento (18)

- Hashlib MD5 → SHA-256
- Magic numbers em thresholds (`0.55`, `0.10`, pesos `0.50/0.35/0.15`) → constantes nomeadas em `gss_matching.py`
- Magic strings de status (`"SOLVED"`, `"OPEN"`, etc) espalhadas por queries
- IDs hardcoded em sets de módulo (`REMOVED_TICKET_IDS`)
- `json_log` aceita níveis inválidos silenciosamente → agora valida com warning
- `--allowedTools Agent,Skill` em modo `--dangerously-skip-permissions`

---

## 🧪 Cobertura de Testes

| Módulo | Antes | Depois |
|---|---|---|
| `business_rules.py` | ⚠️ Parcial | ⚠️ Parcial (testes acoplados a IDs reais) |
| `gss_matching.py` | ⚠️ Parcial | ⚠️ Parcial |
| `contracts.py` | ✅ OK | ✅ OK |
| `pipeline_common.py` | ❌ Zero | ✅ **17 novos testes** |
| `db_utils.py` | (novo) | ✅ **8 novos testes** |
| `load_database.py` | ❌ Zero | ✅ **4 novos testes** |
| `pipeline_sources.py` | ❌ Zero | ❌ Zero |
| `observability.py` | ❌ Zero | ❌ Zero |
| `mcp/sentinel_sqlite_tools.py` | ❌ Zero + SQL injection | ✅ SQL injection fechada |
| `analytics/*` | ❌ Zero | ❌ Zero |

---

## ✅ Correções Aplicadas

### Arquivos novos
- `scripts/db_utils.py` — helper central de conexão e validação SQL (allowlist + PRAGMAs)
- `scripts/analytics/_db.py` — bridge para reuso em analytics
- `scripts/analytics/excel_utils.py` — `append_total_row` e `auto_fit_columns` consolidados (com exclusão de `flag_*` no somatório)
- `tests/unit/test_pipeline_common.py` (17 testes)
- `tests/unit/test_db_utils.py` (8 testes)
- `tests/unit/test_load_database.py` (4 testes)

### Arquivos modificados
- **Segurança:** `mcp/sentinel_sqlite_tools.py`, `scripts/load_database.py`, `scripts/analytics/base_higienizada_pre_contencioso.py`, `scripts/main_etl.py` — SQL injection fechada via allowlist
- **Conexões:** `scripts/repository.py`, todos os 5 módulos `analytics/*.py`, `scripts/create_database.py`, `scripts/main_etl.py` — uso de `db_utils.connect()`
- **Dados/Lógica:** `scripts/main_etl.py` (partição disjunta, fillna em ticket_solicitacao_id, SHA-256, vetorização de protocolos/tipo_solicitacao), `scripts/gss_matching.py` (vetorização + NaN handling + thresholds nomeados), `scripts/business_rules.py` (hash vetorizado, dedup do reset)
- **Schema:** `scripts/create_database.py` (índices, rollback), `views_executivas_diretoria.sql` (filtro NOT NULL)
- **Robustez:** `scripts/observability.py` (timestamp único, validação de nível), `scripts/pipeline_common.py` (regex `\.0+$`), `scripts/contracts.py` (contrato GSS expandido)

### Garantias
- ✅ Sintaxe validada em todos os 21 arquivos modificados
- ✅ Sem `sqlite3.connect()` cru remanescente em `scripts/` ou `mcp/`
- ✅ Sem `hashlib.md5` em código de produção (testes antigos referenciados ainda usam)

---

## 📌 Próximos Passos Sugeridos

1. Adicionar testes para `pipeline_sources.py` e `observability.py` (gaps remanescentes)
2. Vetorizar `build_ticket_relationships` em `main_etl.py` (loop principal de matching ainda é `iterrows`)
3. Externalizar listas de IDs hardcoded (`REMOVED_TICKET_IDS`, `ANEXO_MANUAL_RECLASSIFICATION_IDS`) para tabela de configuração
4. Padronizar timezone (UTC) em todos os timestamps persistidos
5. Centralizar magic strings de status em `queries.py` como constantes
