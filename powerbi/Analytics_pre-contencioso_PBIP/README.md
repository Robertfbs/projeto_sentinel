# Analytics_pre-contencioso - Starter PBIP

Este pacote organiza a futura conversao do relatorio `Analytics_pre-contencioso`
para o formato Power BI Project (`PBIP/PBIR`), mais aderente a versionamento,
code review e governanca corporativa.

## Escopo deste starter

Este diretorio nao contem um `.pbip` binario/gerado automaticamente. Em vez
disso, ele entrega a estrutura de trabalho recomendada para que o relatorio seja
criado no Power BI Desktop e salvo em formato projeto assim que:

- o driver ODBC SQLite estiver instalado;
- o Desktop abrir corretamente a conexao ao `pre_contencioso.db`.

## Fluxo recomendado

1. Configure o ODBC SQLite.
2. Monte o relatorio no Power BI Desktop usando o kit:
   - `..\\Analytics_pre-contencioso_kit`
3. Salve o relatorio inicialmente como `.pbix`.
4. No Power BI Desktop, habilite o modo projeto se necessario.
5. Salve como projeto Power BI no formato `PBIP`.
6. Use esta pasta como referencia de organizacao no Git.

## Estrutura recomendada para o projeto PBIP final

```text
Analytics_pre-contencioso.pbip
Analytics_pre-contencioso.Report/
Analytics_pre-contencioso.SemanticModel/
```

## Convencoes recomendadas

- Relatorio: `Analytics_pre-contencioso`
- Paginas:
  - `Visao Geral`
  - `Produtividade`
  - `Canais`
  - `Assuntos`
  - `Audiencias`
  - `Geo`
- Prefixo de medidas:
  - base: sem prefixo
  - suporte: `_`

## Git e governanca

- versionar o projeto PBIP, nao o `.pbix`;
- revisar mudancas em `report.json`, `pages`, `visuals` e semantic model;
- evitar mudancas manuais em massa fora do Desktop;
- documentar alteracoes de medidas, filtros e temas.

## Tema e UX executiva recomendados

- fundo claro, contraste alto e pouco ruído visual;
- 1 cor principal institucional + 1 cor de destaque para alerta;
- maximo de 6 a 8 visuais por pagina;
- KPIs grandes no topo;
- slicers padronizados:
  - periodo
  - canal
  - colaborador
  - municipio

## Conteudo de apoio

Use estes arquivos como fonte de implementacao:

- `..\\Analytics_pre-contencioso_kit\\README.md`
- `..\\Analytics_pre-contencioso_kit\\powerquery\\`
- `..\\Analytics_pre-contencioso_kit\\sql\\`
- `..\\Analytics_pre-contencioso_kit\\dax\\Analytics_pre-contencioso_measures.dax`
- `..\\Analytics_pre-contencioso_kit\\model\\Analytics_pre-contencioso_modelo.md`
