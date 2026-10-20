# Probar RoyaleGym en Windows

Hay dos comprobaciones distintas: `simulator_adapter.py` inspecciona el entorno con un reset sin ejecutar acciones; `royalegym_contract.py` ejecuta unos pocos pasos NOOP contra `MockEngine` para comprobar el contrato de reset/step, las máscaras y las recompensas. Ninguna usa emuladores ni juega en el cliente oficial. `MockEngine` es un motor de referencia en Python, no una simulación fiel del juego real.

## Requisitos

El README de RoyaleGym indica Python 3.12 y recomienda instalar el paquete con sus extras para seguir el flujo completo. Revisa también su documentación actual: https://royalegym.github.io/RoyaleGym/install/

## Pasos

Desde PowerShell, dentro de la carpeta del repositorio:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "royalegym[all]"
python -m src.simulator_adapter
python -m src.royalegym_contract --steps 3
```

Si PowerShell bloquea la activación del entorno, se puede ejecutar directamente el Python del entorno sin cambiar la política global:

```powershell
.\.venv\Scripts\python.exe -m pip install "royalegym[all]"
.\.venv\Scripts\python.exe -m src.simulator_adapter
.\.venv\Scripts\python.exe -m src.royalegym_contract --steps 3
```

`simulator_adapter.py` imprime JSON con espacios y forma de la observación. `royalegym_contract.py` comprueba los mappings de ambos asientos, `action_mask`, una acción válida, recompensas finitas y tipos de terminación. Si falla por incompatibilidad, imprime un diagnóstico JSON para investigar antes de adaptar una política.

## Pruebas locales sin instalar RoyaleGym

```powershell
py -m unittest discover -s tests -v
```

Las pruebas unitarias de los helpers usan objetos falsos y no requieren instalar RoyaleGym. La prueba de contrato requiere el paquete RoyaleGym; por defecto usa `MockEngine`. La prueba con `RustEngine` y el entrenador sigue pendiente y debe ejecutarse en el PC donde se instalen las dependencias.

## Qué sigue tras obtener el diagnóstico

1. Confirmar que el entorno se crea y se cierra correctamente.
2. Inspeccionar el formato real de observaciones y acciones documentado por la versión instalada.
3. Ejecutar `python -m src.royalegym_contract --steps 3` y guardar su JSON como evidencia del entorno instalado.
4. Implementar una política de referencia que use solo acciones válidas.
5. Ejecutar episodios simulados con el motor Rust y registrar semillas, recompensas y resultados antes de entrenar un modelo.

No conectes este adaptador a partidas competitivas reales. El objetivo aquí es simulación offline y experimentación reproducible.
