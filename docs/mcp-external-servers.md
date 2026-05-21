# MCP Servers Externos - Sentinel

Este documento descreve como usar MCP servers externos junto ao MCP customizado do Projeto Sentinel, sem Docker Desktop e sem expor dados locais sensiveis.

## Regra principal

Os dados do Sentinel devem ser acessados somente pelo nosso MCP customizado:

```text
mcp_server/server.py
```

Nao usar MCP generico de filesystem, SQLite, Excel ou database para:

- `01_raw/`
- `02_silver/`
- `03_database/`
- `outputs/`
- `backup_relatorios_anteriores/`
- qualquer `.db`, `.xlsx`, `.csv` ou backup operacional

Essa regra existe porque o Sentinel tem PII, regras de negocio, filtros executivos e governanca propria. Servidores genericos nao conhecem essas restricoes.

## Estado local verificado

Em 2026-05-15, na branch `codex-mcp-external-servers`:

- Sentinel MCP customizado: funcional em `.venv-mcp`.
- MCP CLI Python: instalado.
- Node: disponivel pelo runtime do Codex.
- Docker: nao encontrado no PATH e nao pode ser instalado por falta de acesso admin.
- `npm`/`npx`: nao encontrados no PATH.
- GitHub CLI `gh`: nao encontrado no PATH.

Conclusao: para GitHub, as opcoes viaveis sem Docker sao GitHub MCP remoto ou binario local oficial. Para Power BI/Microsoft, a estrategia segura e remota/corporativa, com aprovacao administrativa quando aplicavel.

## Arquitetura recomendada sem Docker

```text
Cliente MCP
  |-- sentinel
  |     |-- MCP customizado local Python/FastMCP
  |     |-- unica interface para Gold, outputs e contexto Sentinel
  |
  |-- github-remote
  |     |-- GitHub MCP remoto oficial via OAuth
  |     |-- preferido quando disponivel no cliente
  |
  |-- github-readonly-local-binary
  |     |-- GitHub MCP Server oficial baixado como .exe
  |     |-- PAT fine-grained em variavel de ambiente
  |     |-- read-only no primeiro ciclo
  |
  |-- powerbi-remote
  |     |-- Power BI MCP remoto oficial
  |     |-- depende de tenant setting e Build permission
  |
  |-- microsoft-graph-enterprise
        |-- Microsoft MCP Server for Enterprise
        |-- depende de Entra/admin consent e escopos MCP delegados
```

## 1. Sentinel MCP local

Validar:

```powershell
.\.venv-mcp\Scripts\python.exe -m unittest tests.unit.test_mcp_server
```

Abrir Inspector:

```powershell
.\.venv-mcp\Scripts\mcp.exe dev mcp_server\server.py
```

Config generica:

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "<PROJECT_ROOT>\\.venv-mcp\\Scripts\\python.exe",
      "args": [
        "<PROJECT_ROOT>\\mcp_server\\server.py"
      ],
      "env": {
        "SENTINEL_MCP_CONFIG": "<PROJECT_ROOT>\\mcp_server\\config\\sentinel_mcp.toml"
      }
    }
  }
}
```

## 2. GitHub MCP sem Docker

### Opcao A - GitHub MCP remoto oficial

Use quando o cliente oferecer instalacao do servidor remoto GitHub MCP, como VS Code/GitHub Copilot.

Verificacao local:

- o comando `code --version` respondeu com VS Code `1.120.0`, compativel com MCP remoto;
- `code --list-extensions` nao listou `github.copilot` neste ambiente, apenas `github.vscode-pull-request-github`;
- se a extensao GitHub Copilot nao estiver instalada/logada no seu VS Code real, instale/ative antes de autenticar o MCP remoto.

Vantagens:

- nao precisa Docker;
- nao precisa PAT local;
- usa OAuth;
- menor risco de segredo em maquina local.

Passos gerais:

1. Abrir VS Code neste workspace.
2. Conferir o arquivo local ignorado pelo Git:

```text
.vscode/mcp.json
```

3. Confirmar que o servidor `github-readonly-remote` esta configurado com:

```text
https://api.githubcopilot.com/mcp/readonly
```

4. Abrir Command Palette.
5. Executar `MCP: List Servers`.
6. Selecionar `github-readonly-remote`.
7. Iniciar/autenticar quando o VS Code solicitar OAuth GitHub.
8. Testar leitura do repositorio `Robertfbs/projeto_sentinel`.

Se aparecer a janela `Dynamic Client Registration not supported`, cancele o fluxo OAuth e use a configuracao com PAT mascarado abaixo. Esse caminho evita registro dinamico de cliente e nao grava o token em arquivo versionado.

Se aparecer `Authorization header is badly formatted`, o servidor remoto recebeu um header `Authorization` fora do formato esperado. O valor deve ser exatamente:

```text
Bearer <SEU_FINE_GRAINED_PAT>
```

Use um unico espaco depois de `Bearer`, sem aspas, sem quebra de linha e sem colar `Bearer` duas vezes.

Config local sugerida para VS Code:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "github_mcp_authorization_header",
      "description": "Header completo: Bearer <GitHub fine-grained PAT read-only>",
      "password": true
    }
  ],
  "servers": {
    "github-readonly-remote": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "${input:github_mcp_authorization_header}",
        "X-MCP-Toolsets": "repos,issues,pull_requests,actions,users",
        "X-MCP-Readonly": "true"
      }
    }
  }
}
```

