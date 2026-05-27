#Requires -Version 5.1
<#
.SYNOPSIS
    Inicia todos os servicos do Develoi Transcription API com um unico comando.
.EXAMPLE
    .\start.ps1
    .\start.ps1 -Port 8080
    .\start.ps1 -SkipOllama
#>
param(
    [int]$Port = 8000,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$tag, [string]$msg, [string]$color = "Cyan") {
    Write-Host "[$tag] " -ForegroundColor $color -NoNewline
    Write-Host $msg
}

Write-Host ""
Write-Host " ========================================" -ForegroundColor DarkCyan
Write-Host "   Develoi Local AI - Iniciando servicos" -ForegroundColor White
Write-Host " ========================================" -ForegroundColor DarkCyan
Write-Host ""

Set-Location $PSScriptRoot

# --- .env ---
if (-not (Test-Path ".env")) {
    Write-Step "SETUP" "Criando .env a partir de .env.example..." "Yellow"
    Copy-Item ".env.example" ".env"
}

# --- tmp dir ---
if (-not (Test-Path "tmp")) { New-Item -ItemType Directory "tmp" | Out-Null }

# --- Python ---
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Step "ERRO" "Python nao encontrado. Instale Python 3.10+ e tente novamente." "Red"
    exit 1
}

# --- Virtualenv ---
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Step "SETUP" "Criando ambiente virtual Python..." "Yellow"
    python -m venv .venv
}

Write-Step "SETUP" "Ativando ambiente virtual..."
& ".venv\Scripts\Activate.ps1"

# --- Dependencias ---
$fastapiCheck = python -c "import fastapi" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Step "SETUP" "Instalando dependencias Python..." "Yellow"
    pip install -r requirements.txt
}

# --- Ollama ---
if (-not $SkipOllama) {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Step "AVISO" "Ollama nao encontrado. Baixe em: https://ollama.com/download" "Yellow"
        Write-Step "AVISO" "A API de transcricao funcionara, mas a IA estara offline." "Yellow"
    } else {
        # Verifica se ja esta rodando
        $ollamaUp = $false
        try {
            $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 -UseBasicParsing
            $ollamaUp = $true
        } catch {}

        if (-not $ollamaUp) {
            Write-Step "OLLAMA" "Iniciando Ollama em background..." "Cyan"
            Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden

            Write-Step "OLLAMA" "Aguardando Ollama ficar pronto..." "Cyan"
            for ($i = 0; $i -lt 15; $i++) {
                Start-Sleep -Seconds 1
                try {
                    $null = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 -UseBasicParsing
                    $ollamaUp = $true
                    break
                } catch {}
            }
            if ($ollamaUp) {
                Write-Step "OLLAMA" "Ollama esta online." "Green"
            } else {
                Write-Step "AVISO" "Ollama demorou para responder. Continuando mesmo assim..." "Yellow"
            }
        } else {
            Write-Step "OLLAMA" "Ollama ja esta rodando." "Green"
        }

        # Modelo padrao
        $envContent = Get-Content ".env" -ErrorAction SilentlyContinue
        $modelLine = $envContent | Where-Object { $_ -match "^OLLAMA_DEFAULT_MODEL=" }
        $model = if ($modelLine) { ($modelLine -split "=", 2)[1].Trim() } else { "qwen2.5:7b" }

        $modelList = ollama list 2>&1
        if ($modelList -notmatch [regex]::Escape($model)) {
            Write-Step "OLLAMA" "Baixando modelo $model (pode demorar na primeira vez)..." "Yellow"
            ollama pull $model
        } else {
            Write-Step "OLLAMA" "Modelo $model ja disponivel." "Green"
        }
    }
}

# --- API ---
Write-Host ""
Write-Step "API" "Iniciando servidor FastAPI na porta $Port..." "Green"
Write-Host ""
Write-Host "  Painel: " -NoNewline; Write-Host "http://localhost:$Port" -ForegroundColor Yellow
Write-Host "  Docs:   " -NoNewline; Write-Host "http://localhost:$Port/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Pressione Ctrl+C para parar." -ForegroundColor DarkGray
Write-Host " ========================================" -ForegroundColor DarkCyan
Write-Host ""

uvicorn main:app --host 0.0.0.0 --port $Port --reload
