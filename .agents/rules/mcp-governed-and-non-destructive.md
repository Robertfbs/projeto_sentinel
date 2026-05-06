---
title: MCP Governado e Não Destrutivo
impact: HIGH
impactDescription: garante automação assistida sem perda de controle humano
tags: sentinel, mcp, governance, ai
---

## Regra

MCP, skills e agentes do Sentinel devem operar como camada de leitura, validação, apoio analítico e orquestração governada, nunca como substitutos autônomos do pipeline operacional.

## Motivação

O objetivo da camada de IA é aumentar capacidade de análise e automação assistida sem comprometer previsibilidade, rastreabilidade e segurança operacional.

## Permitido

- leitura de contexto do projeto;
- validação de contratos de dados;
- apoio à geração de documentação;
- explicação de métricas e reconciliação analítica.

## Não permitido

- alterar banco, outputs ou regras sem permissão humana explícita;
- criar semântica nova sem validação;
- executar ação destrutiva fora do fluxo governado.

## Validação

Toda automação deve deixar claro:
- o que leu;
- o que pretende fazer;
- quais regras se aplicam;
- se há necessidade de autorização humana.
