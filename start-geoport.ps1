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
foreach ($p in $legacyPython, $modernPython) {
    if (-not (Test-Path $p)) { throw "Missing $p - run the setup steps in the walkthrough first." }
}

$env:GEOPORT_MODERN_PMD3_PYTHON = $modernPython
Set-Location (Join-Path $root 'src')
Write-Host "Modern bridge: $modernPython"
& $legacyPython main.py @args
