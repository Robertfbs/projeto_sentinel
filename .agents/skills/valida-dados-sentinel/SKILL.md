---
name: valida-dados-sentinel
description: Executa análise estruturada de qualidade e consistência de dados do Projeto Sentinel, comparando Gold, outputs e regras críticas do negócio sem alterar registros. Use quando a solicitação envolver auditoria de base, validação de consistência, reconciliação ou qualidade de dados do Sentinel.
---

# Validação de Dados do Sentinel

## Procedures

**Step 1: Determinar escopo da validação**
1. Identificar a base ou relatório alvo.
2. Ler as regras críticas aplicáveis ao escopo.

**Step 2: Validar consistência**
1. Verificar filtros executivos obrigatórios.
2. Verificar presença de `ANEXO` e `Informativo::Anexo` em bases onde não deveriam existir.
3. Verificar aderência entre Gold e outputs derivados.

**Step 3: Verificar qualidade**
1. Validar cobertura de matrícula.
2. Validar cobertura de enriquecimento GSS.
3. Validar consistência de classificação.
4. Validar tickets conhecidos por override persistido.

**Step 4: Reportar**
1. Produzir resumo objetivo.
2. Separar achados críticos, alertas e dados conformes.
3. Não alterar dados sem autorização explícita.

## Core Principles

- Validar sem contaminar a base.
- Priorizar métricas oficiais e regras executivas.
- Diferenciar problema estrutural de exceção conhecida.

## Quality Checklist

- [ ] Escopo identificado
- [ ] Regras críticas lidas
- [ ] Reconciliação Gold x outputs executada
- [ ] Exceções conhecidas verificadas
- [ ] Relatório estruturado produzido

## Error Handling

- Se o output não existir, reportar ausência e não inferir.
- Se houver divergência, apontar a origem provável sem alterar registros.
