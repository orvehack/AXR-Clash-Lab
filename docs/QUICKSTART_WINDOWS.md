# Inicio rápido en Windows 11

Esta guía empieza con comprobaciones seguras y no instala el stack pesado de IA. El entrenamiento y el motor RoyaleGym se configuran después de confirmar que el proyecto base funciona.

## Opción recomendada: comprobación guiada

1. Descarga el repositorio como se indica más abajo y entra a su carpeta.
2. Abre PowerShell dentro de esa carpeta.
3. Ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\first_run_windows.ps1
```

El script exige Python 3.12, crea el entorno aislado `.venv`, ejecuta `src.doctor`, corre las pruebas offline y valida los planes sin iniciar entrenamiento ni descargar modelos. Al final te pregunta si quieres abrir la interfaz. Si falla, copia el error completo antes de seguir; no instales más paquetes a ciegas.

Si prefieres revisar cada paso manualmente, sigue la guía de abajo.

## 1. Descargar el repositorio

Abre PowerShell y ejecuta:

```powershell
git clone https://github.com/orvehack/AXR-Clash-Lab.git
cd AXR-Clash-Lab
```

Si Windows dice que `git` no existe, descarga el ZIP desde GitHub y descomprímelo; después abre PowerShell dentro de la carpeta del proyecto.

## 2. Comprobar Python

```powershell
py --version
```

Para la interfaz y las pruebas básicas se recomienda Python 3.11 o posterior. Para el flujo documentado de RoyaleGym, usa Python 3.12.

## 3. Ejecutar el análisis

Desde la carpeta raíz del repositorio:

```powershell
py src\match_stats.py
```

Para analizar otro CSV:

```powershell
py src\match_stats.py ruta\a\mis_partidas.csv
```

El CSV debe incluir las columnas `result`, `opponent_deck` y `trophy_delta`. Se pueden conservar también las columnas adicionales como `date`, `own_deck` y `notes`.

Resultados reconocidos: `win`, `won`, `victoria`, `victorias`, `loss`, `lost`, `derrota` y `derrotas`.

## 4. Ejecutar las pruebas

```powershell
py -m unittest discover -s tests -v
```

Las pruebas usan datos temporales y no modifican el registro de partidas.

## Importante

`data/matches.csv` contiene partidas ficticias de ejemplo para comprobar el funcionamiento del analizador. Sustitúyelas o añade tus propios datos antes de interpretar las estadísticas como resultados reales.
