# Analytics_pre-contencioso - Kit Power BI Desktop

Este kit foi preparado para acelerar a construcao do relatorio
`Analytics_pre-contencioso` no Power BI Desktop com base no banco
`E:\Projeto_Sentinel\03_database\pre_contencioso.db`.

## Objetivo

Entregar uma base tecnica pronta para:

- conectar o Power BI ao SQLite via ODBC;
- carregar apenas os dados analiticos validos;
- montar um modelo em estrela limpo e escalavel;
- aplicar medidas DAX executivas;
- salvar o arquivo final como `.pbit`.

## Premissas de negocio aplicadas

As consultas do kit respeitam as regras hoje consideradas oficiais no
Projeto Sentinel:

- considerar apenas `SOLICITACAO`;
- excluir `tipo_manifestacao = 'ANEXO'`;
- excluir `classificacao_notificacoes = 'Informativo::ANEXO'`;
- excluir tickets com `flag_arquivado_relatorio = 1`;
- manter auditoria e excecoes operacionais fora das metricas executivas.

## Arquitetura do modelo

Fato principal:

- `fTicketsSolicitacao`

Fato complementar:

- `fAudiencias`

Dimensoes:

- `dCalendario`
- `dCanal`
- `dAssunto`
- `dColaborador`
- `dStatus`
- `dLocalizacao`

## Ordem recomendada de construcao no Power BI Desktop

1. Instale e configure o ODBC SQLite.
2. Abra um arquivo em branco no Power BI Desktop.
3. Crie os parametros:
   - `pDbPath`
   - `pSqliteDriverName`
4. Importe as consultas em `powerquery`.
5. Verifique se `fTicketsSolicitacao` e `fAudiencias` carregam corretamente.
6. Crie os relacionamentos conforme `model/Analytics_pre-contencioso_modelo.md`.
7. Cole as medidas do arquivo `dax/Analytics_pre-contencioso_measures.dax`.
8. Monte as paginas do relatorio conforme o layout sugerido no starter PBIP.
9. Salve o arquivo como `Analytics_pre-contencioso.pbix`.
10. Exporte uma copia como `Analytics_pre-contencioso.pbit`.

## Parametros

### pDbPath

Caminho fisico do banco SQLite.

Valor sugerido:

`E:\Projeto_Sentinel\03_database\pre_contencioso.db`

### pSqliteDriverName

Nome do driver ODBC SQLite instalado localmente.

Valor sugerido:

`SQLite3 ODBC Driver`

## Consultas disponiveis

### fxNormalizeHierarchy

Funcao M para remover prefixos hierarquicos como:

- `Canais de atrito::PROCON` -> `PROCON`
- `Servicos Financeiros::Cobranca indevida` -> `Cobranca indevida`

### fTicketsSolicitacao

Tabela fato principal com tickets de solicitacao ja filtrados e enriquecidos,
incluindo:

- datas operacionais;
- colaborador;
- canal;
- assunto;
- localizacao;
- dados de audiencia relacionados;
- protocolos institucionais;
- campos de GSS relevantes para analise.

### fAudiencias

Fato especifico de audiencias derivado dos tickets validos.

### dCalendario

Dimensao calendario padrao, pronta para relacoes com:

- `data_entrada`
- `data_criacao`
- `data_resolucao`
- `data_audiencia`

### dCanal / dAssunto / dColaborador / dStatus / dLocalizacao

Dimensoes derivadas do fato principal.

## Medidas DAX

As medidas foram organizadas por dominio:

- volume;
- produtividade;
- status;
- audiencias;
- geo;
- rankings.

Observacao importante:

Medidas de prazo/SLA juridico nao foram materializadas neste kit porque o
projeto ainda nao possui um campo oficial e confiavel de vencimento por ticket.
O kit inclui apenas metricas robustas com base no estado atual do DW.

## Boas praticas recomendadas

- Desabilitar Auto Date/Time no Power BI.
- Marcar `dCalendario` como Date Table.
- Preferir medidas a colunas calculadas.
- Ocultar chaves tecnicas e colunas de apoio no painel de campos.
- Manter nomes amigaveis nas tabelas e medidas.
- Documentar, no proprio arquivo PBIX/PBIT, a origem ODBC e o caminho do banco.

## Observacoes sobre performance

- O filtro de negocio ja e aplicado em SQL nativo, reduzindo volume trafegado.
- As dimensoes sao construidas a partir do fato validado, evitando duplicacao.
- O modelo foi pensado para importacao, nao DirectQuery.

## Resultado esperado

Ao final da montagem, voce tera um arquivo corporativo pronto para distribuicao:

- `Analytics_pre-contencioso.pbix`
- `Analytics_pre-contencioso.pbit`

## Referencias internas

- Modelo: `model/Analytics_pre-contencioso_modelo.md`
- DAX: `dax/Analytics_pre-contencioso_measures.dax`
- SQL: `sql/`
- Power Query: `powerquery/`
