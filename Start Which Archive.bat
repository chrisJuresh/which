@echo off
cd /d "%~dp0"
title Which Archive
echo.
echo   Which Archive - launching the local website
echo   -------------------------------------------
echo   A browser tab will open at http://localhost:5173
echo   Keep this window OPEN while you browse.
echo   Close this window or press Ctrl+C to stop the site.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-site.ps1" %*
echo.
echo   The site has stopped.
pause
