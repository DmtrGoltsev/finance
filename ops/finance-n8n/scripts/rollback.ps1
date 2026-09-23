param(
    [Parameter(Mandatory=$true)][string]$PreviousImage,
    [Parameter(Mandatory=$true)][string]$PreviousGatewayImage,
    [Parameter(Mandatory=$true)][string]$WorkflowBackup,
    [string]$EnvFile = ".env",
    [string]$Confirmation
)

$ErrorActionPreference = "Stop"
if ($Confirmation -ne "ROLLBACK_FINANCE_N8N") { throw "Use -Confirmation ROLLBACK_FINANCE_N8N" }
if ($PreviousImage -notmatch '^n8nio/n8n:[0-9]+\.[0-9]+\.[0-9]+$') { throw "PreviousImage must be an exact n8n version" }
if ($PreviousGatewayImage -notmatch '^[a-zA-Z0-9./_-]+:[a-zA-Z0-9._-]+$' -or $PreviousGatewayImage.EndsWith(':latest')) { throw "PreviousGatewayImage must use a fixed tag" }
$root = Split-Path -Parent $PSScriptRoot
$env:FINANCE_N8N_IMAGE = $PreviousImage
$env:FINANCE_GATEWAY_IMAGE = $PreviousGatewayImage
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") stop n8n analysis-gateway
if ($LASTEXITCODE -ne 0) { throw "Stop failed" }
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") up -d --no-build --wait analysis-gateway n8n
if ($LASTEXITCODE -ne 0) { throw "Rollback startup failed" }
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") cp $WorkflowBackup n8n:/tmp/finance-workflow.json
if ($LASTEXITCODE -ne 0) { throw "Workflow copy failed" }
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T n8n n8n import:workflow --input=/tmp/finance-workflow.json
if ($LASTEXITCODE -ne 0) { throw "Workflow import failed" }
Write-Output "Rollback imported but did not activate workflows. Verify and activate the intended version manually."
