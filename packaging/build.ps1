<#
.SYNOPSIS
  Builds Parkomate Station for other PCs: the program folder, a quick self-check, then the
  Setup.exe (Inno Setup) - or a portable .zip when Inno Setup is not installed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\build.ps1

  Result (in dist\):
    ParkomateStation\                       the program folder (PyInstaller)
    ParkomateStation-Setup-<version>.exe    the installer  (needs Inno Setup 6.3+:
                                            winget install JRSoftware.InnoSetup)
    ParkomateStation-<version>-portable.zip only when Inno Setup is missing
#>
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }

$version = (& uv run python -c "import parkomate; print(parkomate.__version__)").Trim()
Step "Parkomate Station $version"

if (-not $SkipTests) {
    Step "Tests"
    & uv run pytest -q
    if ($LASTEXITCODE -ne 0) { throw "tests failed - fix them before building" }
}

Step "Icon"
& uv run python packaging\make_icon.py packaging\parkomate.ico
if ($LASTEXITCODE -ne 0) { throw "icon failed" }

Step "Program folder (PyInstaller)"
& uv run --group build pyinstaller packaging\parkomate.spec --noconfirm --clean `
    --distpath dist --workpath build\pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Step "Self-check of the built program"
$exe = Join-Path $root "dist\ParkomateStation\parkomate.exe"
& $exe --version
if ($LASTEXITCODE -ne 0) { throw "the built parkomate.exe does not start" }
$check = Join-Path $env:TEMP ("parkomate-build-check-" + [guid]::NewGuid().ToString("N"))
$env:PARKOMATE_DATA_DIR = $check
try {
    & $exe doctor   # a fresh data folder: "no administrator yet" is expected here
    & $exe measuring-device --send good --port 9 | Out-Null   # the simulator runs (nobody listens)
} finally {
    Remove-Item Env:\PARKOMATE_DATA_DIR
    Remove-Item -Recurse -Force $check -ErrorAction SilentlyContinue
}

if ($SkipInstaller) { Step "Done (installer skipped)"; exit 0 }

Step "Installer"
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$version" packaging\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    Write-Host "`nInstaller: dist\ParkomateStation-Setup-$version.exe" -ForegroundColor Green
} else {
    $zip = "dist\ParkomateStation-$version-portable.zip"
    Compress-Archive -Path dist\ParkomateStation\* -DestinationPath $zip -Force
    Write-Host "`nInno Setup is not installed, so no Setup.exe was made." -ForegroundColor Yellow
    Write-Host "Portable zip: $zip  (unzip anywhere, run ParkomateStation.exe)"
    Write-Host "For the real installer: winget install JRSoftware.InnoSetup  - then run this again."
}
