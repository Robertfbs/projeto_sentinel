# TechSpec — Projeto Sentinel

## Resumo Executivo

O Projeto Sentinel é uma plataforma de dados baseada em Python + SQLite, estruturada em Bronze > Silver > Gold, para consolidar, tratar, enriquecer e disponibilizar dados operacionais de CX e pré-contencioso oriundos principalmente do Zendesk e complementarmente do GSS/SCAE.

A solução atual opera sobre arquivos Excel extraídos manualmente, aplica regras de negócio já validadas, persiste dados em `pre_contencioso.db` e gera saídas executivas e analíticas em Excel. A evolução proposta nesta TechSpec é integralmente aditiva: ela fortalece governança, observabilidade, versionamento, contratos de dados, consumo semântico para Power BI e preparação AI-ready sem alterar o comportamento atual do pipeline.

## Arquitetura do Sistema

### Visão Geral dos Componentes

Componentes canônicos do Sentinel:
- `scripts/main_etl.py`
- `scripts/create_database.py`
- `scripts/load_database.py`
- `scripts/pipeline_sources.py`
- `scripts/pipeline_common.py`
- `scripts/gss_matching.py`
- `scripts/analytics/relatorio_diario_pre_contencioso.py`
- `scripts/analytics/produtividade_semanal.py`
- `scripts/analytics/relatorio_executivo.py`
- `scripts/analytics/base_higienizada_pre_contencioso.py`
- `03_database/pre_contencioso.db`
- `02_silver/*.xlsx`
- `outputs/*.xlsx`

Componentes aditivos recomendados:
- `scripts/business_rules.py`
- `scripts/contracts.py`
- `scripts/schema_validation.py`
- `scripts/observability.py`
- `scripts/repository.py`
- `scripts/analytics/powerbi_semantic_exports.py`
- `scripts/analytics/gold_ai_ready.py`

Componentes presentes no repositório, mas não autoritativos para o Sentinel:
- `AGENTS.md` da raiz, hoje orientado a outro stack;
- `frontend/`, `backend/`, `e2e/`, `package.json` e artefatos Bun/Vite;

Relacionamentos principais:
- `main_etl.py` orquestra ingestão, transformação, enriquecimento, persistência e geração de saídas.
- `pipeline_sources.py` localiza e lê arquivos por prefixo.
- `pipeline_common.py` centraliza utilidades técnicas reutilizáveis.
- `gss_matching.py` executa enriquecimento complementar.
- `business_rules.py` deve consolidar regras de negócio hoje dispersas.
- `load_database.py` deve continuar responsável pela persistência.
- `create_database.py` deve evoluir o schema de forma aditiva.
- Scripts de analytics consomem diretamente a Gold, nunca a origem bruta.

Fluxo de dados:
1. arquivos chegam em `01_raw`;
2. contratos e schema são validados;
3. dados são transformados e normalizados;
4. regras de negócio e auditoria são aplicadas;
5. enriquecimento GSS é executado;
6. Silver é gerada para rastreio operacional;
7. Gold é persistida em SQLite;
8. saídas executivas, semânticas e AI-ready são geradas a partir da Gold.

Estrutura de pastas sugerida para evolução:
- manter a estrutura atual;
- adicionar, quando aprovado, módulos de governança, observabilidade e repository dentro de `scripts/`;
- adicionar saídas semânticas em `outputs/semantic/`;
- adicionar camada AI-ready em `outputs/ai_ready/`;
- adicionar rules em `.agents/rules/`;
- manter skills em `.agents/skills/` seguindo o padrão `SKILL.md + assets + references + scripts`.

## Design de Implementação

### Interfaces Principais

Interfaces existentes:
```python
def setup_database() -> None
def upsert_sqlite(df: pd.DataFrame, table_name: str, primary_key: str, conn: sqlite3.Connection) -> None
def extract_source_reports(raw_dir: Path, source_key: str) -> pd.DataFrame
def transform_data(df: pd.DataFrame, ticket_kind: str) -> pd.DataFrame
def enrich_with_gss(df_tickets: pd.DataFrame, df_gss: pd.DataFrame) -> pd.DataFrame
def enrich_tickets_with_gss(df_tickets: pd.DataFrame, df_gss: pd.DataFrame) -> pd.DataFrame
def process_and_load() -> None
def generate_daily_pre_contencioso_report(db_path: Path | None = None, reference_date: date | None = None) -> Path
def generate_produtividade_semanal_report(db_path: Path | None = None, reference_date: date | None = None) -> Path
def generate_base_higienizada_pre_contencioso(db_path: Path | None = None, reference_date: date | None = None) -> Path
```

