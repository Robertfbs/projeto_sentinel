---
name: cria-prd-sentinel
description: Cria ou evolui PRDs do Projeto Sentinel usando o template oficial do projeto, o PRD vigente e o contexto real do produto de dados. Use quando a solicitacao envolver PRD, data product, requisitos, métricas, governança ou escopo funcional do Sentinel.
---

# Criação de PRD do Sentinel

## Procedures

**Step 1: Validar contexto**
1. Confirmar que a solicitação pertence ao Projeto Sentinel.
2. Ler o template em `templates/prd-template.md`.
3. Ler o PRD vigente em `prd.md` antes de propor evolução.

**Step 2: Levantar contexto obrigatório**
1. Ler `README.md`, `techspec.md` e documentos diretamente ligados ao escopo pedido.
2. Confirmar regras de negócio já existentes e não alterá-las.
3. Identificar público consumidor, métrica oficial e impacto executivo.

**Step 3: Estruturar o PRD**
1. Seguir fielmente a estrutura do template.
2. Descrever o produto como Data Product governado.
3. Diferenciar claramente:
   - dado operacional;
   - dado auditável;
   - dado executivo.
4. Incluir objetivos mensuráveis, personas, métricas e fora de escopo.

**Step 4: Validar aderência**
1. Confirmar que o documento não altera comportamento funcional do Sentinel.
2. Confirmar compatibilidade com Bronze > Silver > Gold.
3. Confirmar coerência com Power BI enterprise e preparação AI-ready.

## Core Principles

- PRD fala de WHAT e WHY, não de HOW.
- Não inventar SLAs ou números sem evidência.
- Não remover conteúdo já validado; apenas evoluir.
- Toda métrica oficial precisa ser semanticamente clara.

## Quality Checklist

- [ ] Template oficial lido
- [ ] PRD atual lido
- [ ] Regras de negócio preservadas
- [ ] Personas e consumidores identificados
- [ ] Métricas oficiais e critérios de sucesso definidos
- [ ] Fora de escopo explicitado

## Error Handling

- Se o template não existir, interromper e reportar.
- Se faltar contexto de negócio, usar apenas evidência já presente no projeto.
- Se houver conflito entre documentos, priorizar o comportamento validado do pipeline.
