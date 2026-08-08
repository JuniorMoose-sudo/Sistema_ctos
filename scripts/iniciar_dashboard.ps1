# Inicia o dashboard Streamlit em produção (Windows).
# Uso:  .\scripts\iniciar_dashboard.ps1
$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $raiz ".venv"
$dashboard = Join-Path $raiz "dashboard"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Venv nao encontrado em $python. Crie com: python -m venv .venv"
    exit 1
}

Push-Location $dashboard
try {
    Write-Host "Subindo dashboard em http://0.0.0.0:8501 ..." -ForegroundColor Green
    & $python -m streamlit run app.py `
        --server.address=0.0.0.0 `
        --server.port=8501 `
        --server.headless=true
}
finally {
    Pop-Location
}
