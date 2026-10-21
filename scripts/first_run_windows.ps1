# AXR Clash Lab: first-run setup for Windows 11.
# Creates an isolated Python environment, runs offline tests, and optionally opens the UI.
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host ""
Write-Host "=== AXR Clash Lab | primera comprobacion ===" -ForegroundColor Cyan
Write-Host "Carpeta: $RepoRoot"
Write-Host "Este script NO instala RoyaleGym/PyTorch ni controla el juego."
Write-Host ""

$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonLauncher) {
    throw "No encuentro el lanzador 'py'. Instala Python 3.12 desde python.org y marca 'Add Python to PATH'. Luego vuelve a ejecutar este archivo."
}

$VersionOutput = & py -3.12 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "No encuentro Python 3.12. Instala Python 3.12; no cambiare tu instalacion automaticamente."
}
Write-Host "Python detectado: $VersionOutput" -ForegroundColor Green

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creando entorno virtual .venv..."
    & py -3.12 -m venv (Join-Path $RepoRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear .venv." }
} else {
    Write-Host "El entorno .venv ya existe; lo reutilizare."
}

Write-Host ""
Write-Host "1/3 - Diagnostico local" -ForegroundColor Cyan
& $VenvPython -m src.doctor
if ($LASTEXITCODE -ne 0) {
    throw "El diagnostico detecto un problema basico. Copia el JSON del diagnostico y mandamelo."
}

Write-Host ""
Write-Host "2/3 - Pruebas offline" -ForegroundColor Cyan
& $VenvPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw "Alguna prueba fallo. No iniciare el entrenamiento; copia el error y lo revisamos."
}

Write-Host ""
Write-Host "3/3 - Validar planes sin entrenar ni descargar modelos" -ForegroundColor Cyan
& $VenvPython -m src.train_agent --plan-only --steps 1000 --save-dir runs\preflight
if ($LASTEXITCODE -ne 0) { throw "Fallo el plan de entrenamiento." }
& $VenvPython -m src.imitate_agent --plan-only --matches 5 --out-dir runs\imitation_preflight
if ($LASTEXITCODE -ne 0) { throw "Fallo el plan de imitacion." }

Write-Host ""
Write-Host "Comprobaciones basicas completadas. Aun NO se ha probado el motor RoyaleGym ni entrenado una IA." -ForegroundColor Green
Write-Host "Para abrir la interfaz: .\.venv\Scripts\python.exe -m src.axr_desktop"
Write-Host "Para revisar el emulador: .\.venv\Scripts\python.exe -m src.emulator_manager diagnostics"
Write-Host ""

$OpenUi = Read-Host "Quieres abrir ahora la interfaz de AXR? (S/N)"
if ($OpenUi -match '^(S|SI|Y|YES)$') {
    & $VenvPython -m src.axr_desktop
}
