param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path (Resolve-Path -LiteralPath $Destination) "finance-n8n-$stamp"
New-Item -ItemType Directory -Path $target | Out-Null

$dump = Join-Path $target "finance-n8n.dump"
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > $dump
if ((Get-Item -LiteralPath $dump).Length -eq 0) { throw "Empty PostgreSQL backup" }

Copy-Item -LiteralPath (Join-Path $root "compose.yml") -Destination $target
Copy-Item -LiteralPath (Join-Path $root "workflows") -Destination $target -Recurse
Copy-Item -LiteralPath (Join-Path $root "policies") -Destination $target -Recurse
Get-ChildItem -LiteralPath $target -File -Recurse | Get-FileHash -Algorithm SHA256 | ForEach-Object {
    "{0}  {1}" -f $_.Hash.ToLowerInvariant(), [IO.Path]::GetRelativePath($target, $_.Path)
} | Set-Content -LiteralPath (Join-Path $target "SHA256SUMS.txt") -Encoding UTF8
Write-Output "Backup created without .env or credential values: $target"
