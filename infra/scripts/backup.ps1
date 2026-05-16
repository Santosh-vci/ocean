param(
  [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dbDump = Join-Path $OutputDir "coalflow-db-$timestamp.dump"
$exportArchive = Join-Path $OutputDir "coalflow-exports-$timestamp.tgz"

docker compose exec -T db sh -lc 'pg_dump -U "${POSTGRES_USER:-coalflow}" -d "${POSTGRES_DB:-coalflow}" -Fc -f /tmp/coalflow-backup.dump'
docker compose cp db:/tmp/coalflow-backup.dump $dbDump
docker compose exec -T db rm -f /tmp/coalflow-backup.dump

docker compose exec -T api sh -lc 'mkdir -p /tmp/coalflow_exports && tar -C /tmp/coalflow_exports -czf /tmp/coalflow-exports.tgz .'
docker compose cp api:/tmp/coalflow-exports.tgz $exportArchive
docker compose exec -T api rm -f /tmp/coalflow-exports.tgz

Write-Host "Database backup: $dbDump"
Write-Host "Export artifact archive: $exportArchive"
