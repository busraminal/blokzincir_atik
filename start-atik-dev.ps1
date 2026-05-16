# ATIK: Ollama + Node (BLOCKCHAIN/atik-dlt) + FastAPI (MACHINE_LEARNING)
# Çift tık veya: powershell -ExecutionPolicy Bypass -File .\start-atik-dev.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonDir = Join-Path $Root "MACHINE_LEARNING\atik_ai_multi_agent_decision-main"
$DltDir = Join-Path $Root "BLOCKCHAIN\atik-dlt"

if (-not (Test-Path $DltDir)) {
  Write-Host "BLOCKCHAIN/atik-dlt bulunamadi: $DltDir" -ForegroundColor Red
  exit 1
}

# .env icinden PORT oku
$Port = 5055
$envPath = Join-Path $DltDir ".env"
if (Test-Path $envPath) {
  Get-Content $envPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*PORT\s*=\s*(\d+)\s*$') { $script:Port = [int]$matches[1] }
  }
}

function Test-PortListening([int]$p) {
  try {
    $c = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
    return $null -ne $c
  } catch {
    $line = netstat -ano 2>$null | Select-String -Pattern "LISTENING" | Select-String -Pattern ":$p\s"
    return $null -ne $line
  }
}

# Ollama (11434) — yoksa yeni pencerede baslat
if (-not (Test-PortListening 11434)) {
  Write-Host "Ollama (11434) kapali — ollama serve aciliyor..." -ForegroundColor Yellow
  $ollamaCmd = "Write-Host 'Ollama'; if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama serve } else { Write-Host 'ollama komutu yok; https://ollama.com kurun'; pause }"
  Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $ollamaCmd
  Start-Sleep -Seconds 2
} else {
  Write-Host "Ollama zaten dinliyor: 11434" -ForegroundColor Green
}

# FastAPI 8000 — Docker'da API zaten ayaktaysa atla
$skipLocalApi = $false
if (Test-PortListening 8000) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health/" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) {
      $skipLocalApi = $true
      Write-Host "8000: ATIK API hazir (Docker veya mevcut sunucu) — yerel uvicorn atlaniyor." -ForegroundColor Green
    }
  } catch {
    Write-Host "8000 acik ama /health yanit vermedi; yerel uvicorn denenecek." -ForegroundColor Yellow
  }
}

if (-not $skipLocalApi -and -not (Test-PortListening 8000)) {
  if (-not (Test-Path $PythonDir)) {
    Write-Host "Uyari: MACHINE_LEARNING/atik_ai_multi_agent_decision-main yok; ATIK AI proxy 502 verebilir: $PythonDir" -ForegroundColor Yellow
  } else {
    Write-Host "FastAPI baslatiliyor: 127.0.0.1:8000" -ForegroundColor Cyan
    $py = "Set-Location -LiteralPath '$PythonDir'; python -m uvicorn atik_ai.api.routes:app --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $py
    Start-Sleep -Seconds 2
  }
} elseif (-not $skipLocalApi) {
  Write-Host "Port 8000 zaten kullaniliyor (FastAPI calisiyor olabilir)" -ForegroundColor Green
}

# Node (tek adres: site + API + proxy)
if (Test-PortListening $Port) {
  Write-Host "Port $Port dolu — Node zaten calisiyor olabilir. Tarayici aciliyor." -ForegroundColor Yellow
} else {
  Write-Host "Node baslatiliyor: http://127.0.0.1:$Port/" -ForegroundColor Cyan
  $nodeCmd = @"
Set-Location -LiteralPath '$DltDir'
`$env:ATIK_AI_PROXY_URL = 'http://127.0.0.1:8000'
npm start
"@
  Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $nodeCmd
  $deadline = (Get-Date).AddSeconds(12)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortListening $Port) { break }
    Start-Sleep -Milliseconds 400
  }
}

$openUrl = "http://127.0.0.1:$Port/"
Write-Host ""
Write-Host "=== Tek adres (tarayici) ===" -ForegroundColor Green
Write-Host $openUrl
Write-Host ""
Write-Host "Arka plan: Ollama 11434 | FastAPI 8000 | Node $Port" -ForegroundColor DarkGray
Start-Process $openUrl
