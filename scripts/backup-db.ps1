param(
    [string]$BackupDirectory = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendEnv = Join-Path $repositoryRoot "backend\.env"

if (-not (Test-Path $backendEnv)) {
    throw "Missing $backendEnv. Configure the application MongoDB connection first."
}

function Read-DotEnvValue {
    param(
        [string]$FilePath,
        [string]$Name
    )

    $line = Get-Content $FilePath |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -First 1
    if (-not $line) {
        return $null
    }

    $value = ($line -split "=", 2)[1].Trim()
    if (
        $value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'")))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

$mongoUri = if ($env:MONGO_URI) {
    $env:MONGO_URI
}
else {
    Read-DotEnvValue $backendEnv "MONGO_URI"
}
$databaseName = if ($env:MONGO_DB_NAME) {
    $env:MONGO_DB_NAME
}
else {
    Read-DotEnvValue $backendEnv "MONGO_DB_NAME"
}

if (-not $mongoUri -or $mongoUri -match "[<>]") {
    throw "MONGO_URI is missing or still contains a placeholder."
}
if (-not $databaseName -or $databaseName -match "[<>]") {
    throw "MONGO_DB_NAME is missing or still contains a placeholder."
}

$mongodump = Get-Command mongodump.exe -ErrorAction SilentlyContinue
if (-not $mongodump) {
    $mongodump = Get-Command mongodump -ErrorAction SilentlyContinue
}
if (-not $mongodump) {
    throw "mongodump is not installed or is not on PATH. Install MongoDB Database Tools."
}

if (-not $BackupDirectory) {
    $BackupDirectory = Join-Path $repositoryRoot "backups"
}
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $BackupDirectory "smarterp-$timestamp"
if (Test-Path $backupPath) {
    throw "Backup destination already exists: $backupPath"
}
New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null

$configPath = Join-Path ([System.IO.Path]::GetTempPath()) (
    "smarterp-mongodump-{0}.yaml" -f [guid]::NewGuid().ToString("N")
)
$escapedUri = $mongoUri.Replace("'", "''")
try {
    [System.IO.File]::WriteAllText(
        $configPath,
        "uri: '$escapedUri'`n",
        [System.Text.UTF8Encoding]::new($false)
    )
    & $mongodump.Source "--config=$configPath" "--db=$databaseName" `
        "--gzip" "--out=$backupPath"
    if ($LASTEXITCODE -ne 0) {
        throw "mongodump failed with exit code $LASTEXITCODE."
    }
    Write-Host "MongoDB backup completed: $backupPath"
}
finally {
    Remove-Item -LiteralPath $configPath -Force -ErrorAction SilentlyContinue
}
