---
name: cria-techspec-sentinel
description: Cria ou evolui TechSpecs do Projeto Sentinel usando o template oficial, o TechSpec vigente, o PRD atual e a arquitetura real do repositório. Use quando a solicitacao envolver arquitetura, governança técnica, ETL, Power BI, observabilidade ou AI-ready no contexto do Sentinel.
---

# Criação de TechSpec do Sentinel

## Procedures

**Step 1: Validar pré-requisitos**
1. Ler `templates/techspec-template.md`.
2. Ler `prd.md` e `techspec.md` vigentes.
3. Ler os componentes reais do projeto antes de propor arquitetura.

**Step 2: Mapear a arquitetura existente**
1. Identificar componentes canônicos do Sentinel.
2. Separar artefatos auxiliares ou de outro stack do núcleo do produto.
3. Preservar regras já validadas.

**Step 3: Especificar a evolução**
1. Focar em HOW, não em WHAT.
2. Documentar:
   - arquitetura;
   - modelos de dados;
   - contratos de dados;
   - observabilidade;
   - governança;
   - Power BI semântico;
   - camada AI-ready.
3. Propor apenas melhorias aditivas.

**Step 4: Validar conformidade**
1. Confirmar aderência a Python + SQLite + Excel + Power BI.
2. Confirmar que MCP, skills e rules não substituem o pipeline.
3. Confirmar que a TechSpec não altera comportamento atual.

## Core Principles

- TechSpec define HOW o produto evolui tecnicamente.
- Não usar stacks paralelos como referência autoritativa do Sentinel.
- Preferir evolução incremental e reversível.
- Toda mudança deve ser observável e testável.

## Quality Checklist

- [ ] Template oficial lido
- [ ] PRD atual lido
- [ ] TechSpec atual lido
- [ ] Arquitetura real do repositório analisada
- [ ] Contratos de dados e observabilidade contemplados
- [ ] Camada semântica Power BI contemplada
- [ ] Camada AI-ready contemplada

## Error Handling

- Se o PRD não existir, interromper e reportar.
- Se houver conflito entre artefatos, priorizar comportamento real validado do Sentinel.
- Se faltar evidência para um detalhe técnico, documentar como lacuna e não inventar.
