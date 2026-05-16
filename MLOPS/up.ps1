# ATIK MLOps: Postgres + FastAPI tek komut
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker bulunamadı. Docker Desktop kurun: https://docs.docker.com/desktop/" -ForegroundColor Red
  exit 1
}
Write-Host "MLOPS: docker compose up --build ..." -ForegroundColor Cyan
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "API:  http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "DB:   localhost:5432  postgres / admin  postgre_database" -ForegroundColor Green
Write-Host "Durdurmak: bu klasörde  docker compose down" -ForegroundColor DarkGray
