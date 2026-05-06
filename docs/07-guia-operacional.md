# Guia Operacional

**Audiencia**: DEV (Desenvolvedores e Engenheiros de Dados)

[Voltar ao indice](README.md) | [Anterior: Linhagem de Dados](06-linhagem-de-dados.md) | [Proximo: Guia de Consumo BI](08-guia-consumo-bi.md)

---

## Pre-requisitos

### Software

| Componente | Versao | Finalidade |
|---|---|---|
| Python | 3.10+ | Runtime do pipeline |
| Pandas | — | Processamento de dados tabulares |
| openpyxl | — | Leitura de arquivos Excel |
| xlsxwriter | — | Escrita formatada de relatorios Excel |
| SQLite | Embutido | Banco de dados Gold (nao requer instalacao separada) |

### Estrutura de diretorios necessaria

```text
Projeto_Sentinel/
|-- 01_raw/          ← Deve existir e conter os arquivos brutos
|-- 02_silver/       ← Criado automaticamente se necessario
|-- 03_database/     ← Criado automaticamente se necessario
|-- outputs/         ← Criado automaticamente se necessario
`-- scripts/         ← Scripts Python do pipeline
```

---

## Execucao do ETL Principal

### Comando

```bash
cd E:\Projeto_Sentinel
python scripts\main_etl.py
```

### O que acontece

| Fase | Acao |
|---|---|
| 1. Schema | Cria ou atualiza o banco SQLite (`03_database/pre_contencioso.db`) |
| 2. Fontes | Processa todos os arquivos disponiveis em `01_raw/` |
| 3. Silver | Gera 5 datasets tratados em `02_silver/` |
| 4. Gold | Persiste registros via UPSERT nas tabelas SQLite |

### Tempo de execucao

Depende do volume de dados em `01_raw/`. O pipeline e sequencial e processa todas as fontes encontradas.

---

## Execucao do Relatorio Executivo

### Modo manual (interativo)

```bash
python scripts\analytics\relatorio_executivo.py
```

### Modo automatico

```bash
python scripts\analytics\relatorio_executivo.py --auto
```

### Caracteristicas

- Gera relatorio Excel em `outputs/`
- Aplica regra estrita de **D-1** (dados ate o dia anterior)
- Exibe resumo executivo no terminal
- Contem abas analiticas + aba `DATA` para auditoria

---

## Preparacao dos Arquivos de Entrada

### Onde colocar

Todos os arquivos brutos devem ser colocados no diretorio `01_raw/`.

### Convencao de nomes

Os arquivos devem comecar com o **prefixo obrigatorio** correspondente:

| Fonte | Prefixo obrigatorio | Exemplos validos |
|---|---|---|
| Zendesk N2 | `ANALYTICS_BASE_TICKETS_GERAL` | `ANALYTICS_BASE_TICKETS_GERAL_2026.xlsx`, `ANALYTICS_BASE_TICKETS_GERAL_v2.xlsx` |
| Zendesk N1 | `ANALYTICS_BASE_TICKETS_N1` | `ANALYTICS_BASE_TICKETS_N1_marco.xlsx` |
| Audiencias | `PRE_CONTENCIOSO_AUDIENCIAS` | `PRE_CONTENCIOSO_AUDIENCIAS_2026-03.xlsx` |
| GSS | `Base_GSS` | `Base_GSS_completa.xlsx`, `Base_GSS_filtrada.xlsx` |

### Regras

- **Multiplos arquivos** por prefixo sao aceitos e concatenados automaticamente
- Variacoes de **sufixo, data e versao** no nome sao toleradas
- Extensao suportada: `.xlsx`
- Metadados `arquivo_origem`, `arquivo_mtime` e `fonte_raw` sao registrados automaticamente

---

## Reprocessamento

O ETL e **idempotente** gracas ao mecanismo de UPSERT. Reprocessar e seguro.

### Cenarios comuns

| Cenario | Acao | Resultado |
|---|---|---|
| **Correcao de dados** | Substituir arquivo em `01_raw/` e reexecutar ETL | Registros existentes sao atualizados pela chave primaria |
| **Adicao de novos dados** | Adicionar novo arquivo em `01_raw/` e reexecutar | Novos registros sao inseridos, existentes sao atualizados |
| **Reprocessamento completo** | Manter todos os arquivos em `01_raw/` e reexecutar | Todos os registros sao reprocessados sem duplicidade |
| **Mudanca de regra** | Alterar script e reexecutar com mesmos dados | Campos derivados sao recalculados |

### Garantias

- Nenhuma linha e duplicada por chave de negocio
- Campos ausentes no DataFrame preservam valores anteriores no banco
- Arquivos Silver sao sobrescritos a cada execucao

---

## Monitoramento e Validacao Pos-Execucao

### Verificacoes recomendadas

| Verificacao | Como | Esperado |
|---|---|---|
| Contagem de tickets | `SELECT COUNT(DISTINCT ticket_id) FROM tickets` | Compativel com volume de `ticket_id` distintos no arquivo bruto |
| Arquivos Silver | Verificar presenca de 5 arquivos em `02_silver/` | Todos presentes e com data de modificacao recente |
| Banco atualizado | Verificar `mtime` de `pre_contencioso.db` | Data/hora recentes |
| Warnings no terminal | Observar saida do ETL | Warnings de `data_reagendamento` sao esperados e nao-bloqueantes |

### Validacao cruzada Bronze vs Gold

**Nao comparar** volume bruto de linhas do arquivo com contagem no banco. O arquivo pode ter linhas duplicadas por assunto.

Comparacao correta:

```sql
-- Contagem de tickets distintos no Gold
SELECT COUNT(DISTINCT ticket_id) FROM tickets;

