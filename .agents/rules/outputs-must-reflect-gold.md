---
title: Outputs Devem Refletir a Gold Oficial
impact: HIGH
impactDescription: protege a confiabilidade analítica do produto
tags: sentinel, outputs, reconciliation
---

## Regra

Nenhum relatório executivo, base higienizada ou export analítico pode divergir do estado vigente da Gold oficial do Sentinel.

## Motivação

O produto perde credibilidade quando banco, Excel e BI mostram números ou atributos diferentes para o mesmo ticket.

## Permitido

- gerar saídas derivadas da Gold;
- adicionar abas informativas de exceção;
- reconciliar outputs após execução.

## Não permitido

- usar base intermediária como verdade final;
- manter output desatualizado após atualização da Gold;
- aceitar divergência sem investigação.

## Validação

Em qualquer mudança relevante:
- comparar amostras entre Gold e outputs;
- validar tickets críticos corrigidos;
- garantir que filtros executivos sejam respeitados.
