# Launch GeoPort (PR #194 build) on Windows with the iOS 27 modern DVT bridge.
# - Self-elevates first, because pyuac's own relaunch does not carry environment
#   variables into the elevated process (the bridge would be silently disabled).
# - Legacy env (.venv-legacy): GeoPort + pymobiledevice3 4.16.7 for discovery / older iOS.
# - Modern env (.venv-modern): pymobiledevice3 11.x used only for iOS 27 location over USB.

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Relaunching as Administrator...'
    $shell = (Get-Process -Id $PID).Path
    Start-Process $shell -Verb RunAs -ArgumentList (@('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"") + $args)
    exit
}

$legacyPython = Join-Path $root '.venv-legacy\Scripts\python.exe'
$modernPython = Join-Path $root '.venv-modern\Scripts\python.exe'

# Create the virtual environments from the requirements files on first run.
function New-GeoPortEnv($name, $python, $requirements) {
    if (Test-Path $python) { return }
    Write-Host "Creating $name from $requirements ..."
    $venvDir = Join-Path $root $name
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv $venvDir --python 3.12
        uv pip install -p $python -r (Join-Path $root $requirements)
    } else {
        python -m venv $venvDir
        & $python -m pip install -r (Join-Path $root $requirements)
    }
    if (-not (Test-Path $python)) { throw "Failed to create $name" }
}
New-GeoPortEnv '.venv-legacy' $legacyPython 'requirements-legacy.txt'
New-GeoPortEnv '.venv-modern' $modernPython 'requirements-modern.txt'

$env:GEOPORT_MODERN_PMD3_PYTHON = $modernPython
Set-Location (Join-Path $root 'src')
Write-Host "Modern bridge: $modernPython"
& $legacyPython main.py @args
