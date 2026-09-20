param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [string]$EnvFile = ".env",
    [string]$Confirmation
)

$ErrorActionPreference = "Stop"
if ($Confirmation -ne "RESTORE_TO_ISOLATED_DATABASE") { throw "Use -Confirmation RESTORE_TO_ISOLATED_DATABASE" }
$root = Split-Path -Parent $PSScriptRoot
$backup = Resolve-Path -LiteralPath $BackupDirectory
$dump = Join-Path $backup "finance-n8n.dump"
if (-not (Test-Path -LiteralPath $dump)) { throw "finance-n8n.dump not found" }
$db = "finance_n8n_restore_" + (Get-Date -Format "yyyyMMddHHmmss")

Get-Content -LiteralPath (Join-Path $backup "SHA256SUMS.txt") | ForEach-Object {
    $parts = $_ -split '\s+', 2
    $actual = (Get-FileHash -LiteralPath (Join-Path $backup $parts[1]) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $parts[0]) { throw "Backup checksum mismatch: $($parts[1])" }
}

docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres sh -c "createdb -U \"`$POSTGRES_USER\" $db"
try {
    Get-Content -LiteralPath $dump -AsByteStream | docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres sh -c "pg_restore -U \"`$POSTGRES_USER\" -d $db --no-owner --no-privileges"
    $count = docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres psql -U finance_n8n -d $db -Atqc "SELECT count(*) FROM information_schema.tables WHERE table_name='finance_analysis_runs';"
    if ($count.Trim() -ne '1') { throw "Restore verification failed" }
    Write-Output "Isolated restore drill PASS: $db"
} finally {
    docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres sh -c "dropdb -U \"`$POSTGRES_USER\" --if-exists $db"
}
