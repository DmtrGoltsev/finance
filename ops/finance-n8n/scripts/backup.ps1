param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$EnvFile = ".env"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path (Resolve-Path -LiteralPath $Destination) ("finance-n8n-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $target | Out-Null
$compose = @("compose", "--env-file", $EnvFile, "-f", (Join-Path $root "compose.yml"))
function Invoke-Compose([string[]]$Arguments) {
    & docker @compose @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker backup command failed" }
}
foreach ($kind in @("n8n", "gateway")) {
    $containerFile = "/tmp/finance-$kind-$([Guid]::NewGuid().ToString('N')).dump"
    $database = if ($kind -eq "n8n") { '$POSTGRES_DB' } else { '$FINANCE_GATEWAY_DB' }
    $command = 'pg_dump -U "$POSTGRES_USER" -d "' + $database + '" -Fc -f "$1"'
    try {
        Invoke-Compose @("exec", "-T", "postgres", "sh", "-c", $command, "sh", $containerFile)
        Invoke-Compose @("cp", "postgres:$containerFile", (Join-Path $target "finance-$kind.dump"))
    } finally {
        Invoke-Compose @("exec", "-T", "postgres", "rm", "-f", "--", $containerFile)
    }
}
foreach ($name in @("compose.yml", "workflows", "gateway", "policies", "postgres", "package.json", "package-lock.json")) {
    Copy-Item -LiteralPath (Join-Path $root $name) -Destination $target -Recurse
}
Get-ChildItem -LiteralPath $target -File -Recurse | Get-FileHash -Algorithm SHA256 | ForEach-Object {
    "{0}  {1}" -f $_.Hash.ToLowerInvariant(), [IO.Path]::GetRelativePath($target, $_.Path)
} | Set-Content -LiteralPath (Join-Path $target "SHA256SUMS.txt") -Encoding UTF8
Write-Output "Backup created: $target. Protect encrypted queue/credentials and escrow keys separately."
