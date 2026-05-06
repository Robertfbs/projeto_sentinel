# PRD — Projeto Sentinel

## Visão Geral

O Projeto Sentinel é um Data Product analítico voltado para CX e pré-contencioso, responsável por transformar arquivos operacionais extraídos manualmente do Zendesk e do GSS/SCAE em uma base confiável, rastreável e reutilizável para diretoria, gerência, BI e engenharia de dados.

O produto resolve um problema crítico de confiabilidade analítica: a origem é manual, os arquivos Excel têm baixa padronização, há inconsistências recorrentes de classificação, múltiplos assuntos por ticket, necessidade de enriquecimento externo e risco de divergência entre banco, relatórios e análises ad hoc. O Sentinel organiza esse fluxo em Bronze > Silver > Gold, preserva regras de negócio já validadas e entrega banco SQLite, relatórios executivos em Excel e base higienizada para consumo analítico.

Como Data Product, o Sentinel deve ser entendido como ativo corporativo de dados, com:
- ownership funcional em negócio pré-contencioso / CX;
- ownership técnico em engenharia de dados;
- guarda semântica em Analytics / BI;
- consumo principal por diretoria, gerência, BI, operação auditiva e futuras automações assistidas.

O valor do produto está em:
- consolidar múltiplas fontes em uma base única e auditável;
- separar dado executivo de dado mantido apenas para auditoria;
- reduzir retrabalho manual em relatórios críticos;
- sustentar métricas confiáveis de entrada, resolução, audiência, produtividade e volumetria;
- preparar uma base limpa e governada para BI enterprise, automação e uso futuro em IA.

## Objetivos

Objetivos principais:
- consolidar dados de Zendesk e GSS em uma base analítica única, estável e rastreável;
- garantir que relatórios executivos reflitam apenas dados válidos para consumo gerencial;
- preservar registros inconsistentes apenas para auditoria, sem contaminar métricas oficiais;
- disponibilizar saídas padronizadas para Power BI, Excel e análises ad hoc;
- reduzir dependência de tratamento manual em relatórios de produtividade, volumetria, audiências e acompanhamento executivo;
- manter o pipeline compatível com múltiplos arquivos por prefixo em `01_raw`, sem duplicação indevida por `ticket_id`;
- preservar regras de negócio já consolidadas, com evolução apenas aditiva e controlada;
- preparar o produto para governança, observabilidade, BI enterprise e camada AI-ready.

Definição de sucesso:
- `pre_contencioso.db` permanece consistente após cada execução;
- relatórios executivos não incluem `ANEXO` ou `Informativo::Anexo`;
- base higienizada e relatórios executivos refletem o estado vigente do banco;
- o pipeline continua operacional com os layouts conhecidos da origem;
- dashboards e relatórios passam a consumir uma semântica oficial e consistente.

Métricas principais do produto:
- quantidade de tickets válidos carregados por execução;
- quantidade de registros arquivados logicamente;
- quantidade de tickets vinculados entre `SOLICITAÇÃO` e `NOTIFICAÇÃO`;
- quantidade de tickets enriquecidos por GSS;
- quantidade de tickets com múltiplos assuntos preservados em `ticket_assunto`;
- taxa de aderência entre banco Gold e saídas derivadas;
- cobertura de colunas críticas por fonte;
- quantidade de execuções bem-sucedidas do ETL e de relatórios gerados.

Indicadores de qualidade e alerta:
- % de tickets com matrícula válida;
- % de tickets com enriquecimento GSS;
- % de tickets com classificação consistente;
- taxa de arquivamento lógico;
- alerta quando houver quebra de contrato, queda abrupta de cobertura ou divergência entre banco e saídas.

SLAs operacionais atuais:
- disponibilidade por ciclo de execução, não em tempo real;
- atualização diária para relatórios executivos, condicionada à chegada dos arquivos;
- relatórios gerados no mesmo ciclo da execução bem-sucedida.

## Histórias de Usuário

Histórias principais:
- Como analista de dados, eu quero consolidar arquivos brutos do Zendesk e GSS em uma base única para produzir análises confiáveis sem retrabalho manual extensivo.
- Como gerente de pré-contencioso, eu quero consultar relatórios diários e semanais limpos para acompanhar produtividade, audiências e volumetria com confiança.
- Como diretoria, eu quero receber relatórios executivos sem ruído operacional para acompanhar indicadores relevantes sem interpretar exceções técnicas.
- Como engenheiro de dados, eu quero preservar regras de negócio e auditoria em uma camada controlada para evoluir o pipeline sem quebrar o histórico validado.
- Como operação, eu quero que tickets inconsistentes permaneçam rastreáveis, mas fora das métricas oficiais, para investigar desvios sem contaminar indicadores.
- Como usuário de BI, eu quero uma base higienizada e um banco relacional consistente para criar dashboards sem depender da Silver operacional.
- Como Data Analyst, eu quero uma camada semântica estável para construir relatórios em Power BI com métricas oficiais e filtros consistentes.
- Como stakeholder de negócio, eu quero definições oficiais de métricas para que todas as áreas consultem os mesmos números com a mesma interpretação.
- Como usuário futuro de IA, eu quero dados textuais padronizados e uma base limpa para habilitar busca semântica, classificação automática e apoio operacional.

