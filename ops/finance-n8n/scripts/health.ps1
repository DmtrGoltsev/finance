param(
    [string]$EnvFile = ".env",
    [string]$BaseUrl = "http://127.0.0.1:5680"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") ps
if ($LASTEXITCODE -ne 0) { throw "Compose status failed" }
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL health failed" }

$secretLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^FINANCE_INGRESS_HMAC_SECRET=' } | Select-Object -Last 1
if (-not $secretLine) { throw "FINANCE_INGRESS_HMAC_SECRET is absent" }
$secret = $secretLine.Substring($secretLine.IndexOf('=') + 1)
$path = "/webhook/internal/finance/health/v1"
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$nonceBytes = New-Object byte[] 24
[Security.Cryptography.RandomNumberGenerator]::Fill($nonceBytes)
$nonce = [Convert]::ToBase64String($nonceBytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$body = "{}"
$canonical = "POST`n$path`n$timestamp`n$nonce`n$body"
$hmac = [Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes($secret))
try { $signature = [Convert]::ToHexString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical))).ToLowerInvariant() } finally { $hmac.Dispose() }
$headers = @{ 'X-Finance-Timestamp' = "$timestamp"; 'X-Finance-Nonce' = $nonce; 'X-Finance-Signature' = $signature }
$response = Invoke-RestMethod -Method Post -Uri "$BaseUrl$path" -Headers $headers -ContentType 'application/json' -Body $body
if ($response.status -ne 'ok') { throw "Signed application health failed" }
Write-Output "Finance n8n signed application health: PASS"
