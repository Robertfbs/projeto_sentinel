# Documentacao do Projeto Sentinel

Documentacao tecnica e analitica do pipeline de dados Sentinel — mini data warehouse operacional para consolidacao, tratamento, enriquecimento e persistencia analitica de tickets Zendesk.

---

## Mapa de Documentos

| Documento | Descricao | Audiencia |
|---|---|---|
| [01 - Visao Geral](01-visao-geral.md) | Objetivo, escopo, stack tecnico e estrutura do projeto | AMBOS |
| [02 - Arquitetura e Pipeline](02-arquitetura-pipeline.md) | Modelo Bronze-Silver-Gold, fluxo ETL passo a passo, scripts | DEV |
| [03 - Fontes de Dados](03-fontes-de-dados.md) | Descricao das 4 fontes de entrada e descoberta dinamica | AMBOS |
| [04 - Regras de Negocio](04-regras-de-negocio.md) | Vinculacao, arquivamento, enriquecimento, derivacoes | AMBOS |
| [05 - Esquema do Banco de Dados](05-esquema-banco-de-dados.md) | Schema completo campo a campo das 10 tabelas Gold | AMBOS |
| [06 - Linhagem de Dados](06-linhagem-de-dados.md) | Rastreabilidade campo a campo: origem, transformacao, destino | DEV |
| [07 - Guia Operacional](07-guia-operacional.md) | Execucao, reprocessamento, monitoramento, troubleshooting | DEV |
| [08 - Guia de Consumo BI](08-guia-consumo-bi.md) | Conexao Power BI, tabelas por caso de uso, filtros, armadilhas | ANALISTA |
| [09 - Glossario](09-glossario.md) | Termos de negocio, termos tecnicos e siglas | AMBOS |
| [10 - Proposta DDD](10-proposta-ddd.md) | Analise e proposta de refatoracao com Domain-Driven Design | DEV |
| [MER Completo](diagramas/mer-completo.md) | Diagrama entidade-relacionamento anotado em MermaidJS | AMBOS |

---

## Como Navegar

**Se voce e desenvolvedor ou engenheiro de dados:**
1. Comece pela [Visao Geral](01-visao-geral.md) para contexto
2. Mergulhe na [Arquitetura e Pipeline](02-arquitetura-pipeline.md) para entender o fluxo ETL
3. Consulte as [Regras de Negocio](04-regras-de-negocio.md) para decisoes de implementacao
4. Use o [Guia Operacional](07-guia-operacional.md) para execucao e troubleshooting

**Se voce e analista de dados ou consome via Power BI:**
1. Comece pela [Visao Geral](01-visao-geral.md) para contexto
2. Va direto ao [Guia de Consumo BI](08-guia-consumo-bi.md) para orientacoes praticas
3. Consulte o [Esquema do Banco](05-esquema-banco-de-dados.md) para significado dos campos
4. Use as [Regras de Negocio](04-regras-de-negocio.md) para entender filtros e flags

---

## Convencoes

| Tag | Significado |
|---|---|
| **DEV** | Conteudo voltado para desenvolvedores e engenheiros de dados |
| **ANALISTA** | Conteudo voltado para analistas de dados e consumidores BI |
| **AMBOS** | Conteudo relevante para ambos os perfis |
