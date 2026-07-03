<#
.SYNOPSIS
  Bring the Which Archive website up locally.

.DESCRIPTION
  One command to view the archive on this PC. It makes sure the Python and web
  dependencies are installed, (re)builds the archive data + link-rewritten
  captures when needed, then starts the SvelteKit dev server.

.PARAMETER Refresh
  Force a fresh data export + capture rewrite before starting, even if data
  already exists. Run this after a new scrape.

.PARAMETER Port
  Dev server port (default 5173).

.EXAMPLE
  ./scripts/run-site.ps1            # start (exports data only if missing)

.EXAMPLE
  ./scripts/run-site.ps1 -Refresh   # re-export after a new scrape, then start
#>
[CmdletBinding()]
param(
  [switch]$Refresh,
  [int]$Port = 5173
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "== Which Archive =====================================" -ForegroundColor Cyan
Write-Host "Project: $root"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is not installed. Install it from https://docs.astral.sh/uv/ then re-run."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "Node.js / npm is not installed. Install Node 18+ then re-run."
}

# --- Python environment -------------------------------------------------
if (-not (Test-Path ".venv")) {
  Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
  uv venv
}
Write-Host "Ensuring Python dependencies..." -ForegroundColor Yellow
uv pip install -r requirements.txt | Out-Null

# --- Web dependencies ---------------------------------------------------
if (-not (Test-Path "archive-web/node_modules")) {
  Write-Host "Installing web dependencies (npm install)..." -ForegroundColor Yellow
  Push-Location archive-web
  try { npm install } finally { Pop-Location }
}

# --- Data + captures ----------------------------------------------------
$dataFile = Join-Path $root "archive-web/static/data/archive.json"
if ($Refresh -or -not (Test-Path $dataFile)) {
  Write-Host "Exporting archive data + rewriting captures..." -ForegroundColor Yellow
  Write-Host "(first run parses every capture; this can take several minutes)" -ForegroundColor DarkGray
  uv run python export_archive_data.py
} else {
  Write-Host "Using existing data ($dataFile)." -ForegroundColor DarkGray
  Write-Host "Run with -Refresh after a new scrape to rebuild it." -ForegroundColor DarkGray
}

# --- Start the site -----------------------------------------------------
Write-Host "Starting dev server on http://localhost:$Port ..." -ForegroundColor Green
Push-Location archive-web
try {
  npx vite dev --port $Port --open
} finally {
  Pop-Location
}
