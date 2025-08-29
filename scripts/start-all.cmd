@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PS1=%SCRIPT_DIR%start-all.ps1
if not exist "%PS1%" (
  echo [ERR ] Cannot find start-all.ps1 next to this file.
  pause
  exit /b 1
)

:: Force NoExit so the window stays open and you can read errors
powershell -NoExit -ExecutionPolicy Bypass -NoProfile -File "%PS1%" %*

:: Fallback pause in case PowerShell returns immediately
pause
