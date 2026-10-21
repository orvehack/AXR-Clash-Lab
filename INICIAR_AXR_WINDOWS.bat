@echo off
setlocal
title AXR Clash Lab - Windows 11
cd /d "%~dp0"
echo.
echo ==========================================
echo   AXR CLASH LAB - PRIMER INICIO
echo ==========================================
echo.
if not exist "scripts\first_run_windows.ps1" (
  echo ERROR: No encuentro scripts\first_run_windows.ps1.
  echo Descarga y extrae el ZIP completo del repositorio.
  echo.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\first_run_windows.ps1"
set "AXR_EXIT=%ERRORLEVEL%"
echo.
if not "%AXR_EXIT%"=="0" (
  echo El inicio termino con un error. Copia el mensaje anterior y mandaselo a ChatGPT.
) else (
  echo El iniciador termino. Revisa los resultados que aparecen arriba.
)
echo.
pause
exit /b %AXR_EXIT%
