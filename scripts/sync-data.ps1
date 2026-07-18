<#
.SYNOPSIS
  Push the archive data (link-rewritten captures + archive.json) to the server.

.DESCRIPTION
  Re-exports the data (unless -SkipExport) then uploads it to /srv/which on the
  server. It packs the captures into a temp tarball and copies it with scp, then
  extracts on the server. This avoids `tar czf - | ssh` — that pipe works in
  bash but PowerShell re-encodes the binary stream and corrupts it
  ("gzip: stdin: not in gzip format").

.EXAMPLE
  ./scripts/sync-data.ps1              # export, then sync to the server
.EXAMPLE
  ./scripts/sync-data.ps1 -SkipExport # sync already-exported data as-is
#>
[CmdletBinding()]
param(
  [switch]$SkipExport,
  [string]$RemoteUser = 'chris',
  [string]$RemoteHost = $env:WHICH_HOST,
  [int]$Port = 22222
)

$ErrorActionPreference = 'Stop'

if (-not $RemoteHost) {
  throw 'Set the deploy host: pass -RemoteHost <addr> or set $env:WHICH_HOST.'
}
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$remote = "$RemoteUser@$RemoteHost"

if (-not $SkipExport) {
  Write-Host 'Exporting archive data (rewriting captures)...' -ForegroundColor Yellow
  uv run python export_archive_data.py
}

$captures = Join-Path $root 'archive-web/static/captures'
$dataFile = Join-Path $root 'archive-web/static/data/archive.json'
$tmp = Join-Path $env:TEMP 'which-captures.tgz'

Write-Host "Packing captures -> $tmp ..." -ForegroundColor Yellow
tar czf "$tmp" -C "$captures" raw-html mhtml
Write-Host ('Uploading captures ({0:N0} MB)...' -f ((Get-Item $tmp).Length / 1MB)) -ForegroundColor Yellow
scp -P $Port "$tmp" "${remote}:/tmp/which-captures.tgz"
Write-Host 'Extracting on server...' -ForegroundColor Yellow
ssh -p $Port $remote 'tar xzf /tmp/which-captures.tgz -C /srv/which/captures && rm -f /tmp/which-captures.tgz'
Write-Host 'Uploading archive.json...' -ForegroundColor Yellow
scp -P $Port "$dataFile" "${remote}:/srv/which/data/archive.json"
Remove-Item "$tmp" -ErrorAction SilentlyContinue

Write-Host 'Done. Server updated (site picks it up immediately).' -ForegroundColor Green
