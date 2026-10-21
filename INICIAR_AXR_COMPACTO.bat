@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m src.axr_compact_ui
) else (
  py -3 -m src.axr_compact_ui
)
if errorlevel 1 (
  echo.
  echo AXR Compacto no pudo iniciarse. Revisa Python/Tkinter y las dependencias.
  pause
)
endlocal
