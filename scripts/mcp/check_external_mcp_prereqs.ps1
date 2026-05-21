$ErrorActionPreference = "Continue"

function Test-Command {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        [pscustomobject]@{
            Name = $Name
            Found = $false
            Source = $null
            Version = $null
        }
        return
    }

    $version = $null
    try {
        if ($Name -eq "docker") {
            $version = (& docker --version) -join " "
        } elseif ($Name -eq "node") {
            $version = (& node --version) -join " "
        } elseif ($Name -eq "npm") {
            $version = (& npm --version) -join " "
        } elseif ($Name -eq "npx") {
            $version = (& npx --version) -join " "
        } elseif ($Name -eq "gh") {
            $version = (& gh --version | Select-Object -First 1) -join " "
        } elseif ($Name -eq "git") {
            $version = (& git --version) -join " "
        }
    } catch {
        $version = "erro ao obter versao: $($_.Exception.Message)"
    }

    [pscustomobject]@{
        Name = $Name
        Found = $true
        Source = $command.Source
        Version = $version
    }
}

$commands = @("git", "docker", "node", "npm", "npx", "gh")
$commands | ForEach-Object { Test-Command $_ } | Format-Table -AutoSize

Write-Host ""
Write-Host "MCP local:" -ForegroundColor Cyan
if (Test-Path ".\.venv-mcp\Scripts\mcp.exe") {
    .\.venv-mcp\Scripts\mcp.exe version
} else {
    Write-Host ".venv-mcp nao encontrada ou mcp.exe ausente."
}

Write-Host ""
Write-Host "Variaveis de proxy:" -ForegroundColor Cyan
[System.Environment]::GetEnvironmentVariables().GetEnumerator() |
    Where-Object { $_.Key -match "proxy" } |
    Select-Object Key, Value |
    Format-Table -AutoSize

Write-Host ""
Write-Host "GitHub DNS:" -ForegroundColor Cyan
Resolve-DnsName github.com -ErrorAction SilentlyContinue | Select-Object Name, Type, IPAddress
