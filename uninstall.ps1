# Removes Book Tracker from Startup and stops the running server.
# App files, venv, config.ini and the database are left untouched.
$ErrorActionPreference = 'Stop'
$vpy = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { $vpy = 'python' }
& $vpy (Join-Path $PSScriptRoot 'app.py') uninstall-service