-- Deve ser compativel com ticket_id distintos no arquivo Bronze
```

### Validacao de assuntos

```sql
-- Total de assuntos (pode ser > total de tickets)
SELECT COUNT(*) FROM ticket_assunto;

-- Tickets com multiplos assuntos
SELECT COUNT(*) FROM tickets WHERE flag_multiplos_assuntos = 1;
```

---

## Troubleshooting

### Arquivo nao encontrado

**Sintoma**: Fonte nao e processada, sem erro explicito.

**Causa provavel**: Arquivo em `01_raw/` nao comeca com o prefixo correto.

**Solucao**: Verificar nome do arquivo contra os prefixos obrigatorios:
- `ANALYTICS_BASE_TICKETS_GERAL`
- `ANALYTICS_BASE_TICKETS_N1`
- `PRE_CONTENCIOSO_AUDIENCIAS`
- `Base_GSS`

---

### UserWarning de parsing em `data_reagendamento`

**Sintoma**: `UserWarning: Could not infer format...` durante processamento de audiencias.

**Causa**: Heterogeneidade de formato de data na coluna `data_reagendamento` do arquivo de audiencias.

**Impacto**: **Nenhum**. O warning e nao-bloqueante e o pipeline continua normalmente.

**Acao**: Nenhuma acao necessaria. Se frequente, considerar padronizar o formato na fonte.

---

### Duplicidade aparente de tickets

**Sintoma**: Contagem de linhas no arquivo bruto e maior que `ticket_id` distintos no banco.

**Causa**: Tickets com multiplos assuntos geram uma linha por assunto no Zendesk.

**Nao e erro**. O ETL consolida em 1 linha por `ticket_id` na tabela `tickets` e preserva todos os assuntos em `ticket_assunto`.

---

### Ruido em campos textuais do GSS

**Sintoma**: Valores inesperados em campos como `telefone` ou `nome_requerente_gss`.

**Causa**: A base GSS pode conter ruido em campos textuais.

**Impacto**: Pode afetar visualizacoes finais se esses campos forem usados diretamente.

**Acao**: Aplicar saneamento adicional se esses campos forem consumidos em dashboards.

---

### Arquivos legados em `02_silver/`

**Sintoma**: Arquivos com nomes antigos desaparecem de `02_silver/`.

**Causa**: O ETL remove automaticamente arquivos de versoes anteriores:
- `ANALYTICS_BASE_TICKETS_GERAL_SOLICITACAO_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_GERAL_NOTIFICACAO_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_processed.xlsx`
- `ANALYTICS_BASE_TICKETS_NOTIFICACAO_processed.xlsx`
- `Base_GSS_processed.xlsx`

**Nao e erro**. Esses arquivos foram substituidos pelo formato atual.

---

## Evolucoes Recomendadas

| Evolucao | Descricao | Prioridade |
|---|---|---|
| Views Gold para Power BI | Criar views SQL otimizadas para consumo direto em BI | Alta |
| Padronizacao de data de referencia | Padronizar `data_referencia` por dominio de negocio | Media |
| Saneamento textual do GSS | Limpar ruido em campos como telefone e nome | Media |
| Auditoria de vinculos ambiguos | Versao operacional para reconciliacao de vinculos AMBIGUO | Media |
| Versionamento de cargas | Estrategia formal de versionamento por lote de carga | Baixa |
| Ordenacao por data no nome | Para cenarios com muitos fragmentos N1, ordenar por data embutida no nome (nao por `mtime`) | Baixa |

---

[Voltar ao indice](README.md) | [Anterior: Linhagem de Dados](06-linhagem-de-dados.md) | [Proximo: Guia de Consumo BI](08-guia-consumo-bi.md)
