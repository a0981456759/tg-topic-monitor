$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
$exitCode = 1
try {
    $env:PYTHONPATH = 'src'
    & python -m tg_monitor digest
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $exitCode
