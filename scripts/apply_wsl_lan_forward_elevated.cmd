@echo off
REM =====================================================================
REM apply_wsl_lan_forward_elevated.cmd
REM Self-elevating launcher for apply_wsl_lan_forward.ps1
REM Double-click this file (or run from any shell) - UAC prompt appears.
REM Result window stays open so you can copy the output back.
REM =====================================================================
setlocal
cd /d "%~dp0.."

echo Requesting administrator privileges...
powershell -NoProfile -Command "Start-Process -FilePath powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%~dp0apply_wsl_lan_forward.ps1\"' -Verb RunAs"
if errorlevel 1 (
  echo [FAIL] Elevation was denied or PowerShell could not start.
  pause
  exit /b 1
)
echo An elevated PowerShell window was opened. Copy its output back to the assistant.
pause
