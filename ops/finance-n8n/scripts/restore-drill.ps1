param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [string]$EnvFile = ".env",
    [string]$Confirmation
)
$ErrorActionPreference = "Stop"
if ($Confirmation -ne "RESTORE_TO_ISOLATED_DATABASE") { throw "Use -Confirmation RESTORE_TO_ISOLATED_DATABASE" }
$root = Split-Path -Parent $PSScriptRoot
$backup = (Resolve-Path -LiteralPath $BackupDirectory).Path
$compose = @("compose", "--env-file", $EnvFile, "-f", (Join-Path $root "compose.yml"))
function Invoke-Compose([string[]]$Arguments) {
    $result = & docker @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker restore command failed" }
    return $result
}
Get-Content -LiteralPath (Join-Path $backup "SHA256SUMS.txt") | ForEach-Object {
    $parts = $_ -split '\s+', 2
    $path = [IO.Path]::GetFullPath((Join-Path $backup $parts[1]))
    if (-not $path.StartsWith($backup + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Invalid backup path" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) { throw "Backup checksum mismatch" }
}
foreach ($kind in @("n8n", "gateway")) {
    $dump = Join-Path $backup "finance-$kind.dump"
    if (-not (Test-Path -LiteralPath $dump)) { throw "Missing dump: $kind" }
    $db = "finance_restore_" + [Guid]::NewGuid().ToString('N')
    $containerFile = "/tmp/$db.dump"
    $table = if ($kind -eq "gateway") { "gateway_runs" } else { "workflow_entity" }
    try {
        Invoke-Compose @("exec", "-T", "postgres", "sh", "-c", 'createdb -U "$POSTGRES_USER" "$1"', "sh", $db)
        Invoke-Compose @("cp", $dump, "postgres:$containerFile")
        Invoke-Compose @("exec", "-T", "postgres", "sh", "-c", 'pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner --no-privileges "$2"', "sh", $db, $containerFile)
        $sql = "SELECT count(*) FROM information_schema.tables WHERE table_name='$table';"
        $count = Invoke-Compose @("exec", "-T", "postgres", "sh", "-c", 'psql -U "$POSTGRES_USER" -d "$1" -Atqc "$2"', "sh", $db, $sql)
        if (($count -join "").Trim() -ne "1") { throw "Restore verification failed: $kind" }
        Write-Output "Isolated restore PASS: $kind"
    } finally {
        Invoke-Compose @("exec", "-T", "postgres", "sh", "-c", 'dropdb -U "$POSTGRES_USER" --if-exists "$1"', "sh", $db)
        Invoke-Compose @("exec", "-T", "postgres", "rm", "-f", "--", $containerFile)
    }
}
