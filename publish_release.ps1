$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$exePath = Join-Path $root 'dist\ブラウザFFMPEG.exe'
$zipPath = Join-Path $root 'dist\ブラウザFFMPEG.zip'
$tagName = 'exe-latest'

$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) {
  $candidate = 'C:\Program Files\GitHub CLI\gh.exe'
  if (Test-Path $candidate) {
    $gh = Get-Item $candidate
  }
}

if (-not $gh) {
  throw "GitHub CLI 'gh' is required. Install it first, then run this script again."
}

$ghPath = $gh.Source

if (-not (Test-Path $exePath)) {
  throw "EXE not found: $exePath. Run build_exe.ps1 first."
}

if (Test-Path $zipPath) {
  Remove-Item $zipPath -Force
}

Compress-Archive -Path $exePath -DestinationPath $zipPath -CompressionLevel Optimal

$releaseExists = $true
try {
  & $ghPath release view $tagName | Out-Null
}
catch {
  $releaseExists = $false
}

$releaseTitle = 'ブラウザFFMPEG EXE'
$releaseNotes = "Automated release built from $(git rev-parse --short HEAD)"

if ($releaseExists) {
  & $ghPath release upload $tagName $exePath $zipPath --clobber
}
else {
  & $ghPath release create $tagName $exePath $zipPath --title $releaseTitle --notes $releaseNotes --prerelease
}

Write-Host "Release published: $tagName"