Personas primárias:
- Diretoria
- Gerência de pré-contencioso / CX
- Analytics / BI
- Engenharia de Dados

Personas secundárias:
- Operação N2
- Auditoria / validação manual
- Data Analyst focado em Power BI
- Stakeholders de negócio

Casos extremos cobertos:
- múltiplos arquivos por prefixo na mesma carga;
- tickets duplicados por múltiplas tabulações de assunto;
- tickets com classificação incorreta de canal ou grupo;
- registros `ANEXO` ou `Informativo::Anexo`;
- tickets que devem permanecer no banco, mas fora das métricas;
- movimentações fora do padrão operacional em fins de semana e feriados;
- divergência entre relatório e banco;
- correções manuais válidas que precisam virar regra persistida;
- mudança de layout de origem sem aviso.

## Funcionalidades Principais

### 1. Ingestão dinâmica de arquivos operacionais

O sistema localiza automaticamente arquivos em `01_raw` por prefixo conhecido, aceita múltiplos arquivos por fonte e mantém separação lógica entre `GERAL`, `N1`, `AUDIÊNCIAS` e `GSS`.

Requisitos funcionais:
1. O sistema deve localizar automaticamente arquivos por prefixo conhecido em `01_raw`.
2. O sistema deve suportar múltiplos arquivos por fonte na mesma execução.
3. O sistema deve preservar a separação lógica entre fontes e ciclos de carga.

### 2. Tratamento e persistência de tickets do Zendesk

O sistema transforma os relatórios do Zendesk em entidades persistidas em SQLite, preservando integridade por `ticket_id`.

Requisitos funcionais:
1. O sistema deve persistir tickets de `SOLICITAÇÃO`, `NOTIFICAÇÃO` e `N1` em estruturas adequadas.
2. O sistema deve evitar duplicidade de `ticket_id` na tabela principal.
3. O sistema deve manter histórico e rastreabilidade compatíveis com a operação.
4. O sistema deve continuar apto para consumo em SQLite e Power BI.

### 3. Segregação entre dados válidos e dados de auditoria

O sistema separa dados válidos para métrica de dados mantidos apenas para rastreio e auditoria.

Requisitos funcionais:
1. O sistema não deve considerar `tipo_manifestacao = ANEXO` nas métricas executivas.
2. O sistema não deve considerar `classificacao_notificacoes = Informativo::Anexo` nas métricas executivas.
3. O sistema deve manter esses registros no banco para auditoria futura.
4. O sistema deve permitir correções manuais controladas e persistência de regras recorrentes no ETL.

### 4. Preservação de múltiplos assuntos por ticket

O sistema evita duplicação de tickets na Gold, mas preserva o tracking completo dos assuntos tratados.

Requisitos funcionais:
1. O sistema deve manter uma linha por `ticket_id` na entidade principal.
2. O sistema deve armazenar múltiplos assuntos em tabela filha apropriada.
3. O sistema deve permitir identificar tickets com múltiplos assuntos.

### 5. Enriquecimento com dados do GSS

O sistema complementa tickets com dados operacionais e cadastrais do GSS por matrícula, sem sobrescrever dados válidos da origem Zendesk.

Requisitos funcionais:
1. O sistema deve usar `matricula` como chave principal de enriquecimento.
2. O sistema deve complementar apenas campos ausentes.
3. O sistema não deve sobrescrever valores válidos já presentes no Zendesk.
4. O sistema deve manter rastreabilidade da origem do número de O.S. quando aplicável.

### 6. Geração de saídas executivas e analíticas

O sistema gera relatórios e bases derivadas em `outputs`, voltados para diretoria, gestão e BI.

Requisitos funcionais:
1. O sistema deve gerar relatório diário executivo.
2. O sistema deve gerar relatório semanal de produtividade.
3. O sistema deve gerar a base higienizada para consumo analítico.
4. As saídas devem refletir o estado atual do banco no momento da execução.
5. As saídas executivas não devem incluir dados arquivados logicamente.

### 7. Contratos de dados e proteção operacional

O produto deve formalizar contratos mínimos por fonte para reduzir fragilidade por mudança de layout ou quebra silenciosa do Excel de origem.

