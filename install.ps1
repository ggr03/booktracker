<#
  Book Tracker installer for Windows 10/11 (PowerShell 5.1+).

    powershell -ExecutionPolicy Bypass -File .\install.ps1          # this PC only
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Lan     # also on your network

  Creates .\venv, installs dependencies, creates a private config.ini in
  %APPDATA%\BookTracker, runs the first sync, and adds a Startup-folder
  shortcut that runs the server with pythonw (no console window, no
  admin rights needed).
#>
param([switch]$Lan, [int]$Port = 0)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

# 1. Find Python >= 3.9 (the py launcher first, then python on PATH).
$check = 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'
$pyExe = $null; $pyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c $check 2>$null
    if ($LASTEXITCODE -eq 0) { $pyExe = 'py'; $pyArgs = @('-3') }
}
if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c $check 2>$null
    if ($LASTEXITCODE -eq 0) { $pyExe = 'python' }
}
if (-not $pyExe) {
    Write-Error "Python 3.9+ not found. Install it from https://www.python.org/downloads/windows/ or run: winget install Python.Python.3.12"
}

# 2. Virtualenv + dependencies.
if (-not (Test-Path '.\venv\Scripts\python.exe')) {
    Write-Host 'Creating virtualenv ...'
    & $pyExe @pyArgs -m venv venv
}
$vpy = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
& $vpy -m pip install --quiet --upgrade pip
& $vpy -m pip install --quiet -r requirements.txt

# 3-5. Config, first sync, autostart.
& $vpy app.py init-config
& $vpy app.py sync
if ($LASTEXITCODE -ne 0) { Write-Warning 'Initial sync failed; the server will retry automatically.' }

$svcArgs = @('app.py', 'install-service')
if ($Lan) { $svcArgs += '--lan' }
if ($Port -gt 0) { $svcArgs += @('--port', "$Port") }
& $vpy @svcArgs
& $vpy app.py paths
