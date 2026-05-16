# Docker Desktop acik olmali. Ilk calistirmada Fabric indirmesi uzun surebilir.
# Not: C:\... atik  gibi Turkce/Unicode yol, WSL'e aynen gidince bozulur (No such file).
# cozum: 8.3 kisa yol (PROJEL~1 vb.) veya C:\dev\atik-work\  gibi Turkce'siz yol.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BootstrapSh = Join-Path $Root "scripts\bootstrap-fabric.sh"

function Get-ShortPath8Dot3 {
  param([string]$Path)
  try {
    if (-not (Test-Path -LiteralPath $Path)) { return $Path }
    $rp = (Resolve-Path -LiteralPath $Path).Path
    $fso = New-Object -ComObject Scripting.FileSystemObject
    if ((Get-Item -LiteralPath $rp) -is [System.IO.DirectoryInfo]) {
      return $fso.GetFolder($rp).ShortPath
    }
    return $fso.GetFile($rp).ShortPath
  } catch {
    return $Path
  }
}

# wsl + wslpath: PowerShell 'C:\Users\...' ile native cagirdiginda backslash'ler
# silinebiliyor (C:Users...). On egik + ayri arguman ile kacin.
function Convert-WinPathToWsl {
  param([string]$Path)
  if (-not $Path) { return $null }
  $winPath = $Path -replace "\\", "/"
  $p = [System.Diagnostics.ProcessStartInfo]::new()
  $p.FileName = "wsl.exe"
  $p.Arguments = "wslpath -a " + $winPath
  if ($winPath -match " ") { $p.Arguments = "wslpath -a " + [char]34 + $winPath + [char]34 }
  $p.UseShellExecute = $false
  $p.RedirectStandardOutput = $true
  $p.RedirectStandardError = $true
  $p.CreateNoWindow = $true
  $proc = [System.Diagnostics.Process]::new()
  $proc.StartInfo = $p
  [void]$proc.Start()
  $out = $proc.StandardOutput.ReadToEnd()
  $err = $proc.StandardError.ReadToEnd()
  $null = $proc.WaitForExit(20000)
  $t = $out.Trim()
  if ($t) { return $t }
  if ($proc.ExitCode -ne 0) { if ($err) { Write-Host $err.Trim() -ForegroundColor Red }; return $null }
  return $null
}

docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host @"

[!] Docker calismiyor.
    1) Docker Desktop ac, trey ikonu hazir olana kadar bekle.
    2) Docker - Settings - Resources - WSL Integration: Ubuntu acik olsun.
    3) Scripti yeniden calistir.

"@ -ForegroundColor Yellow
  exit 1
}

Write-Host ">> 1/2 Fabric bootstrap (WSL)..." -ForegroundColor Cyan
$PathForWsl = Get-ShortPath8Dot3 -Path $BootstrapSh
$wslPath = Convert-WinPathToWsl -Path $PathForWsl
if (-not $wslPath) {
  Write-Host "wslpath basarisiz. Projeyi C:\dev\atik-work\gibi Turkce'siz yola tasi, veya 8.3 (fsutil) kapaliysa farkli diske tasi" -ForegroundColor Red
  exit 1
}
# bash -lc icinde de $wslPath icin tek tirnak guvenli (Türkce yol cevrilmis olsa bile)
wsl -e bash -lc "bash -- '$wslPath'"
if ($LASTEXITCODE -ne 0) {
  Write-Host "Bootstrap hata. Hâlâ kırılıyorsa: projeyi C:\dev\atik-work\atik-dlt\  gibi Turkce icermeyen yola tasi" -ForegroundColor Red
  Write-Host "Veya WSL icinde:  cd (manuel wslpath ile) && bash scripts/bootstrap-fabric.sh" -ForegroundColor Red
  exit $LASTEXITCODE
}

Write-Host ">> 2/2 API (Fabric Gateway, Windows Node)..." -ForegroundColor Cyan
$cryptoWin = (& wsl -e bash -lc 'wslpath -w "$HOME/fabric-samples/test-network/organizations/peerOrganizations/org1.example.com"').Trim()
if (-not $cryptoWin) { throw "CRYPTO_PATH uretilemedi" }

Set-Location $Root
$env:USE_FABRIC = "1"
$env:CRYPTO_PATH = $cryptoWin
npm run start:fabric
