# Power BI

Esta pasta concentra os artefatos de BI do Projeto Sentinel para o relatório
`Analytics_pre-contencioso`.

Estrutura:

- `Analytics_pre-contencioso_kit`
  Kit funcional para abrir no Power BI Desktop, criar o modelo e salvar como
  `.pbit` após a configuração do ODBC SQLite.
- `Analytics_pre-contencioso_PBIP`
  Starter kit para organização versionável em modo projeto (`PBIP/PBIR`),
  alinhado a um fluxo corporativo de governança e controle de mudanças.

Arquivos principais do kit:

- `README.md`
  Guia operacional de montagem do relatório no Power BI Desktop.
- `powerquery/*.m`
  Consultas M para parâmetros, fatos e dimensões.
- `sql/*.sql`
  SQL nativo usado pelas consultas ODBC.
- `dax/Analytics_pre-contencioso_measures.dax`
  Medidas DAX prontas para colagem no modelo.
- `model/Analytics_pre-contencioso_modelo.md`
  Desenho lógico do modelo estrela e regras de relacionamento.

Observações:

- O Power BI Desktop não possui conector nativo para SQLite; a estratégia
  recomendada neste projeto é uso de ODBC.
- Este pacote foi construído a partir do schema real do banco:
  `E:\Projeto_Sentinel\03_database\pre_contencioso.db`.
- O kit evita depender de tabelas auxiliares de auditoria nas métricas
  executivas, respeitando as regras vigentes do projeto.
