---
title: Respeitar o Limite de Stack do Sentinel
impact: HIGH
impactDescription: evita contaminação arquitetural por artefatos paralelos do repositório
tags: sentinel, architecture, stack-boundary
---

## Regra

Toda proposta para o núcleo do Projeto Sentinel deve respeitar o stack canônico: Python + SQLite + Excel + Power BI.

## Motivação

O repositório hoje contém estruturas auxiliares de outros stacks. Esses artefatos não podem redefinir a arquitetura oficial do produto de dados.

## Permitido

- usar Python para ETL, automação e utilitários;
- usar SQLite como banco oficial;
- usar Excel e Power BI como saídas e consumo.

## Não permitido

- tratar React, Vite, Bun, Hono, Claude API ou PostgreSQL como padrão arquitetural do Sentinel;
- substituir o pipeline principal por tecnologias paralelas sem decisão formal.

## Validação

Antes de propor implementação:
- conferir aderência ao stack oficial;
- justificar qualquer artefato auxiliar fora do núcleo do produto.
