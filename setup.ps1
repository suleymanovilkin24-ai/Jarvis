Write-Host "========================================"
Write-Host "      J.A.R.V.I.S Windows Kurulum"
Write-Host "========================================"

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python bulunamadi. Python 3.11+ kurup tekrar deneyin."
    exit 1
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "Kurulum tamamlandi. Baslatmak icin:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python main.py"
