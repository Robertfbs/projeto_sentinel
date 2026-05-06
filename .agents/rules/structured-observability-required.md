---
title: Observabilidade Estruturada Obrigatória
impact: HIGH
impactDescription: melhora diagnóstico, auditoria e previsibilidade do ETL
tags: sentinel, observability, logging
---

## Regra

Toda evolução relevante do pipeline deve prever observabilidade mínima por execução e por etapa.

## Motivação

Sem histórico estruturado de execução, falhas e desvios de volume são difíceis de explicar e auditar.

## Obrigatório

- registro de execução em `etl_runs`;
- eventos estruturados em `etl_logs`;
- status final da execução;
- volume processado;
- tempo por etapa;
- erro detalhado quando houver falha.

## Não permitido

- depender apenas de logs soltos no terminal;
- concluir uma mudança de ETL sem estratégia de rastreabilidade;
- registrar falhas sem contexto suficiente para investigação.

## Validação

Cada execução deve ser respondível com:
- o que rodou;
- quando rodou;
- quanto processou;
- onde falhou;
- quais saídas foram geradas.
