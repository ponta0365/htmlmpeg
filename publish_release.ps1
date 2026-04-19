$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$exePath = Join-Path $root 'dist\ブラウザFFMPEG.exe'
$zipPath = Join-Path $root 'dist\ブラウザFFMPEG.zip'
$releaseExeName = 'ブラウザFFMPEG.exe'
$releaseZipName = 'ブラウザFFMPEG.zip'
$releaseExePath = Join-Path $root "dist\$releaseExeName"
$releaseZipPath = Join-Path $root "dist\$releaseZipName"
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

$ghPath = if ($gh.PSObject.Properties.Match('Source').Count -gt 0 -and $gh.Source) { $gh.Source } else { $gh.FullName }

if (-not (Test-Path $exePath)) {
  throw "EXE not found: $exePath. Run build_exe.ps1 first."
}

if (Test-Path $zipPath) {
  Remove-Item $zipPath -Force
}

if (Test-Path $releaseExePath) {
  Remove-Item $releaseExePath -Force
}
if (Test-Path $releaseZipPath) {
  Remove-Item $releaseZipPath -Force
}

Compress-Archive -Path $exePath -DestinationPath $zipPath -CompressionLevel Optimal
Copy-Item -Path $exePath -Destination $releaseExePath -Force
Copy-Item -Path $zipPath -Destination $releaseZipPath -Force

$releaseExists = $true
try {
  & $ghPath release view $tagName | Out-Null
}
catch {
  $releaseExists = $false
}

$releaseTitle = 'ブラウザFFMPEG Windows EXE'
$releaseNotes = "Windows pre-release build of htmlmpeg.`n`nIncluded:`n- Browser-based UI for local FFmpeg compression`n- Python backend`n- Preset-based workflows for video, audio, and image files`n`nAssets:`n- ブラウザFFMPEG.exe`n- ブラウザFFMPEG.zip`n`nUsage:`n1. Download one of the assets.`n2. Extract the zip if needed.`n3. Run the EXE on Windows.`n`nFor project details, see the repository README."

function Remove-ReleaseAssetIfExists {
  param(
    [string]$Tag,
    [string]$AssetName
  )

  try {
    & $ghPath release delete-asset $Tag $AssetName -y | Out-Null
  }
  catch {
    # Ignore missing asset errors so the publish flow stays idempotent.
  }
}

if ($releaseExists) {
  Remove-ReleaseAssetIfExists -Tag $tagName -AssetName 'FFMPEG.exe'
  Remove-ReleaseAssetIfExists -Tag $tagName -AssetName 'FFMPEG.zip'
  Remove-ReleaseAssetIfExists -Tag $tagName -AssetName $releaseExeName
  Remove-ReleaseAssetIfExists -Tag $tagName -AssetName $releaseZipName
  & $ghPath release upload $tagName $releaseExePath $releaseZipPath --clobber
}
else {
  & $ghPath release create $tagName $releaseExePath $releaseZipPath --title $releaseTitle --notes $releaseNotes --prerelease
}

Write-Host "Release published: $tagName"
