from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List


@dataclass(frozen=True)
class McpContext:
    name: str
    description: str


@dataclass(frozen=True)
class McpTool:
    name: str
    domain: str
    description: str


@dataclass(frozen=True)
class McpAgent:
    name: str
    description: str
    responsibilities: List[str]


CONTEXTS = [
    McpContext("sentinel_project_context", "Contexto estrutural do projeto, PRD, TechSpec e componentes canônicos."),
    McpContext("sentinel_operational_context", "Contexto operacional do ETL, fontes, execuções e outputs."),
    McpContext("sentinel_analytics_context", "Contexto semântico de métricas, fatos, dimensões e filtros executivos."),
    McpContext("sentinel_audit_context", "Contexto de auditoria, exceções, inconsistências e overrides."),
    McpContext("sentinel_ai_ready_context", "Contexto de campos limpos, textos normalizados e base preparada para IA."),
]


TOOLS = [
    McpTool("etl.list_sources", "etl", "Lista fontes operacionais esperadas e sua situação de leitura."),
    McpTool("etl.validate_contracts", "etl", "Valida contratos mínimos das fontes antes de uma carga."),
    McpTool("etl.preview_run", "etl", "Resume o escopo e os riscos de uma execução antes da carga."),
    McpTool("etl.inspect_last_run", "etl", "Expõe informações da última execução registrada."),
    McpTool("analytics.list_metrics", "analytics", "Lista métricas oficiais do produto e sua semântica."),
    McpTool("analytics.describe_metric", "analytics", "Descreve uma métrica oficial e suas regras de inclusão/exclusão."),
    McpTool("analytics.preview_fact_tickets", "analytics", "Apresenta o grão e o escopo do fato principal de tickets."),
    McpTool("analytics.preview_dimensional_model", "analytics", "Resume fatos, dimensões e uso esperado no Power BI."),
    McpTool("audit.find_inconsistencies", "audit", "Lista inconsistências e exceções operacionais conhecidas."),
    McpTool("audit.compare_gold_vs_output", "audit", "Compara a Gold com outputs executivos e analíticos."),
    McpTool("audit.list_manual_overrides", "audit", "Lista correções persistidas ou exceções governadas."),
    McpTool("ai.preview_ai_ready_dataset", "ai", "Resume a camada AI-ready e seus campos sem ruído executivo."),
]


AGENTS = [
    McpAgent(
        "sentinel-etl-agent",
        "Agente focado em ETL, contratos de dados e reconciliação.",
        ["validar fontes", "apoiar execução governada", "inspecionar observabilidade"],
    ),
    McpAgent(
        "sentinel-bi-agent",
        "Agente focado em BI, semântica oficial e consumo analítico.",
        ["explicar métricas", "descrever fatos e dimensões", "apoiar Power BI"],
    ),
    McpAgent(
        "sentinel-audit-agent",
        "Agente focado em auditoria de inconsistências e correções persistidas.",
        ["comparar Gold e outputs", "localizar desvios", "rastrear exceções"],
    ),
    McpAgent(
        "sentinel-ai-readiness-agent",
        "Agente focado em preparação textual e AI-ready layer.",
        ["identificar ruído textual", "descrever campos úteis", "apoiar casos futuros de IA"],
    ),
]


def build_manifest() -> dict:
    return {
        "product": "Projeto Sentinel",
        "stack": ["Python", "SQLite", "Excel", "Power BI"],
        "contexts": [asdict(item) for item in CONTEXTS],
        "tools": [asdict(item) for item in TOOLS],
        "agents": [asdict(item) for item in AGENTS],
    }