Requisitos funcionais:
1. O produto deve definir colunas mínimas obrigatórias por fonte.
2. O produto deve identificar quebra de contrato antes do consumo analítico.
3. O produto deve registrar a quebra de contrato de forma rastreável.
4. O produto deve falhar de forma explícita quando a quebra impedir regras centrais do negócio.

### 8. Camada semântica para BI enterprise

O produto deve disponibilizar um modelo semântico estável e oficial para consumo em Power BI.

Requisitos funcionais:
1. O produto deve definir o grão analítico oficial do ticket.
2. O produto deve separar fatos e dimensões oficiais para dashboards.
3. O produto deve manter coerência entre banco, base higienizada e dashboards.
4. O produto deve explicitar o que entra e o que não entra nas métricas executivas.

### 9. Observabilidade e governança do produto

O produto deve se tornar monitorável e governado sem alterar o comportamento atual.

Requisitos funcionais:
1. Toda execução do ETL deve ser rastreável.
2. O produto deve registrar volume processado, status da execução e status da geração dos relatórios.
3. O produto deve ter fluxo claro de aprovação para novas regras.
4. Correções recorrentes devem virar regra persistida no ETL.

### 10. Preparação para IA e automação

O produto deve manter dados limpos, padronizados e governados para suportar futuros usos em IA.

Requisitos funcionais:
1. O produto deve preservar campos textuais úteis para classificação, busca e apoio operacional.
2. O produto deve evitar ruído executivo nas saídas orientadas a uso semântico.
3. O produto deve permitir uma futura camada AI-ready sem quebrar a operação atual.

## Experiência do Usuário

Personas e necessidades:
- Diretoria precisa de relatórios objetivos, limpos e confiáveis.
- Gerência precisa acompanhar produtividade, audiências e entradas com baixa fricção operacional.
- BI / Analytics precisa de base consistente, rastreável e semanticamente padronizada.
- Engenharia de Dados precisa de pipeline evolutivo, auditável e de baixo acoplamento.
- Operação precisa conseguir validar exceções sem contaminar métricas.

Fluxos principais:
- operador salva arquivos brutos em `01_raw`;
- ETL é executado;
- Gold é atualizada em `pre_contencioso.db`;
- saídas tratadas são geradas em `02_silver` e `outputs`;
- BI enterprise consome a Gold e/ou a base higienizada;
- auditoria consulta registros segregados;
- futuras automações consumirão a camada AI-ready.

Considerações de UI/UX:
- relatórios Excel devem ser limpos e focados em leitura executiva;
- abas auxiliares só devem existir quando agregarem rastreabilidade sem poluir a leitura principal;
- nomenclatura de colunas e arquivos deve ser previsível;
- bases para BI devem evitar colunas técnicas desnecessárias ao usuário final;
- métricas devem ter semântica única e documentada.

Requisitos de acessibilidade:
- nomenclatura clara em colunas e abas;
- baixo ruído visual;
- formatos simples de consumo: `.xlsx`, SQLite, Power BI;
- distinção clara entre dado operacional, auditável e executivo.

## Restrições Técnicas de Alto Nível

- O projeto opera sobre arquivos Excel extraídos manualmente do Zendesk e do GSS.
- O banco oficial do projeto é SQLite (`pre_contencioso.db`).
- O stack atual é Python, pandas, sqlite3, openpyxl, xlsxwriter, Excel e Power BI.
- A arquitetura Bronze > Silver > Gold deve ser preservada.
- Regras de negócio já validadas não devem ser removidas ou simplificadas.
- O sistema deve permanecer compatível com o consumo atual em Power BI.
- O projeto trata dados potencialmente sensíveis, como matrícula, CPF, telefone, endereço e e-mail.
- O ambiente de origem possui baixa padronização operacional e pode sobrescrever correções se estas não forem persistidas no ETL.
- O projeto não possui campo estruturado universal de prazo/vencimento por ticket.
- O repositório hoje contém estruturas auxiliares de skills, MCP e artefatos de outros stacks; esses artefatos não alteram a arquitetura canônica do Sentinel e não devem substituir o stack principal do produto.

Detalhes de implementação serão abordados na TechSpec.

## Fora de Escopo

- integração online ou em tempo real com APIs do Zendesk;
- migração do banco SQLite para outro mecanismo no escopo atual;
- automação nativa de publicação no Power BI Service;
- substituição do processo atual de extração manual na origem;
- extração automática de prazo a partir de PDFs ou anexos;
- implementação de uma régua oficial e universal de SLA jurídico para todos os canais;
- correção automática irrestrita de classificação sem validação governada;
- eliminação da camada Silver voltada a auditoria;
- entrega de funcionalidades de IA em produção neste estágio do produto;
- substituição do pipeline atual por agentes, skills ou MCPs sem manter compatibilidade total com a operação existente.
