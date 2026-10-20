# Probar RoyaleGym en Windows

Esta es una prueba de integración inicial: comprueba si el paquete se puede importar y qué interfaces ofrece el entorno. No ejecuta acciones (`step`) ni juega en el cliente de Clash Royale.

## Requisitos

El README de RoyaleGym indica Python 3.12 y recomienda instalar el paquete con sus extras para seguir el flujo completo. Revisa también su documentación actual: https://royalegym.github.io/RoyaleGym/install/

## Pasos

Desde PowerShell, dentro de la carpeta del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "royalegym[all]"
python src\simulator_adapter.py
```

Si PowerShell bloquea la activación del entorno, se puede ejecutar directamente el Python del entorno sin cambiar la política global:

```powershell
.\.venv\Scripts\python.exe -m pip install "royalegym[all]"
.\.venv\Scripts\python.exe src\simulator_adapter.py
```

El script imprime JSON con el tipo de entorno, espacios de observación/acción y forma de la observación. Si no encuentra RoyaleGym, devuelve un diagnóstico. Si falla por incompatibilidad, guarda el error para investigar antes de adaptar una política.

## Pruebas locales sin instalar RoyaleGym

```powershell
py -m unittest discover -s tests -v
```

Las pruebas del adaptador usan entornos falsos y no requieren instalar RoyaleGym. La prueba real del simulador sí debe ejecutarse en el PC donde se instalará la dependencia.

## Qué sigue tras obtener el diagnóstico

1. Confirmar que el entorno se crea y se cierra correctamente.
2. Inspeccionar el formato real de observaciones y acciones documentado por la versión instalada.
3. Implementar una política de referencia que use solo acciones válidas.
4. Ejecutar episodios simulados y registrar semillas, recompensas y resultados antes de entrenar un modelo.

No conectes este adaptador a partidas competitivas reales. El objetivo aquí es simulación offline y experimentación reproducible.
