---
name: gera-relatorio-sentinel
description: Orienta a geração e auditoria dos relatórios oficiais do Projeto Sentinel, preservando filtros executivos, regras de dia útil e coerência com a Gold. Use quando a solicitação envolver relatórios executivos, base higienizada ou auditoria de saída analítica.
---

# Geração de Relatórios do Sentinel

## Procedures

**Step 1: Identificar relatório alvo**
1. Confirmar qual saída será gerada ou validada.
2. Ler a regra de negócio correspondente ao relatório.

**Step 2: Confirmar fonte oficial**
1. Validar que a Gold é a base de verdade.
2. Confirmar filtros executivos obrigatórios.

**Step 3: Gerar ou auditar**
1. Aplicar a regra temporal correta.
2. Validar exclusões executivas.
3. Separar aba informativa de exceções quando aplicável.

**Step 4: Reconciliação**
1. Conferir amostra de registros na Gold.
2. Confirmar aderência entre relatório e banco.

## Core Principles

- Relatório oficial sempre deriva da Gold.
- Aba informativa não pode contaminar o indicador principal.
- Datas e filtros devem seguir a regra do relatório, não conveniência operacional.

## Quality Checklist

- [ ] Relatório identificado
- [ ] Regra temporal confirmada
- [ ] Filtros executivos aplicados
- [ ] Exceções segregadas corretamente
- [ ] Reconciliação com a Gold realizada

## Error Handling

- Se o relatório divergir da Gold, reportar antes de concluir.
- Se a regra temporal estiver ambígua, usar a definição já validada no projeto.
