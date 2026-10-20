# Inicio rápido en Windows 11

Esta guía ejecuta el análisis localmente. No necesita conectarse al juego ni instalar paquetes externos.

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

Se recomienda Python 3.11 o posterior.

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
