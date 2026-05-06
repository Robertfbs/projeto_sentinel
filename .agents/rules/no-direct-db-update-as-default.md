---
title: Não Usar Update Direto no Banco Como Caminho Padrão
impact: HIGH
impactDescription: evita divergência entre base oficial, ETL e outputs
tags: sentinel, sqlite, governance
---

## Regra

Alteração direta no `pre_contencioso.db` não pode ser o mecanismo padrão de correção funcional do produto.

## Motivação

Correções feitas apenas no banco podem ser sobrescritas em nova carga e quebrar a aderência entre ETL, base higienizada e relatórios.

## Permitido

- correção manual pontual, excepcional e autorizada;
- correção manual com backup prévio;
- auditoria e validação pontual de registros críticos.

## Não permitido

- manter correção recorrente somente no banco;
- usar update manual para substituir regra do ETL;
- corrigir em produção sem rastreabilidade mínima.

## Validação

Quando a correção se repetir ou afetar métrica oficial, ela deve ser convertida em regra persistida no ETL.