Segundo a documentacao oficial do GitHub MCP remoto, o header `X-MCP-Readonly` restringe as ferramentas a acesso de leitura. O token deve ser um fine-grained PAT limitado ao repositorio necessario.

Ao iniciar o servidor no VS Code, quando o prompt pedir `github_mcp_authorization_header`, cole o header completo:

```text
Bearer github_pat_xxxxxxxxxxxxxxxxx
```

Nao cole apenas `github_pat_xxx` nesse formato de configuracao.

Primeiros testes:

- listar repositorio;
- ler README;
- listar pull requests;
- listar issues;
- consultar status de workflows.

Nao habilitar escrita na primeira rodada.

### Opcao B - Binario local oficial

Use se o cliente nao suportar GitHub MCP remoto.

Pre-requisitos:

- baixar `github-mcp-server.exe` das releases oficiais do repositorio `github/github-mcp-server`;
- salvar em uma pasta local nao versionada, por exemplo:

```text
tools/mcp/github-mcp-server.exe
```

A pasta `tools/mcp/` esta no `.gitignore`.

Criar um Fine-grained Personal Access Token:

- Repository access: somente `Robertfbs/projeto_sentinel`.
- Permissoes iniciais: leitura para Contents, Metadata, Issues, Pull requests e Actions.
- Sem permissoes de escrita no primeiro teste.

Definir token apenas na sessao local:

```powershell
$env:GITHUB_PERSONAL_ACCESS_TOKEN = "<SEU_TOKEN_GITHUB_FINE_GRAINED_READONLY>"
```

Exemplo de configuracao:

```json
{
  "mcpServers": {
    "github-readonly-local-binary": {
      "command": "<PROJECT_ROOT>\\tools\\mcp\\github-mcp-server.exe",
      "args": [
        "stdio",
        "--read-only",
        "--toolsets",
        "default,actions"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    }
  }
}
```

Observacoes:

- `--read-only` deve ser mantido no primeiro ciclo.
- `default,actions` cobre contexto, repos, issues, pull requests, users e actions.
- Nunca salve o PAT em arquivo versionado.

## 3. Power BI MCP remoto

O endpoint oficial remoto e:

```text
https://api.fabric.microsoft.com/v1/mcp/powerbi
```

Pre-requisitos:

- Power BI admin precisa habilitar a tenant setting de MCP preview.
- Usuario precisa ter Build permission em ao menos um semantic model.
- VS Code/GitHub Copilot e autenticacao Microsoft.

Config manual VS Code:

```json
{
  "servers": {
    "powerbi-remote": {
      "type": "http",
      "url": "https://api.fabric.microsoft.com/v1/mcp/powerbi"
    }
  }
}
```

Para o Sentinel:

- use o Power BI MCP para modelos publicados no Power BI/Fabric;
- use o Sentinel MCP para Gold local, exports e regras validadas;
- nao exponha `03_database/pre_contencioso.db` por MCP generico.

## 4. Microsoft MCP Server for Enterprise

Este caminho e corporativo e depende de Microsoft Entra.

Pre-requisitos:

- conta com permissao de Application Administrator ou Cloud Application Administrator;
- app registration para o cliente MCP;
- delegated permissions no formato `MCP.<GraphScope>`;
- admin consent.

Escopos iniciais sugeridos, se a empresa aprovar:

- `MCP.User.Read.All` apenas para validacao de tenant;
- `MCP.Reports.Read.All` para relatorios;
- evitar escopos de escrita ate haver governanca formal.

No MCP Sentinel, Teams/Outlook/Planner permanecem `draft_only` ate existir OAuth/admin consent, allowlist de destinatarios e politica de auditoria.

## 5. Ordem segura de implantacao

1. Validar Sentinel MCP local.
2. Configurar GitHub MCP remoto, se o cliente suportar.
3. Se remoto nao estiver disponivel, baixar binario oficial GitHub MCP em `tools/mcp/`.
4. Criar PAT fine-grained read-only.
5. Testar GitHub somente leitura.
6. Solicitar habilitacao do Power BI MCP ao admin, se fizer sentido.
7. Configurar Power BI remoto no VS Code.
8. Avaliar Microsoft Graph Enterprise MCP com TI/seguranca.
9. So depois considerar tools de escrita.

## 6. Regras de seguranca

- Nunca versionar tokens.
- Nunca versionar configs locais com secrets.
- Comecar todo MCP externo em read-only.
- Separar Sentinel MCP de MCPs externos.
- Nao usar MCP generico em arquivos ou banco Sentinel.
- Toda escrita deve exigir confirmacao humana.
- Se uma ferramenta externa pedir caminho local do projeto, negar acesso a pastas de dados.

## 7. Arquivos relacionados

- `docs/mcp-client-config.no-docker.example.json`
- `scripts/mcp/check_external_mcp_prereqs.ps1`
- `mcp_server/server.py`
- `mcp_server/config/sentinel_mcp.toml`
