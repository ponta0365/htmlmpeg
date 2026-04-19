$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$exePath = Join-Path $root 'dist\ブラウザFFMPEG.exe'
$zipPath = Join-Path $root 'dist\ブラウザFFMPEG.zip'
$tagName = 'exe-latest'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI 'gh' is required. Install it first, then run this script again."
}

if (-not (Test-Path $exePath)) {
  throw "EXE not found: $exePath. Run build_exe.ps1 first."
}

if (Test-Path $zipPath) {
  Remove-Item $zipPath -Force
}

Compress-Archive -Path $exePath -DestinationPath $zipPath -CompressionLevel Optimal

$releaseExists = $true
try {
  gh release view $tagName | Out-Null
}
catch {
  $releaseExists = $false
}

$releaseTitle = 'ブラウザFFMPEG EXE'
$releaseNotes = "Automated release built from $(git rev-parse --short HEAD)"

if ($releaseExists) {
  gh release upload $tagName $exePath $zipPath --clobber
}
else {
  gh release create $tagName $exePath $zipPath --title $releaseTitle --notes $releaseNotes --prerelease
}

Write-Host "Release published: $tagName"
