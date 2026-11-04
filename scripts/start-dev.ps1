param(
    [string]$MongoServiceName = "MongoDB"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $repositoryRoot "backend"
$frontendDirectory = Join-Path $repositoryRoot "frontend"
$pythonPath = Join-Path $backendDirectory "venv\Scripts\python.exe"
$backendEnv = Join-Path $backendDirectory ".env"
$frontendEnv = Join-Path $frontendDirectory ".env"

if (-not (Test-Path $backendEnv)) {
    throw "Missing $backendEnv. Copy backend\.env.example and configure it first."
}
if (-not (Test-Path $frontendEnv)) {
    throw "Missing $frontendEnv. Copy frontend\.env.example first."
}
if (-not (Test-Path $pythonPath)) {
    throw "Missing backend virtual environment. Create it and install backend\requirements-dev.txt."
}

$npm = Get-Command npm.cmd -ErrorAction Stop
$mongoService = Get-Service -Name $MongoServiceName -ErrorAction Stop
if ($mongoService.Status -ne "Running") {
    Write-Host "Starting MongoDB Windows service '$MongoServiceName'..."
    Start-Service -Name $MongoServiceName
    $mongoService = Get-Service -Name $MongoServiceName
    $mongoService.WaitForStatus(
        [System.ServiceProcess.ServiceControllerStatus]::Running,
        [TimeSpan]::FromSeconds(30)
    )
}
Write-Host "MongoDB service '$MongoServiceName' is running."

$backendProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000") `
    -WorkingDirectory $backendDirectory `
    -PassThru
$frontendProcess = Start-Process `
    -FilePath $npm.Source `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $frontendDirectory `
    -PassThru

Write-Host "Backend development server started (PID $($backendProcess.Id))."
Write-Host "Frontend development server started (PID $($frontendProcess.Id))."
Write-Host "Frontend: http://127.0.0.1:5173/"
Write-Host "API health: http://127.0.0.1:8000/api/health/"
