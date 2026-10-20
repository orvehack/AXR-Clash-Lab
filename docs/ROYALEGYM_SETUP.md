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


## Imitation learning y warm-start opcional

La pipeline cooperativa usa [RoyaleImitate](https://github.com/RoyaleGym/RoyaleImitate) para producir un actor de demostraciones, y después [RoyaleLearn](https://github.com/RoyaleGym/RoyaleLearn) para afinarlo con PPO en el simulador.

1. Instala la parte opcional de imitación según la guía upstream y comprueba que la versión de RoyaleGym/RoyaleLearn coincide con la del artefacto.
2. Crea un actor de RoyaleImitate y conserva su carpeta de artefacto completa (incluye metadatos y huellas de prueba).
3. Ejecuta un plan corto primero, sin entrenar:
   `python -m src.train_agent --plan-only --steps 10000 --save-dir runs/axr_warmstart --warm-start runs/teacher-actor`
4. Tras revisar la configuración, inicia una corrida pequeña con el mismo comando quitando `--plan-only`.

`--warm-start` espera una carpeta de artefacto de actor de RoyaleImitate, no una ruta a un checkpoint PPO arbitrario. La compatibilidad del artefacto debe ser verificada por RoyaleImitate/RoyaleLearn. Tras entrenar, AXR intenta exportar `runs/.../axr_actor` como artefacto reutilizable; si RoyaleImitate no está instalado, conserva el checkpoint PPO normal y registra que no exportó el actor.

Esto es una ruta de integración de código, no evidencia de que el entrenamiento ya haya funcionado: no se ha ejecutado en la PC del usuario ni validado con el motor Rust.


### Instalar el componente de imitación

En un entorno Python compatible con las versiones upstream, instala las dependencias de imitación y lectura de replays:

```powershell
python -m pip install "royaleimitate[replays,torch]"
```

Sigue además la guía upstream de [RoyaleGym](https://github.com/RoyaleGym/RoyaleGym) para el motor y las dependencias de entrenamiento. No mezcles instalaciones de versiones incompatibles en el mismo entorno.

### Ejecutar la pipeline de demostraciones

Primero, sin descargar ni entrenar:

```powershell
python -m src.imitate_agent --plan-only --matches 25 --out-dir runs/axr_imitation_smoke
```

Luego, una prueba pequeña:

```powershell
python -m src.imitate_agent --matches 25 --epochs 2 --out-dir runs/axr_imitation_smoke
```

La carpeta `runs/axr_imitation_smoke/axr_imitation_actor` contiene el artefacto que puede usarse para inicializar PPO:

```powershell
python -m src.train_agent --plan-only --steps 10000 --save-dir runs/axr_ppo_smoke --warm-start runs/axr_imitation_smoke/axr_imitation_actor
```

Quita `--plan-only` de `src.train_agent` únicamente después de revisar el plan. Las rutas y ejemplos anteriores no se han ejecutado en el equipo del usuario.
