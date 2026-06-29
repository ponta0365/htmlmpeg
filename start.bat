@echo off
setlocal EnableExtensions

cd /d "%~dp0" || exit /b 1

set "FORCE_PYTHON="
if /I "%~1"=="--force-python" set "FORCE_PYTHON=-ForcePython"
if /I "%~1"=="/force-python" set "FORCE_PYTHON=-ForcePython"
if /I "%~1"=="force-python" set "FORCE_PYTHON=-ForcePython"

if defined FORCE_PYTHON (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %FORCE_PYTHON%
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
)

set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo Start failed with exit code %EXITCODE%
  pause
)

exit /b %EXITCODE%