Interfaces aditivas recomendadas:
```python
class DatabaseRepository:
    def execute(self, sql: str, params: dict | tuple | None = None) -> None: ...
    def fetch_df(self, sql: str, params: dict | tuple | None = None) -> pd.DataFrame: ...
    def begin(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

class DataContractValidator:
    def validate_source(self, source_name: str, df: pd.DataFrame) -> list[dict]: ...

class EtlRunTracker:
    def start_run(self, pipeline_name: str) -> str: ...
    def finish_run(self, run_id: str, status: str, tempo_execucao: float, qtd_registros_processados: int, erro: str | None = None) -> None: ...

class StructuredLogger:
    def log_step(self, run_id: str, etapa: str, status: str, volume: int | None = None, tempo_etapa: float | None = None, erro: str | None = None, detalhes: dict | None = None) -> None: ...

def apply_business_rules(df: pd.DataFrame, ticket_kind: str) -> pd.DataFrame
def persist_tickets_scd2(df_tickets: pd.DataFrame, conn: sqlite3.Connection, run_id: str) -> None
def generate_powerbi_semantic_exports(db_path: Path | None = None) -> dict[str, Path]
def generate_gold_ai_ready(db_path: Path | None = None, reference_date: date | None = None) -> Path
```

### Modelos de Dados

Entidades principais já existentes:
- `clientes`
- `cases`
- `tickets`
- `tickets_notificacao`
- `tickets_n1`
- `ticket_assunto`
- `ticket_relacionamentos`
- `ticket_vinculos_manuais`
- `audiencias`
- `gss_ordens_servico`
- `tickets_auditoria_classificacao`

Entidades aditivas recomendadas:
- `etl_runs`
- `etl_logs`
- `tickets_auditoria_operacional`
- `gold_ai_ready`
- views ou tabelas materializadas da camada semântica:
  - `fato_tickets`
  - `fato_audiencias`
  - `dim_tempo`
  - `dim_canal`
  - `dim_status`
  - `dim_atribuido`
  - `dim_assunto`

Evolução crítica em `tickets`:
- adicionar `data_inicio_vigencia`
- adicionar `data_fim_vigencia`
- adicionar `flag_ativo`

Objetivo:
- permitir SCD Type 2;
- reconstrução do estado histórico;
- auditoria temporal sem alterar a lógica atual de uso corrente.

Colunas críticas já consolidadas em `tickets`:
- dados centrais do ticket;
- campos de vínculo com notificação;
- enriquecimento GSS;
- governança e auditoria;
- atributos analíticos auxiliares como `bloco`, múltiplos assuntos e protocolos.

Semântica analítica oficial:
- grão principal de `tickets`: 1 linha por `ticket_id`;
- `ticket_assunto` preserva detalhe sem romper o grão principal;
- `audiencias`: 1 linha por audiência;
- `tickets_notificacao` permanece domínio auxiliar, não substitui o fato principal de solicitação em dashboards executivos padrão.

Camada AI-ready:
- deve derivar da Gold validada;
- deve remover ruído textual;
- deve manter texto normalizado e contexto suficiente para embeddings, classificação futura e busca semântica;
- não deve incluir registros arquivados logicamente na visão padrão AI-ready.

### Endpoints de API

Não se aplica no estado atual.

O Sentinel não expõe API HTTP nem opera como serviço web. O uso de MCP, skills e agentes deve ser entendido como camada de automação assistiva, não como substituição da execução atual do pipeline.

## Pontos de Integração

Fontes externas atuais:
- relatórios Excel do Zendesk:
  - `ANALYTICS_BASE_TICKETS_GERAL*`
  - `ANALYTICS_BASE_TICKETS_N1*`
  - `PRE_CONTENCIOSO_AUDIENCIAS*`
- relatório Excel do GSS/SCAE:
  - `Base_GSS*`

Contratos de dados obrigatórios:
- validar presença de colunas mínimas por fonte;
- validar compatibilidade de layout;
- validar disponibilidade dos campos críticos para regras de negócio;
- falhar em caso de quebra crítica;
- registrar erro detalhado em observabilidade.

Validação de schema de Excel:
- mapear aliases conhecidos;
- detectar colunas obrigatórias ausentes;
- emitir mensagem clara de falha;
- impedir continuidade silenciosa quando a quebra inviabilizar regras centrais.

