---
name: valida-contrato-dados-sentinel
description: Valida contratos de dados das fontes do Projeto Sentinel antes de carga, evolução de ETL ou geração de outputs, com foco em colunas obrigatórias, regras mínimas de preenchimento e critérios de rejeição. Use quando a solicitação envolver schema, layouts de Excel, fontes operacionais ou risco de quebra na origem.
---

# Validação de Contrato de Dados do Sentinel

## Procedures

**Step 1: Identificar a fonte**
1. Confirmar se a fonte é Zendesk GERAL, N1, Audiências ou GSS.
2. Ler o contrato correspondente.

**Step 2: Validar o contrato**
1. Conferir colunas obrigatórias.
2. Conferir disponibilidade de dados críticos.
3. Validar se o layout permite aplicar as regras de negócio centrais.

**Step 3: Classificar o resultado**
1. Aprovado
2. Alerta
3. Rejeitado

**Step 4: Reportar**
1. Registrar colunas faltantes.
2. Explicar o risco operacional.
3. Recomendar fail-fast quando a quebra for crítica.

## Core Principles

- Contrato de dados é proteção, não burocracia.
- Quebra crítica precisa ser explícita.
- Não inferir schema ausente.

## Quality Checklist

- [ ] Fonte identificada
- [ ] Contrato correto lido
- [ ] Colunas obrigatórias verificadas
- [ ] Critérios de rejeição aplicados
- [ ] Resultado reportado com clareza

## Error Handling

- Se a fonte não for reconhecida, interromper e pedir enquadramento correto.
- Se houver quebra crítica, não tratar como simples alerta.
