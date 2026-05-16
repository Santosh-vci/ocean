param(
  [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\backup.ps1" -OutputDir $OutputDir

$latestDump = Get-ChildItem -Path $OutputDir -Filter "coalflow-db-*.dump" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $latestDump) {
  throw "No database dump was produced."
}

docker compose cp $latestDump.FullName db:/tmp/coalflow-rehearsal.dump
docker compose exec -T db sh -lc 'pg_restore -l /tmp/coalflow-rehearsal.dump >/tmp/coalflow-rehearsal.list && test -s /tmp/coalflow-rehearsal.list'
docker compose exec -T db rm -f /tmp/coalflow-rehearsal.dump /tmp/coalflow-rehearsal.list

Write-Host "Backup rehearsal passed: $($latestDump.FullName)"
