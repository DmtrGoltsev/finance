param(
    [Parameter(Mandatory=$true)][string]$PreviousImage,
    [Parameter(Mandatory=$true)][string]$WorkflowBackup,
    [string]$EnvFile = ".env",
    [string]$Confirmation
)

$ErrorActionPreference = "Stop"
if ($Confirmation -ne "ROLLBACK_FINANCE_N8N") { throw "Use -Confirmation ROLLBACK_FINANCE_N8N" }
if ($PreviousImage -notmatch '^n8nio/n8n:[0-9]+\.[0-9]+\.[0-9]+$') { throw "PreviousImage must be an exact n8n version" }
$root = Split-Path -Parent $PSScriptRoot
$env:FINANCE_N8N_IMAGE = $PreviousImage
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") stop n8n
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") up -d --wait n8n
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") cp $WorkflowBackup n8n:/tmp/finance-workflow.json
docker compose --env-file $EnvFile -f (Join-Path $root "compose.yml") exec -T n8n n8n import:workflow --input=/tmp/finance-workflow.json
Write-Output "Rollback imported but did not activate workflows. Verify and activate the intended version manually."
