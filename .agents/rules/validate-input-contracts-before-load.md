---
title: Validar Contratos de Dados Antes da Carga
impact: HIGH
impactDescription: reduz quebra silenciosa por mudança de layout na origem
tags: sentinel, data-contracts, ingestion
---

## Regra

Nenhuma fonte operacional pode ser considerada apta para carga sem validação prévia de contrato de dados e de schema mínimo esperado.

## Motivação

Os arquivos do Zendesk e do GSS são manuais e sujeitos a mudança de layout. Sem validação explícita, o ETL pode falhar tardiamente ou produzir dados incorretos.

## Permitido

- validação de presença de colunas obrigatórias;
- validação de campos críticos para regras do negócio;
- registro detalhado de falhas de contrato.

## Não permitido

- seguir processamento quando faltar coluna crítica;
- inferir layout desconhecido sem evidência;
- mascarar quebra estrutural com fallback silencioso.

## Validação

Antes da carga, verificar:
- colunas mínimas por fonte;
- mapeamento de aliases conhecidos;
- critérios de rejeição documentados.
