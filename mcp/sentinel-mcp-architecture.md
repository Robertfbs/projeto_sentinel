# Arquitetura MCP do Projeto Sentinel

## Objetivo

Preparar o Sentinel para automação inteligente, copilots internos e workflows assistidos por IA sem alterar o pipeline principal.

## Princípios

- Gold oficial em SQLite continua sendo a verdade do produto;
- skills operam como instruções especializadas;
- rules operam como camada de governança;
- agentes operam por domínio e sem autonomia destrutiva;
- toda ação prática continua exigindo autorização humana.

## Domínios de atuação

- ETL
- BI
- Auditoria
- AI-ready

## Fluxo lógico

1. MCP lê contexto do projeto.
2. MCP seleciona skill aderente.
3. Rules validam se a ação é permitida.
4. Agente especializado executa análise ou proposta.
5. Ação prática só ocorre com autorização humana.
