# Instalacao do ODBC SQLite para o Projeto Sentinel

## Objetivo

Permitir que o Power BI Desktop consuma o banco SQLite
`E:\Projeto_Sentinel\03_database\pre_contencioso.db` por ODBC.

## Driver recomendado

O driver de uso mais comum para esse cenario e o `SQLite ODBC Driver`
disponibilizado por Christian Werner:

- site: [https://www.ch-werner.de/](https://www.ch-werner.de/)

## Qual versao instalar

Instale a versao com a mesma arquitetura do seu Power BI Desktop.

Na pratica, quase sempre:

- Power BI Desktop 64-bit -> instalar driver ODBC SQLite 64-bit

Se houver duvida, priorize 64-bit.

## Passo a passo

1. Baixe o instalador do driver SQLite ODBC no site indicado.
2. Execute a instalacao com privilegios administrativos, se necessario.
3. Abra o administrador ODBC correto:
   - 64-bit: `C:\Windows\System32\odbcad32.exe`
4. Va em `System DSN` ou `User DSN`.
5. Clique em `Add`.
6. Selecione o driver `SQLite3 ODBC Driver`.
7. Configure o driver/DSN com:
   - driver: `SQLite3 ODBC Driver`
   - opcionalmente crie o DSN `SQLite_PreContencioso`
   - `Database Name`: `E:\Projeto_Sentinel\03_database\pre_contencioso.db`
8. Salve a configuracao.
9. Teste a conexao no proprio dialogo do driver, se o driver oferecer essa opcao.

## Como usar no Power BI Desktop

1. Abra o Power BI Desktop.
2. Va em `Get Data`.
3. Escolha `ODBC`.
4. Use um `Blank Query` e importe as consultas `.m` do kit, que usam a
   connection string ODBC parametrizada por caminho.
5. Se preferir operar por DSN, adapte facilmente o `ConnectionString`
   dentro das consultas M.

## Parametrizacao recomendada no Power BI

Crie estes parametros:

- `pDbPath` = `E:\Projeto_Sentinel\03_database\pre_contencioso.db`
- `pSqliteDriverName` = `SQLite3 ODBC Driver`

## Validacao rapida

Depois da instalacao, a validacao minima e:

- o DSN aparecer no administrador ODBC;
- o Power BI conseguir listar a fonte ODBC;
- a consulta `fTicketsSolicitacao` retornar linhas;
- a consulta `fAudiencias` retornar linhas.

## Problemas comuns

### O DSN nao aparece no Power BI

Causa provavel:

- incompatibilidade entre arquitetura do Power BI e do driver

Acao:

- reinstalar a versao correta, normalmente 64-bit

### Erro de permissao no arquivo `.db`

Causa provavel:

- arquivo aberto por outro processo ou permissao insuficiente no diretorio

Acao:

- validar leitura do arquivo em `E:\Projeto_Sentinel\03_database`

### Lentidao na importacao

Causas provaveis:

- leitura de tabelas sem filtro
- modelo importando colunas desnecessarias

Acao:

- usar as consultas SQL do kit, que ja aplicam filtro de negocio na origem
