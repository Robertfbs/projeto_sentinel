---
title: Persistir Correções Recorrentes no ETL
impact: HIGH
impactDescription: garante permanência de correções aprovadas após reprocessamento
tags: sentinel, etl, overrides
---

## Regra

Toda correção operacional aprovada que se repita ou que tenha impacto executivo deve ser persistida no ETL, e não apenas aplicada na Gold.

## Motivação

O pipeline reprocessa dados a partir da origem. Sem persistência da regra, a correção legítima pode ser perdida.

## Permitido

- manter tabela ou bloco de overrides governados;
- registrar justificativa da persistência;
- validar a correção após rerun completo.

## Não permitido

- depender de memória operacional;
- deixar correções críticas apenas em planilha paralela;
- considerar concluída uma correção que não sobrevive a nova carga.

## Validação

Após a mudança:
- rerodar o ETL;
- reconciliar banco e outputs;
- confirmar aderência em ticket(s) de amostra.
