param(
  [switch]$ForcePython
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$exePath = Join-Path $root 'dist\ブラウザFFMPEG.exe'

if (-not $ForcePython -and (Test-Path $exePath)) {
  Write-Host 'Starting packaged EXE...'
  & $exePath
  exit $LASTEXITCODE
}

if ($ForcePython) {
  Write-Host 'ForcePython specified. Starting Python app...'
} else {
  Write-Host 'Packaged EXE not found. Starting Python app...'
}
$env:BROWSER_FFMPEG_OPEN_BROWSER = '1'
& python app.py
exit $LASTEXITCODE