Tratamento de erros:
- logs estruturados em JSON;
- persistência em `etl_logs`;
- fallback de escrita para relatórios bloqueados;
- detecção de arquivo Excel aberto/bloqueado;
- backup antes de correções controladas;
- fail-fast em quebra crítica de contrato.

## Abordagem de Testes

### Testes Unidade

Cobertura mínima obrigatória:
- normalização de assunto sem fallback para título;
- derivação de `bloco`;
- regras de `ANEXO` e `Informativo::Anexo`;
- vínculo `SOLICITAÇÃO x NOTIFICAÇÃO`;
- enriquecimento GSS sem sobrescrita indevida;
- persistência de overrides manuais no ETL;
- contratos de dados;
- regras de auditoria;
- versionamento temporal em `tickets`.

Estrutura sugerida:
- `tests/unit/test_business_rules.py`
- `tests/unit/test_contracts.py`
- `tests/unit/test_gss_matching.py`
- `tests/unit/test_ticket_linking.py`
- `tests/unit/test_audit_rules.py`

### Testes de Integração

Cenários principais:
- descoberta de arquivos + transformação + persistência;
- ETL + contratos de dados;
- ETL + `etl_runs` e `etl_logs`;
- ETL + regras persistidas de correção manual;
- ETL + enriquecimento GSS;
- banco SQLite + geração de relatórios;
- base higienizada refletindo correções persistidas.

Estrutura sugerida:
- `tests/integration/test_main_etl_flow.py`
- `tests/integration/test_sqlite_outputs.py`
- `tests/integration/test_reports_outputs.py`

### Testes de E2E

Não se aplica ao núcleo do Sentinel no estado atual.

Observação:
- o template técnico menciona Playwright, mas isso não é componente canônico do Sentinel de dados;
- qualquer E2E futuro deve ser limitado a fluxos de automação auxiliares e não substitui os testes de ETL e reconciliação.

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. Evolução do schema em `create_database.py`
- `etl_runs`
- `etl_logs`
- `tickets_auditoria_operacional`
- colunas SCD Type 2 em `tickets`

2. Contratos de dados e validação de schema
- `contracts.py`
- `schema_validation.py`

3. Refatoração de responsabilidades
- criar `business_rules.py`
- eliminar duplicidade entre `enrich_with_gss` e `enrich_tickets_with_gss`

4. Observabilidade estruturada
- `observability.py`
- `run_id`
- logs JSON
- persistência em `etl_runs` e `etl_logs`

5. Abstração de banco
- `repository.py`

6. Camada semântica para BI
- exportações ou views de fatos e dimensões
- definição oficial de métricas e filtros

7. Camada AI-ready
- `gold_ai_ready`

8. Testes automatizados e reconciliação
- cobertura mínima obrigatória
- validação cruzada entre banco e saídas derivadas

### Dependências Técnicas

Dependências atuais:
- Python 3.10+
- pandas
- sqlite3
- openpyxl
- xlsxwriter
- arquivos Excel exportados manualmente
- Power BI para consumo analítico

Dependências aditivas recomendadas:
- `pytest`
- serialização JSON para observabilidade
- biblioteca opcional de validação de schema, se mantiver simplicidade operacional

Bloqueios potenciais:
- layout dos relatórios de origem mudar sem aviso;
- arquivos obrigatórios não chegarem em `01_raw`;
- relatório de saída estar aberto no momento da escrita;
- correções manuais não serem persistidas no ETL;
- coexistência temporária entre UPSERT atual e histórico SCD Type 2;
- confusão operacional causada por artefatos de outros stacks presentes no repositório.

## Monitoramento e Observabilidade

Estado atual:
- `logging` simples;
- validações manuais via SQL;
- conferência manual de `02_silver` e `outputs`;
- auditoria pontual no banco.

Evolução obrigatória:
- `etl_runs` com:
  - `run_id`
  - `data_execucao`
  - `status`
  - `tempo_execucao`
  - `qtd_registros_processados`
  - `erro`
- `etl_logs` com:
  - `run_id`
  - `timestamp_log`
  - `nivel`
  - `etapa`
  - `status`
  - `volume_processado`
  - `tempo_etapa`
  - `erro`
  - `payload_json`

Indicadores mínimos por execução:
- total de arquivos encontrados por fonte;
- total de arquivos rejeitados;
- volume de linhas por origem;
- volume de tickets persistidos;
- volume de registros arquivados logicamente;
- volume de tickets auditados;
- volume de vínculos gerados;
- volume de enriquecimentos GSS;
- status final da execução;
- status da geração dos relatórios.

