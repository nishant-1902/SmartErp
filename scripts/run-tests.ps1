$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot "backend"
$frontendDirectory = Join-Path $repositoryRoot "frontend"
$pythonPath = Join-Path $backendDirectory "venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    throw "Missing backend virtual environment. Create it and install backend\requirements-dev.txt."
}
$npm = Get-Command npm.cmd -ErrorAction Stop

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Executable $($Arguments -join ' ')"
    }
}

Push-Location $backendDirectory
try {
    Invoke-CheckedCommand $pythonPath @("manage.py", "check")
    Invoke-CheckedCommand $pythonPath @("-m", "pytest", "-v")
    Invoke-CheckedCommand $pythonPath @(
        "-m", "pytest", "--cov=.", "--cov-report=term-missing"
    )
}
finally {
    Pop-Location
}

Push-Location $frontendDirectory
try {
    Invoke-CheckedCommand $npm.Source @("test")
    Invoke-CheckedCommand $npm.Source @("run", "lint")
    Invoke-CheckedCommand $npm.Source @("run", "build")
}
finally {
    Pop-Location
}
