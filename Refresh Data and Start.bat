@echo off
cd /d "%~dp0"
title Which Archive (refresh)
echo.
echo   Which Archive - rebuilding data, then launching
echo   ----------------------------------------------
echo   Run this after a new scrape. It re-exports the data and
echo   rewrites captures first (can take a few minutes), then
echo   opens http://localhost:5173.
echo   Keep this window OPEN while you browse.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-site.ps1" -Refresh %*
echo.
echo   The site has stopped.
pause