Observação importante:
- o template técnico menciona Prometheus/Grafana, mas não há evidência de infraestrutura disponível para isso no contexto atual;
- portanto, a observabilidade oficial do Sentinel deve permanecer baseada em SQLite + logs JSON até nova aprovação arquitetural.

## Considerações Técnicas

### Decisões Principais

- manter SQLite como banco Gold oficial;
- manter ETL em Python com pandas;
- preservar arquitetura Bronze > Silver > Gold;
- manter segregação de auditoria em vez de exclusão física;
- manter base higienizada separada da Silver;
- persistir correções recorrentes no ETL em vez de confiar em updates diretos no banco;
- introduzir observabilidade, contratos e SCD Type 2 de forma aditiva;
- formalizar camada semântica para Power BI e camada AI-ready;
- tratar skills, rules e MCP como camada de governança e automação, não como substituição do pipeline.

### Riscos Conhecidos

- mudança silenciosa de layout nas origens;
- perda de correções se não forem convertidas em regra persistente;
- dependência da classificação operacional correta na origem;
- divergência entre análises manuais externas e banco oficial;
- qualidade do enriquecimento GSS depender da matrícula e do dado de origem;
- ausência de prazo/vencimento estruturado por ticket;
- bloqueio de arquivos Excel durante a escrita;
- aumento de complexidade com SCD Type 2 se não houver convenção clara de `flag_ativo`;
- repositório conter templates, AGENTS e protótipos de MCP desalinhados do stack do Sentinel;
- templates atuais apresentarem problema de encoding para reutilização corporativa.

Mitigações:
- alterações aditivas no schema;
- backups antes de correções controladas;
- validação por contrato;
- logs estruturados;
- base higienizada derivada da Gold;
- rules de governança;
- skills específicas do Sentinel;
- MCP aderente ao stack Python + SQLite.

### Conformidade com Skills Padrões

Skills observadas no repositório:
- `.agents/skills/cria-prd`
- `.agents/skills/cria-techspec`
- `.agents/skills/executar-task`
- diversas skills de frontend, React, Cloudflare e Claude API

Diretriz para o Sentinel:
- usar apenas o padrão estrutural das skills existentes;
- não herdar regras de stacks não utilizadas;
- propor skills novas e específicas do Sentinel;
- não tratar skills genéricas de frontend, React, Cloudflare ou Claude API como padrão técnico deste produto.

### Arquivos relevantes e dependentes

Arquivos principais:
- `E:\Projeto_Sentinel\scripts\main_etl.py`
- `E:\Projeto_Sentinel\scripts\create_database.py`
- `E:\Projeto_Sentinel\scripts\load_database.py`
- `E:\Projeto_Sentinel\scripts\pipeline_common.py`
- `E:\Projeto_Sentinel\scripts\pipeline_sources.py`
- `E:\Projeto_Sentinel\scripts\gss_matching.py`

Arquivos analíticos:
- `E:\Projeto_Sentinel\scripts\analytics\relatorio_diario_pre_contencioso.py`
- `E:\Projeto_Sentinel\scripts\analytics\produtividade_semanal.py`
- `E:\Projeto_Sentinel\scripts\analytics\relatorio_executivo.py`
- `E:\Projeto_Sentinel\scripts\analytics\base_higienizada_pre_contencioso.py`
- `E:\Projeto_Sentinel\scripts\analytics\queries.py`

Documentos e templates:
- `E:\Projeto_Sentinel\prd.md`
- `E:\Projeto_Sentinel\techspec.md`
- `E:\Projeto_Sentinel\templates\prd-template.md`
- `E:\Projeto_Sentinel\templates\techspec-template.md`
- `E:\Projeto_Sentinel\README.md`
- `E:\Projeto_Sentinel\MER_Projeto_Sentinel.mmd`
- `E:\Projeto_Sentinel\views_executivas_diretoria.sql`

Estruturas auxiliares:
- `E:\Projeto_Sentinel\.agents\skills\`
- `E:\Projeto_Sentinel\mcp\`
- `E:\Projeto_Sentinel\powerbi\`

Pastas de dados:
- `E:\Projeto_Sentinel\01_raw`
- `E:\Projeto_Sentinel\02_silver`
- `E:\Projeto_Sentinel\03_database`
- `E:\Projeto_Sentinel\outputs`
