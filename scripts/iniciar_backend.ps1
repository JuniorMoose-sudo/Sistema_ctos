# Inicia o backend Django em produção (Windows / waitress).
# Uso:  .\scripts\iniciar_backend.ps1
$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $raiz ".venv"
$backend = Join-Path $raiz "backend"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Venv nao encontrado em $python. Crie com: python -m venv .venv"
    exit 1
}

# Garante a pasta de logs
New-Item -ItemType Directory -Force -Path (Join-Path $backend "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $backend "media") | Out-Null

Push-Location $backend
try {
    Write-Host "[1/3] Aplicando migracoes..." -ForegroundColor Cyan
    & $python manage.py migrate

    Write-Host "[2/3] Coletando arquivos estaticos..." -ForegroundColor Cyan
    & $python manage.py collectstatic --noinput

    Write-Host "[3/3] Subindo waitress em http://0.0.0.0:8000 ..." -ForegroundColor Green
    & $python -m waitress --host=0.0.0.0 --port=8000 --threads=8 config.wsgi:application
}
finally {
    Pop-Location
}
