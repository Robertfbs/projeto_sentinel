---
name: executa-etl-sentinel
description: Orienta a execução segura do ETL do Projeto Sentinel, incluindo checagens prévias, validação de fontes e reconciliação pós-execução. Use quando a solicitação envolver rodar o pipeline, reprocessar cargas ou verificar integridade operacional do ETL.
---

# Execução do ETL do Sentinel

## Procedures

**Step 1: Validar pré-condições**
1. Confirmar presença das fontes esperadas em `01_raw`.
2. Conferir se há risco de arquivo obrigatório ausente.
3. Conferir se a solicitação autoriza execução prática.

**Step 2: Validar contrato mínimo**
1. Garantir que as fontes críticas tenham colunas mínimas.
2. Sinalizar quebra de contrato antes da execução.

**Step 3: Executar**
1. Rodar o ETL principal.
2. Monitorar status de sucesso, falha e outputs esperados.
3. Não corrigir divergência com update direto no banco como primeira opção.

**Step 4: Validar pós-run**
1. Verificar `pre_contencioso.db`.
2. Verificar outputs executivos e base higienizada.
3. Validar amostra de tickets críticos quando aplicável.

## Core Principles

- Executar somente com autorização explícita.
- Validar antes e depois da carga.
- Banco oficial e outputs devem ficar coerentes.

## Quality Checklist

- [ ] Pré-condições validadas
- [ ] Contratos mínimos verificados
- [ ] ETL executado com autorização explícita
- [ ] Banco atualizado
- [ ] Outputs esperados gerados
- [ ] Reconciliação pós-run realizada

## Error Handling

- Se faltarem fontes críticas, interromper e reportar.
- Se houver quebra de contrato, não prosseguir silenciosamente.
- Se outputs divergirem da Gold, tratar como incidente de reconciliação.
