$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name "ブラウザFFMPEG" `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --add-data "presets;presets" `
  app.py

Write-Host "Build complete: dist\ブラウザFFMPEG.exe"
