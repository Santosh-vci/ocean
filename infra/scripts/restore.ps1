param(
  [Parameter(Mandatory = $true)]
  [string]$DatabaseDump,
  [string]$ExportArchive = "",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not $Force) {
  throw "Restore replaces the current local database. Re-run with -Force after confirming the target."
}

if (-not (Test-Path -LiteralPath $DatabaseDump)) {
  throw "Database dump not found: $DatabaseDump"
}

docker compose cp $DatabaseDump db:/tmp/coalflow-restore.dump
docker compose exec -T db sh -lc 'dropdb -U "${POSTGRES_USER:-coalflow}" --if-exists "${POSTGRES_DB:-coalflow}" && createdb -U "${POSTGRES_USER:-coalflow}" "${POSTGRES_DB:-coalflow}" && pg_restore -U "${POSTGRES_USER:-coalflow}" -d "${POSTGRES_DB:-coalflow}" /tmp/coalflow-restore.dump'
docker compose exec -T db rm -f /tmp/coalflow-restore.dump

if ($ExportArchive -and (Test-Path -LiteralPath $ExportArchive)) {
  docker compose cp $ExportArchive api:/tmp/coalflow-exports-restore.tgz
  docker compose exec -T api sh -lc 'mkdir -p /tmp/coalflow_exports && tar -C /tmp/coalflow_exports -xzf /tmp/coalflow-exports-restore.tgz && rm -f /tmp/coalflow-exports-restore.tgz'
}

Write-Host "Restore completed. Restart API/worker if they were running against the restored database."
